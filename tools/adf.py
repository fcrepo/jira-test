"""Convert Atlassian Document Format (ADF) JSON to GitHub-flavoured Markdown."""

import html
import re

ZWSP = "​"

_URL = re.compile(r"(https?://[^\s<>]+)")
_SPECIAL = re.compile(r"([\\`*_\[\]<>~|])")
_LINE_START = re.compile(r"^(\s*)(#{1,6}(?=\s)|[-+](?=\s)|\d+(?=[.)]\s))", re.M)
_BROWSE = re.compile(r"/browse/([A-Z][A-Z0-9]+-\d+)")

PANELS = {"info": "NOTE", "note": "IMPORTANT", "success": "TIP",
          "warning": "WARNING", "error": "CAUTION"}


class Context:
    """Lookups needed while converting one issue.

    media: Jira media id -> {"url", "name", "image"}
    users: Jira display name -> GitHub login
    ref:   function(issue key) -> markdown for a reference to that issue
    link:  function(href) -> href to use in the converted text
    """

    def __init__(self, media=None, users=None, ref=None, names=None, link=None):
        self.link = link or (lambda href: href)
        self.media = media or {}
        self.names = names or {}
        self.users = users or {}
        self.ref = ref or (lambda key: key)


def escape(text):
    """Escape markdown syntax in plain text. URLs are left unchanged."""
    out = []
    for i, part in enumerate(_URL.split(text)):
        if i % 2:
            out.append(part)
            continue
        part = _SPECIAL.sub(r"\\\1", part)
        # Stop GitHub from turning Jira text into user mentions or issue references.
        part = re.sub(r"@(?=\w)", "@" + ZWSP, part)
        part = re.sub(r"(?<!\w)#(?=\d)", "#" + ZWSP, part)
        out.append(part)
    return "".join(out)


def _wrap(text, marker, close=None):
    """Apply an inline marker, keeping leading and trailing whitespace outside it."""
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return lead + marker + stripped + (close or marker) + trail


def _code_span(text):
    ticks = "`"
    while ticks in text:
        ticks += "`"
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return ticks + pad + text + pad + ticks


def _text(node, ctx):
    text = node.get("text", "")
    marks = {m["type"]: m.get("attrs", {}) for m in node.get("marks", [])}
    if "code" in marks:
        out = _code_span(text)
    else:
        out = escape(text)
        if "strong" in marks:
            out = _wrap(out, "**")
        if "em" in marks:
            out = _wrap(out, "*")
        if "strike" in marks:
            out = _wrap(out, "~~")
        if "subsup" in marks:
            tag = "sub" if marks["subsup"].get("type") == "sub" else "sup"
            out = _wrap(out, "<%s>" % tag, "</%s>" % tag)
    if "link" in marks:
        href = ctx.link(marks["link"].get("href", ""))
        if href and href != text:
            out = _wrap(out, "[", "](%s)" % href.replace(" ", "%20").replace(")", "%29"))
        elif href:
            out = href
    return out


def _media(node, ctx):
    attrs = node.get("attrs", {})
    if attrs.get("type") in ("external", "link"):
        url = attrs.get("url", "")
        return "![](%s)" % url if attrs.get("type") == "external" else "<%s>" % url
    item = ctx.media.get(attrs.get("id")) or ctx.names.get(attrs.get("alt") or "")
    if not item:
        return "*(attachment %s not found in the Jira export)*" % escape(attrs.get("alt") or "")
    label = escape(item["name"])
    if item["image"] and node["type"] != "mediaInline":
        return "![%s](%s)" % (label, item["url"])
    return "[%s](%s)" % (label, item["url"])


def _card(node, ctx):
    url = node.get("attrs", {}).get("url", "")
    match = _BROWSE.search(url)
    if match:
        return ctx.ref(match.group(1))
    return "<%s>" % url if url else ""


def inline(nodes, ctx):
    out = []
    for node in nodes or []:
        kind = node.get("type")
        attrs = node.get("attrs", {})
        if kind == "text":
            out.append(_text(node, ctx))
        elif kind == "hardBreak":
            out.append("  \n")
        elif kind == "mention":
            name = (attrs.get("text") or "").lstrip("@") or "unknown user"
            login = ctx.users.get(name)
            out.append("[%s](https://github.com/%s)" % (escape(name), login) if login else escape(name))
        elif kind == "emoji":
            out.append(attrs.get("text") or attrs.get("shortName", ""))
        elif kind in ("inlineCard", "blockCard", "embedCard"):
            out.append(_card(node, ctx))
        elif kind in ("media", "mediaInline"):
            out.append(_media(node, ctx))
        elif kind == "date":
            out.append(_date(attrs.get("timestamp")))
        elif kind == "status":
            out.append(_code_span(attrs.get("text", "")))
        elif kind == "placeholder":
            continue
        else:
            out.append(inline(node.get("content"), ctx))
    return "".join(out)


def _date(timestamp):
    import datetime
    try:
        stamp = datetime.datetime.fromtimestamp(int(timestamp) / 1000, datetime.timezone.utc)
        return stamp.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _fence(text, language=""):
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return "%s%s\n%s\n%s" % (ticks, language or "", text, ticks)


def _indent(text, width):
    pad = " " * width
    lines = text.split("\n")
    return "\n".join([lines[0]] + [pad + line if line else line for line in lines[1:]])


def _list(node, ctx, ordered):
    out = []
    number = node.get("attrs", {}).get("order", 1) if ordered else None
    for item in node.get("content", []):
        if item.get("type") == "taskItem":
            done = item.get("attrs", {}).get("state") == "DONE"
            marker = "- [%s] " % ("x" if done else " ")
            body = inline(item.get("content"), ctx)
        else:
            marker = "%d. " % number if ordered else "- "
            body = blocks(item.get("content"), ctx, tight=True)
        if ordered:
            number += 1
        out.append(marker + _indent(body, 2 if marker.startswith("-") else len(marker)))
    return "\n".join(out)


def _cell(node, ctx):
    parts = []
    for child in node.get("content", []):
        if child.get("type") == "codeBlock":
            code = html.escape(_plain(child)).replace("\n", "<br>")
            parts.append("<pre>%s</pre>" % code)
        else:
            parts.append(block(child, ctx))
    text = "<br>".join(p for p in parts if p)
    return re.sub(r" *\n+", "<br>", text).replace("|", "\\|").replace("\\\\|", "\\|")


def _table(node, ctx):
    rows = [[_cell(c, ctx) for c in row.get("content", [])] for row in node.get("content", [])]
    rows = [r for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    first = node["content"][0].get("content", [])
    if first and all(c.get("type") == "tableHeader" for c in first):
        header, rows = rows[0], rows[1:]
    else:
        header = [""] * width
    lines = [header, ["---"] * width] + rows
    return "\n".join("| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in lines)


def _plain(node):
    if node.get("type") == "text":
        return node.get("text", "")
    if node.get("type") == "hardBreak":
        return "\n"
    return "".join(_plain(c) for c in node.get("content", []))


def _quote(text, prefix="> "):
    return "\n".join((prefix + line).rstrip() for line in text.split("\n"))


def block(node, ctx):
    kind = node.get("type")
    attrs = node.get("attrs", {})
    content = node.get("content", [])
    if kind == "paragraph":
        return _LINE_START.sub(r"\1\\\2", inline(content, ctx)).strip()
    if kind == "heading":
        return "#" * min(int(attrs.get("level", 1)) + 2, 6) + " " + inline(content, ctx).strip()
    if kind == "codeBlock":
        return _fence(_plain(node), attrs.get("language"))
    if kind == "bulletList":
        return _list(node, ctx, ordered=False)
    if kind == "orderedList":
        return _list(node, ctx, ordered=True)
    if kind == "taskList":
        return _list(node, ctx, ordered=False)
    if kind == "blockquote":
        return _quote(blocks(content, ctx))
    if kind == "panel":
        return "> [!%s]\n%s" % (PANELS.get(attrs.get("panelType"), "NOTE"), _quote(blocks(content, ctx)))
    if kind == "rule":
        return "---"
    if kind == "table":
        return _table(node, ctx)
    if kind in ("mediaSingle", "mediaGroup"):
        return "\n".join(_media(c, ctx) for c in content if c.get("type") == "media")
    if kind in ("expand", "nestedExpand"):
        title = html.escape(attrs.get("title") or "Details")
        return "<details><summary>%s</summary>\n\n%s\n\n</details>" % (title, blocks(content, ctx))
    if kind in ("decisionList", "decisionItem", "layoutSection", "layoutColumn", "doc"):
        return blocks(content, ctx)
    if content and all(c.get("type") in ("paragraph", "codeBlock", "bulletList", "orderedList") for c in content):
        return blocks(content, ctx)
    return inline([node], ctx).strip()


def blocks(nodes, ctx, tight=False):
    rendered = [block(n, ctx) for n in nodes or []]
    rendered = [r for r in rendered if r and r.strip()]
    if tight and all(n.get("type") in ("paragraph", "bulletList", "orderedList") for n in nodes or []):
        return "\n".join(rendered)
    return "\n\n".join(rendered)


def to_markdown(doc, ctx=None):
    """Convert an ADF document (dict) to markdown. Returns '' for an empty document."""
    if not doc:
        return ""
    if isinstance(doc, str):
        return escape(doc)
    return blocks(doc.get("content"), ctx or Context()).strip()
