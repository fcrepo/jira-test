# Cutover checklist

Steps that change shared GitHub or Jira state. Run them in this order on the cutover day.

## 1. Freeze Jira

- In Jira project settings, change the permission scheme so only administrators can create and edit
  issues and comments.
- Add an announcement banner: "This tracker is read-only. New issues: https://github.com/fcrepo/fcrepo/issues".

## 2. Final export, archive, import

```bash
export JIRA_EMAIL=... JIRA_TOKEN=...      # include restricted issues
python3 tools/migrate.py export
python3 tools/migrate.py convert
python3 tools/migrate.py import --repo fcrepo/fcrepo --production --assign
python3 tools/migrate.py archive --mapping out/import-fcrepo-fcrepo.json
```

Review `out/github/*.md` between `convert` and `import`.

## 3. Publish the archive

```bash
git add -A && git commit -m "Jira archive export <date>"
git push origin main
gh api -X POST repos/fcrepo/jira/pages -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/'
```

The site appears at https://fedora.info/jira/ because the `fcrepo` organisation site uses that domain.

## 4. Autolinks

Turns `FCREPO-1234` in commits, issues and pull requests into links to the archive.

```bash
for repo in fcrepo/fcrepo fcrepo/fcrepo-storage-ocfl fcrepo/fcrepo-build-tools \
    fcrepo-exts/fcrepo-import-export fcrepo-exts/fcrepo-camel-toolbox fcrepo-exts/fcrepo-camel \
    fcrepo-exts/migration-utils fcrepo-exts/fcrepo-upgrade-utils fcrepo-exts/fcrepo-migration-validator \
    fcrepo-exts/fcrepo-java-client fcrepo-exts/fcrepo-docker fcrepo-exts/fcrepo-aws-deployer; do
  gh api -X POST "repos/$repo/autolinks" -f key_prefix=FCREPO- \
    -f url_template='https://fedora.info/jira/FCREPO-<num>' -F is_alphanumeric=false
done
```

## 5. Redirect other repositories to fcrepo/fcrepo

Create `fcrepo-exts/.github` and `fcrepo4/.github` with `.github/ISSUE_TEMPLATE/config.yml`:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Report an issue
    url: https://github.com/fcrepo/fcrepo/issues/new/choose
    about: Issues for all Fedora repositories are tracked in fcrepo/fcrepo.
```

Repositories with their own issue templates override this; remove those templates.
Existing issues in those repositories stay readable.

## 6. Move open issues from fcrepo-exts

`gh issue transfer` does not work across organisations. For each open issue in fcrepo-exts
(12 at the time of writing), create an issue in fcrepo/fcrepo that links to the original, then close
the original with a comment pointing at the new one.

## 7. Enable private vulnerability reporting

```bash
gh api -X PUT repos/fcrepo/fcrepo/private-vulnerability-reporting
```

## 8. Merge the fcrepo branch

Issue forms, `SECURITY.md`, the PR template and the replaced Jira links.
Update the PR template in the other repositories the same way.

## 9. Back-links from Jira

Comment on each migrated Jira issue with its GitHub URL. The import state file maps keys to numbers:

```bash
jq -r '.issues | to_entries[] | "\(.key) https://github.com/fcrepo/fcrepo/issues/\(.value.number)"' \
  out/import-fcrepo-fcrepo.json
```

Jira's REST API accepts comments on behalf of the token owner (`POST /rest/api/3/issue/{key}/comment`).
