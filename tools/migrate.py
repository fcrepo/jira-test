#!/usr/bin/env python3
"""Export the FCREPO Jira project, build a static archive, and import open issues to GitHub.

Subcommands:
  export   download issues (JSON) and attachments from Jira
  archive  generate static HTML pages from the exported JSON
  convert  generate GitHub issue payloads for the issues in scope
  import   create the converted issues in a GitHub repository

Requires Python 3.9+ and, for import, an authenticated gh CLI. No other dependencies.
"""

import argparse
import base64
import datetime
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import adf

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
DATA = ROOT / "data"
ATTACHMENTS = ROOT / "attachments"
OUT = ROOT / "out"
CONFIG = json.loads((TOOLS / "config.json").read_text())

BODY_LIMIT = 65000
PLACEHOLDER = re.compile(r"\{\{jira:([A-Z][A-Z0-9]+-\d+)\}\}")


def log(message):
    print(message, file=sys.stderr, flush=True)


def key_number(key):
    return int(key.rsplit("-", 1)[1])


def load_issues():
    files = sorted(DATA.glob("%s-*.json" % CONFIG["project"]), key=lambda p: key_number(p.stem))
    if not files:
        sys.exit("No exported issues in %s. Run 'export' first." % DATA)
    return [json.loads(p.read_text()) for p in files]


def parse_date(value):
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(datetime.timezone.utc)


def show_date(value, time_of_day=False):
    if not value:
        return ""
    return parse_date(value).strftime("%Y-%m-%d %H:%M UTC" if time_of_day else "%Y-%m-%d")


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:150] or "file"


def attachment_path(key, attachment):
    """Path of an attachment relative to the archive root."""
    return "attachments/%s/%s_%s" % (key, attachment["id"], safe_name(attachment["filename"]))


def names(items):
    return [i["name"] for i in items or []]


def person(user):
    return (user or {}).get("displayName") or ""


# ---------------------------------------------------------------- Jira export

class _DropAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward Jira credentials to the media host that serves attachments."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            new.headers.pop("Authorization", None)
            new.unredirected_hdrs.pop("Authorization", None)
        return new


OPENER = urllib.request.build_opener(_DropAuthOnRedirect)


def jira_get(path, params=None, binary=False, retries=6):
    url = path if path.startswith("http") else CONFIG["jira_base"] + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "*/*" if binary else "application/json", "User-Agent": "fcrepo-jira-export"}
    # Anonymous access reads public issues. Set both variables to include restricted issues.
    if os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_TOKEN"):
        pair = "%s:%s" % (os.environ["JIRA_EMAIL"], os.environ["JIRA_TOKEN"])
        headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
    for attempt in range(retries):
        try:
            with OPENER.open(urllib.request.Request(url, headers=headers), timeout=180) as response:
                body = response.read()
            return body if binary else json.loads(body)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
            wait = int(error.headers.get("Retry-After") or 5 * 2 ** attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == retries - 1:
                raise
            wait = 5 * 2 ** attempt
        log("  retry in %ds: %s" % (wait, url[:100]))
        time.sleep(wait)


def fetch_all_comments(key):
    comments, rendered, start = [], [], 0
    while True:
        page = jira_get("/rest/api/3/issue/%s/comment" % key,
                        {"startAt": start, "maxResults": 100, "expand": "renderedBody"})
        for comment in page["comments"]:
            rendered.append({"id": comment["id"], "created": comment.get("created"),
                             "body": comment.pop("renderedBody", "")})
            comments.append(comment)
        start += len(page["comments"])
        if start >= page["total"] or not page["comments"]:
            return comments, rendered


def cmd_export(args):
    DATA.mkdir(exist_ok=True)
    jql = args.jql or "project = %s ORDER BY key ASC" % CONFIG["project"]
    token, count, skipped, total_bytes = None, 0, [], 0
    while True:
        params = {"jql": jql, "maxResults": 50, "fields": "*all", "expand": "renderedFields"}
        if token:
            params["nextPageToken"] = token
        page = jira_get("/rest/api/3/search/jql", params)
        for issue in page.get("issues", []):
            key = issue["key"]
            comment = issue["fields"].get("comment") or {}
            if comment.get("total", 0) > len(comment.get("comments", [])):
                comments, rendered = fetch_all_comments(key)
                issue["fields"]["comment"]["comments"] = comments
                issue["renderedFields"]["comment"] = {"comments": rendered}
            (DATA / (key + ".json")).write_text(json.dumps(issue, indent=1, ensure_ascii=False, sort_keys=True))
            count += 1
            if args.no_attachments:
                continue
            for attachment in issue["fields"].get("attachment") or []:
                target = ROOT / attachment_path(key, attachment)
                size = attachment.get("size", 0)
                if size > CONFIG["max_attachment_bytes"]:
                    skipped.append("%s %s (%d bytes)" % (key, attachment["filename"], size))
                    continue
                total_bytes += size
                if target.exists() and target.stat().st_size == size:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_bytes(jira_get(attachment["content"], binary=True))
                except urllib.error.HTTPError as error:
                    skipped.append("%s %s (HTTP %d)" % (key, attachment["filename"], error.code))
        log("exported %d issues" % count)
        token = page.get("nextPageToken")
        if not token:
            break
    log("Done: %d issues, %.1f MB of attachments" % (count, total_bytes / 1e6))
    for line in skipped:
        log("SKIPPED attachment: " + line)


# ------------------------------------------------------------- static archive

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<a href="index.html">Fedora Repository Jira archive</a>
<span>Read-only. Report new issues at <a href="https://github.com/{tracker}/issues">github.com/{tracker}</a>.</span>
</header>
<main>
{body}
</main>
<footer>Exported from {jira_base} on {exported}.</footer>
</body>
</html>
"""

STYLE = """body { font: 15px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1f2328; margin: 0; background: #fff; }
header { background: #f6f8fa; border-bottom: 1px solid #d0d7de; padding: 10px 16px; display: flex; gap: 16px; flex-wrap: wrap; justify-content: space-between; }
header a:first-child { font-weight: 600; }
main { max-width: 1000px; margin: 0 auto; padding: 16px; overflow-wrap: anywhere; }
footer { max-width: 1000px; margin: 0 auto; padding: 16px; color: #656d76; font-size: 13px; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 24px; margin: 8px 0 16px; }
h2 { font-size: 18px; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; margin-top: 32px; }
table { border-collapse: collapse; }
th, td { border: 1px solid #d0d7de; padding: 4px 10px; text-align: left; vertical-align: top; }
table.meta th { background: #f6f8fa; width: 160px; font-weight: 600; }
table.list { width: 100%; }
table.list th { background: #f6f8fa; }
pre { background: #f6f8fa; padding: 10px; overflow-x: auto; font-size: 13px; }
code, tt { background: #f6f8fa; padding: 1px 4px; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; }
img { max-width: 100%; height: auto; }
.notice { background: #ddf4ff; border: 1px solid #54aeff; padding: 8px 12px; margin: 12px 0; }
.comment { border: 1px solid #d0d7de; margin: 12px 0; }
.comment .by { background: #f6f8fa; border-bottom: 1px solid #d0d7de; padding: 6px 12px; font-size: 13px; }
.comment .text { padding: 4px 12px; }
.key { white-space: nowrap; }
input#filter { width: 100%; box-sizing: border-box; padding: 8px; font-size: 15px; margin: 8px 0 16px; }
blockquote { border-left: 4px solid #d0d7de; margin-left: 0; padding-left: 12px; color: #656d76; }
"""

FILTER_SCRIPT = """<script>
document.getElementById('filter').addEventListener('input', function () {
  var terms = this.value.toLowerCase().split(/\\s+/).filter(Boolean);
  var rows = document.querySelectorAll('table.list tbody tr');
  for (var i = 0; i < rows.length; i++) {
    var text = rows[i].textContent.toLowerCase();
    rows[i].hidden = !terms.every(function (t) { return text.indexOf(t) !== -1; });
  }
});
</script>"""


def rewrite_html(text, issue, known_keys):
    """Make Jira-rendered HTML work outside Jira."""
    if not text:
        return ""
    key = issue["key"]
    base = re.escape(CONFIG["jira_base"])
    attachments = {a["id"]: a for a in issue["fields"].get("attachment") or []}

    text = re.sub(r"(?is)<script\b.*?</script>", "", text)
    text = re.sub(r"(?is)<(iframe|object|embed|form)\b.*?</\1>", "", text)
    text = re.sub(r"""(?i)\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", text)
    text = re.sub(r"""(?i)(href|src)\s*=\s*(["'])\s*javascript:[^"']*\2""", r'\1="#"', text)
    text = re.sub(r'<sup>\s*<img class="rendericon"[^>]*>\s*</sup>', "", text)
    text = re.sub(r'<img class="rendericon"[^>]*>', "", text)
    text = re.sub(r'<img class="icon"[^>]*>', "", text)
    text = re.sub(r'<img class="emoticon"[^>]*?alt="([^"]*)"[^>]*>', r"\1", text)

    def attachment(match):
        item = attachments.get(match.group(2))
        if item and (ROOT / attachment_path(key, item)).exists():
            return '%s="%s"' % (match.group(1), urllib.parse.quote(attachment_path(key, item)))
        return '%s="%s/rest/api/3/attachment/content/%s"' % (match.group(1), CONFIG["jira_base"], match.group(2))

    text = re.sub(r'(href|src)="(?:%s)?/rest/api/3/attachment/(?:content|thumbnail)/(\d+)"' % base,
                  attachment, text)

    def browse(match):
        if match.group(1) in known_keys:
            return 'href="%s.html"' % match.group(1)
        return 'href="%s/browse/%s"' % (CONFIG["jira_base"], match.group(1))

    text = re.sub(r'href="(?:%s)?/browse/([A-Z][A-Z0-9]+-\d+)[^"]*"' % base, browse, text)
    text = re.sub(r'<a [^>]*href="(?:%s)?/secure/ViewProfile[^"]*"[^>]*>(.*?)</a>' % base, r"\1", text, flags=re.S)
    text = re.sub(r'(href|src)="/(?!/)', r'\1="%s/' % CONFIG["jira_base"], text)
    return text


def issue_link(key, known_keys, summary=""):
    label = html.escape(key)
    if key in known_keys:
        label = '<a href="%s.html">%s</a>' % (key, label)
    return label + (" " + html.escape(summary) if summary else "")


def archive_issue(issue, known_keys, migrated, exported):
    key, fields, rendered = issue["key"], issue["fields"], issue.get("renderedFields") or {}
    rows = [
        ("Type", html.escape(fields["issuetype"]["name"])),
        ("Status", html.escape(fields["status"]["name"])),
        ("Resolution", html.escape((fields.get("resolution") or {}).get("name", ""))),
        ("Priority", html.escape((fields.get("priority") or {}).get("name", ""))),
        ("Reporter", html.escape(person(fields.get("reporter")))),
        ("Assignee", html.escape(person(fields.get("assignee")))),
        ("Created", show_date(fields.get("created"), True)),
        ("Updated", show_date(fields.get("updated"), True)),
        ("Resolved", show_date(fields.get("resolutiondate"), True)),
        ("Components", html.escape(", ".join(names(fields.get("components"))))),
        ("Affects versions", html.escape(", ".join(names(fields.get("versions"))))),
        ("Fix versions", html.escape(", ".join(names(fields.get("fixVersions"))))),
        ("Labels", html.escape(", ".join(fields.get("labels") or []))),
    ]
    if fields.get("parent"):
        parent = fields["parent"]
        rows.append(("Parent", issue_link(parent["key"], known_keys, parent.get("fields", {}).get("summary", ""))))
    if fields.get("subtasks"):
        rows.append(("Sub-tasks", "<br>".join(
            issue_link(s["key"], known_keys, s.get("fields", {}).get("summary", "")) for s in fields["subtasks"])))
    for text, other in issue_links(fields):
        rows.append((html.escape(text.capitalize()),
                     issue_link(other["key"], known_keys, other.get("fields", {}).get("summary", ""))))

    body = ["<h1><span class=\"key\">%s</span> %s</h1>" % (key, html.escape(fields.get("summary") or ""))]
    if key in migrated:
        url = "https://github.com/%s/issues/%d" % (CONFIG["tracker"], migrated[key])
        body.append('<p class="notice">This issue continues at <a href="%s">%s#%d</a>.</p>'
                    % (url, CONFIG["tracker"], migrated[key]))
    body.append('<table class="meta">%s</table>' % "".join(
        "<tr><th>%s</th><td>%s</td></tr>" % row for row in rows if row[1]))
    if fields.get("environment"):
        body.append("<h2>Environment</h2>" + rewrite_html(rendered.get("environment"), issue, known_keys))
    body.append("<h2>Description</h2>")
    body.append(rewrite_html(rendered.get("description"), issue, known_keys) or "<p><em>No description.</em></p>")

    attachments = fields.get("attachment") or []
    if attachments:
        body.append("<h2>Attachments</h2><ul>")
        for item in attachments:
            path = attachment_path(key, item)
            if (ROOT / path).exists():
                link = '<a href="%s">%s</a>' % (urllib.parse.quote(path), html.escape(item["filename"]))
            else:
                link = html.escape(item["filename"]) + " (not archived)"
            body.append("<li>%s, %s bytes, added by %s on %s</li>" % (
                link, item.get("size", "?"), html.escape(person(item.get("author"))), show_date(item.get("created"))))
        body.append("</ul>")

    comments = (fields.get("comment") or {}).get("comments") or []
    rendered_comments = (rendered.get("comment") or {}).get("comments") or []
    if comments:
        body.append("<h2>Comments (%d)</h2>" % len(comments))
        for index, comment in enumerate(comments):
            text = rendered_comments[index].get("body") if index < len(rendered_comments) else ""
            body.append('<div class="comment" id="comment-%s"><div class="by">%s, %s</div><div class="text">%s</div></div>' % (
                comment["id"], html.escape(person(comment.get("author"))), show_date(comment.get("created"), True),
                rewrite_html(text, issue, known_keys)))

    body.append('<p><a href="data/%s.json">Raw Jira JSON</a></p>' % key)
    return PAGE.format(title=html.escape("%s %s" % (key, fields.get("summary") or "")), body="\n".join(body),
                       tracker=CONFIG["tracker"], jira_base=CONFIG["jira_base"], exported=exported)


def issue_links(fields):
    """Yield (relationship text, linked issue) for each Jira issue link."""
    for link in fields.get("issuelinks") or []:
        if link.get("outwardIssue"):
            yield link["type"]["outward"], link["outwardIssue"]
        elif link.get("inwardIssue"):
            yield link["type"]["inward"], link["inwardIssue"]


def cmd_archive(args):
    issues = load_issues()
    known_keys = {i["key"] for i in issues}
    migrated = {}
    if args.mapping:
        migrated = {k: v["number"] for k, v in json.loads(Path(args.mapping).read_text())["issues"].items()}
    exported = datetime.datetime.fromtimestamp(
        max(p.stat().st_mtime for p in DATA.glob("*.json")), datetime.timezone.utc).strftime("%Y-%m-%d")
    for issue in issues:
        (ROOT / (issue["key"] + ".html")).write_text(archive_issue(issue, known_keys, migrated, exported))

    rows = []
    for issue in reversed(issues):
        fields = issue["fields"]
        rows.append("<tr><td class=\"key\"><a href=\"%s.html\">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            issue["key"], issue["key"], html.escape(fields.get("summary") or ""),
            html.escape(fields["issuetype"]["name"]), html.escape(fields["status"]["name"]),
            html.escape(", ".join(names(fields.get("components")))), show_date(fields.get("created"))))
    body = ("<h1>Fedora Repository Jira archive</h1>"
            "<p>%d issues from the %s project. Filter by any text in the row.</p>"
            "<input id=\"filter\" type=\"search\" placeholder=\"Filter, e.g. ocfl bug open\" autofocus>"
            "<table class=\"list\"><thead><tr><th>Key</th><th>Summary</th><th>Type</th><th>Status</th>"
            "<th>Components</th><th>Created</th></tr></thead><tbody>%s</tbody></table>%s"
            % (len(issues), CONFIG["project"], "\n".join(rows), FILTER_SCRIPT))
    (ROOT / "index.html").write_text(PAGE.format(
        title="Fedora Repository Jira archive", body=body, tracker=CONFIG["tracker"],
        jira_base=CONFIG["jira_base"], exported=exported))
    (ROOT / "style.css").write_text(STYLE)
    (ROOT / ".nojekyll").write_text("")
    log("Wrote %d issue pages and index.html to %s" % (len(issues), ROOT))


# ------------------------------------------------------- GitHub issue payloads

def in_scope(issue):
    fields = issue["fields"]
    return (fields["status"]["statusCategory"]["key"] != "done"
            and fields["created"][:10] >= CONFIG["cutoff"])


def archive_url(key):
    return "%s/%s" % (CONFIG["archive_base"], key)


def media_lookup(issue):
    """Map Jira media ids and file names to archived attachment URLs."""
    key = issue["key"]
    by_id, by_name, by_attachment = {}, {}, {}
    for item in issue["fields"].get("attachment") or []:
        if (ROOT / attachment_path(key, item)).exists():
            url = "%s/%s" % (CONFIG["archive_base"], urllib.parse.quote(attachment_path(key, item)))
        else:
            url = item["content"]
        entry = {"url": url, "name": item["filename"],
                 "image": (item.get("mimeType") or "").startswith("image/")}
        by_attachment[item["id"]] = entry
        by_name[item["filename"]] = entry
    # The rendered HTML is the only place that relates a media id to an attachment id.
    for tag in re.findall(r"<[^>]*data-media-services-id=[^>]*>", json.dumps(issue.get("renderedFields"))):
        tag = tag.replace('\\"', '"')
        media = re.search(r'data-media-services-id="([^"]+)"', tag)
        attachment = re.search(r"/attachment/(?:content|thumbnail)/(\d+)", tag)
        if media and attachment and attachment.group(1) in by_attachment:
            by_id[media.group(1)] = by_attachment[attachment.group(1)]
    # Some rendered images carry no media id. Pair those by position within the same text.
    fields, rendered = issue["fields"], issue.get("renderedFields") or {}
    texts = [(fields.get("description"), rendered.get("description"))]
    rendered_comments = (rendered.get("comment") or {}).get("comments") or []
    for index, comment in enumerate((fields.get("comment") or {}).get("comments") or []):
        if index < len(rendered_comments):
            texts.append((comment.get("body"), rendered_comments[index].get("body")))
    for document, markup in texts:
        media_ids = list(media_ids_in(document))
        found = re.findall(r"/attachment/(?:content|thumbnail)/(\d+)", markup or "")
        attachment_ids = [a for i, a in enumerate(found) if i == 0 or found[i - 1] != a]
        if len(media_ids) == len(attachment_ids):
            for media_id, attachment_id in zip(media_ids, attachment_ids):
                if attachment_id in by_attachment:
                    by_id.setdefault(media_id, by_attachment[attachment_id])
    return by_id, by_name


def media_ids_in(node):
    """Yield the ids of file media nodes in an ADF document, in document order."""
    if isinstance(node, dict):
        if node.get("type") in ("media", "mediaInline") and node.get("attrs", {}).get("type") == "file":
            yield node["attrs"].get("id")
        for child in node.get("content") or []:
            yield from media_ids_in(child)


def jira_link(href):
    """Point links to issues in this Jira project at the archive."""
    match = re.match(r"%s/browse/(%s-\d+)(?:\?.*?focusedCommentId=(\d+))?"
                     % (re.escape(CONFIG["jira_base"]), CONFIG["project"]), href or "")
    if not match:
        return href
    return archive_url(match.group(1)) + ("#comment-" + match.group(2) if match.group(2) else "")


def user_text(name):
    login = CONFIG["users"].get(name)
    if login:
        return "[%s](https://github.com/%s)" % (adf.escape(name), login)
    return adf.escape(name) if name else ""


def truncate(text, key):
    if len(text) <= BODY_LIMIT:
        return text
    notice = "\n\n*Truncated. Full text: [%s](%s)*" % (key, archive_url(key))
    cut = text[:BODY_LIMIT - len(notice)]
    if cut.count("```") % 2:
        cut += "\n```"
    return cut + notice


def convert_issue(issue):
    key, fields = issue["key"], issue["fields"]
    by_id, by_name = media_lookup(issue)
    ctx = adf.Context(media=by_id, names=by_name, users=CONFIG["users"], link=jira_link,
                      ref=lambda other: "{{jira:%s}}" % other)
    issue_type = fields["issuetype"]["name"]

    labels = list(CONFIG["always_labels"]) + CONFIG["type_labels"].get(issue_type, [])
    repo_labels = [CONFIG["components"][c] for c in names(fields.get("components")) if c in CONFIG["components"]]
    labels += repo_labels or [CONFIG["untriaged_label"]]
    labels += [CONFIG["labels"][l] for l in fields.get("labels") or [] if l in CONFIG["labels"]]

    milestone = None
    for version in names(fields.get("fixVersions")):
        match = re.search(r"(\d+\.\d+\.\d+)$", version)
        if match and match.group(1) in CONFIG["milestones"]:
            milestone = match.group(1)

    rows = [
        ("Reporter", user_text(person(fields.get("reporter")))),
        ("Created", show_date(fields.get("created"))),
        ("Assignee", user_text(person(fields.get("assignee")))),
        ("Type", issue_type),
        ("Status", fields["status"]["name"]),
        ("Priority", (fields.get("priority") or {}).get("name", "")),
        ("Components", adf.escape(", ".join(names(fields.get("components"))))),
        ("Affects versions", adf.escape(", ".join(names(fields.get("versions"))))),
        ("Fix versions", adf.escape(", ".join(names(fields.get("fixVersions"))))),
        ("Jira labels", adf.escape(", ".join(fields.get("labels") or []))),
    ]
    if fields.get("parent"):
        rows.append(("Parent", "{{jira:%s}}" % fields["parent"]["key"]))

    body = ["*Migrated from Jira: [%s](%s)*" % (key, archive_url(key)), "",
            "| | |", "|---|---|"]
    body += ["| %s | %s |" % row for row in rows if row[1]]
    body += ["", "---", ""]
    if fields.get("environment"):
        body += ["**Environment**", "", adf.to_markdown(fields["environment"], ctx), ""]
    body.append(adf.to_markdown(fields.get("description"), ctx) or "*No description.*")

    attachments = fields.get("attachment") or []
    if attachments:
        body += ["", "### Attachments", ""]
        body += ["- [%s](%s) (%s bytes)" % (adf.escape(a["filename"]), by_name[a["filename"]]["url"], a.get("size", "?"))
                 for a in attachments]
    links = list(issue_links(fields))
    if links:
        body += ["", "### Linked issues", ""]
        body += ["- %s {{jira:%s}}: %s" % (text, other["key"], adf.escape(other.get("fields", {}).get("summary", "")))
                 for text, other in links]

    comments = []
    for comment in (fields.get("comment") or {}).get("comments") or []:
        header = "**%s** commented in Jira on %s" % (
            user_text(person(comment.get("author"))) or "Unknown user", show_date(comment.get("created"), True))
        comments.append(truncate(header + "\n\n" + adf.to_markdown(comment.get("body"), ctx), key))

    assignee = CONFIG["users"].get(person(fields.get("assignee")))
    return {
        "key": key,
        "title": "[%s] %s" % (key, (fields.get("summary") or "").strip()),
        "body": truncate("\n".join(body), key),
        "type": CONFIG["types"].get(issue_type, "Task"),
        "labels": sorted(set(labels)),
        "milestone": milestone,
        "assignees": [assignee] if assignee else [],
        "parent": (fields.get("parent") or {}).get("key"),
        "comments": comments,
    }


def cmd_convert(args):
    target = OUT / "github"
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*"):
        stale.unlink()
    count = 0
    for issue in load_issues():
        if not in_scope(issue):
            continue
        payload = convert_issue(issue)
        (target / (payload["key"] + ".json")).write_text(json.dumps(payload, indent=1, ensure_ascii=False))
        preview = ["# " + payload["title"], "",
                   "type: %s | labels: %s | milestone: %s | assignees: %s" % (
                       payload["type"], ", ".join(payload["labels"]), payload["milestone"],
                       ", ".join(payload["assignees"])),
                   "", payload["body"]]
        for comment in payload["comments"]:
            preview += ["", "---", "", comment]
        (target / (payload["key"] + ".md")).write_text("\n".join(preview) + "\n")
        count += 1
    log("Converted %d issues to %s" % (count, target))


# --------------------------------------------------------------- GitHub import

class GitHub:
    def __init__(self, repo, delay):
        self.repo, self.delay = repo, delay

    def call(self, method, path, payload=None, write=True):
        command = ["gh", "api", "-X", method, path, "-H", "X-GitHub-Api-Version: 2022-11-28"]
        if payload is not None:
            command += ["--input", "-"]
        for attempt in range(6):
            result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                                    capture_output=True, text=True)
            if result.returncode == 0:
                if write:
                    time.sleep(self.delay)
                return json.loads(result.stdout) if result.stdout.strip() else None
            message = result.stdout + result.stderr
            if "rate limit" in message.lower() or "abuse" in message.lower():
                wait = 60 * (attempt + 1)
                log("  rate limited, waiting %ds" % wait)
                time.sleep(wait)
                continue
            raise RuntimeError("%s %s failed: %s" % (method, path, message.strip()))
        raise RuntimeError("%s %s failed after retries" % (method, path))

    def repo_call(self, method, path, payload=None, write=True):
        return self.call(method, "repos/%s/%s" % (self.repo, path), payload, write)


def resolve(text, numbers):
    """Replace {{jira:KEY}} with #N for migrated issues and an archive link for the rest."""
    def replace(match):
        key = match.group(1)
        if key in numbers:
            return "#%d" % numbers[key]
        return "[%s](%s)" % (key, archive_url(key))
    return PLACEHOLDER.sub(replace, text)


def label_color(name):
    for prefix, color in CONFIG["label_colors"].items():
        if name == prefix or (prefix.endswith(":") and name.startswith(prefix)):
            return color
    return "ededed"


def cmd_import(args):
    if args.repo == CONFIG["tracker"] and not args.production:
        sys.exit("Refusing to import into %s without --production." % args.repo)
    payloads = sorted((json.loads(p.read_text()) for p in (OUT / "github").glob("*.json")),
                      key=lambda p: key_number(p["key"]))
    if args.only:
        payloads = [p for p in payloads if p["key"] in args.only.split(",")]
    if args.limit:
        payloads = payloads[:args.limit]
    if not payloads:
        sys.exit("Nothing to import. Run 'convert' first.")

    state_file = OUT / ("import-%s.json" % args.repo.replace("/", "-"))
    state = {"issues": {}, "comments": {}, "patched": [], "sub_issues": []}
    if state_file.exists():
        state.update(json.loads(state_file.read_text()))

    def save():
        state_file.write_text(json.dumps(state, indent=1))

    github = GitHub(args.repo, args.delay)
    owner = args.repo.split("/")[0]

    existing = {l["name"].lower() for l in github.call(
        "GET", "repos/%s/labels?per_page=100" % args.repo, write=False)}
    for label in sorted({l for p in payloads for l in p["labels"]}):
        if label.lower() not in existing:
            github.repo_call("POST", "labels", {"name": label, "color": label_color(label)})
            log("created label " + label)

    milestones = {m["title"]: m["number"] for m in github.call(
        "GET", "repos/%s/milestones?state=all&per_page=100" % args.repo, write=False)}
    for title in sorted({p["milestone"] for p in payloads if p["milestone"]}):
        if title not in milestones:
            milestones[title] = github.repo_call("POST", "milestones", {"title": title})["number"]
            log("created milestone " + title)

    try:
        types = {t["name"] for t in github.call("GET", "orgs/%s/issue-types" % owner, write=False)}
    except RuntimeError:
        types = set()
        log("No issue types for %s; using type: labels instead." % owner)

    def numbers():
        return {k: v["number"] for k, v in state["issues"].items()}

    # Pass 1: create the issues. References to issues not yet created become archive links.
    for payload in payloads:
        key = payload["key"]
        if key in state["issues"]:
            continue
        request = {"title": payload["title"], "body": resolve(payload["body"], numbers()),
                   "labels": list(payload["labels"])}
        if payload["type"] in types:
            request["type"] = payload["type"]
        else:
            label = "type:" + payload["type"].lower()
            if label.lower() not in existing:
                github.repo_call("POST", "labels", {"name": label, "color": "ededed"})
                existing.add(label.lower())
            request["labels"].append(label)
        if payload["milestone"]:
            request["milestone"] = milestones[payload["milestone"]]
        if args.assign and payload["assignees"]:
            request["assignees"] = payload["assignees"]
        created = github.repo_call("POST", "issues", request)
        state["issues"][key] = {"number": created["number"], "id": created["id"]}
        save()
        log("%s -> %s#%d" % (key, args.repo, created["number"]))

    # Pass 2: rewrite references now that every issue has a number, then add comments.
    final = numbers()
    for payload in payloads:
        key = payload["key"]
        number = state["issues"][key]["number"]
        referenced = set(PLACEHOLDER.findall(payload["body"]))
        if referenced & set(final) and key not in state["patched"]:
            github.repo_call("PATCH", "issues/%d" % number, {"body": resolve(payload["body"], final)})
            state["patched"].append(key)
            save()
        done = state["comments"].get(key, 0)
        for index, comment in enumerate(payload["comments"]):
            if index < done:
                continue
            github.repo_call("POST", "issues/%d/comments" % number, {"body": resolve(comment, final)})
            state["comments"][key] = index + 1
            save()
        parent = payload.get("parent")
        if parent in state["issues"] and key not in state["sub_issues"]:
            try:
                github.repo_call("POST", "issues/%d/sub_issues" % state["issues"][parent]["number"],
                                 {"sub_issue_id": state["issues"][key]["id"]})
                state["sub_issues"].append(key)
                save()
            except RuntimeError as error:
                log("WARNING: could not link %s as sub-issue of %s: %s" % (key, parent, error))
        log("%s complete (%d comments)" % (key, len(payload["comments"])))
    log("Imported %d issues into %s. State: %s" % (len(payloads), args.repo, state_file))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="download issues and attachments from Jira")
    export.add_argument("--jql", help="JQL to export (default: the whole project)")
    export.add_argument("--no-attachments", action="store_true")
    export.set_defaults(run=cmd_export)

    archive = commands.add_parser("archive", help="generate the static HTML archive")
    archive.add_argument("--mapping", help="import state file; adds links to the migrated GitHub issues")
    archive.set_defaults(run=cmd_archive)

    convert = commands.add_parser("convert", help="generate GitHub issue payloads in out/github")
    convert.set_defaults(run=cmd_convert)

    importer = commands.add_parser("import", help="create the converted issues on GitHub")
    importer.add_argument("--repo", required=True, help="owner/name")
    importer.add_argument("--production", action="store_true",
                          help="required to import into the tracker named in config.json")
    importer.add_argument("--assign", action="store_true",
                          help="assign mapped users (sends them notifications)")
    importer.add_argument("--only", help="comma-separated Jira keys")
    importer.add_argument("--limit", type=int, help="import only the first N issues")
    importer.add_argument("--delay", type=float, default=1.0, help="seconds between writes")
    importer.set_defaults(run=cmd_import)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
