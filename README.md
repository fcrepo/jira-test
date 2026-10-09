# Fedora Repository Jira archive

Read-only copy of the `FCREPO` project from https://fedora-repository.atlassian.net, published at
https://fedora.info/jira/. Issue tracking continues at https://github.com/fcrepo/fcrepo/issues.

| Path | Content |
|---|---|
| `FCREPO-<n>.html` | One page per issue. Also served as `https://fedora.info/jira/FCREPO-<n>` |
| `index.html` | List of all issues with a text filter |
| `data/FCREPO-<n>.json` | Issue as returned by the Jira REST API, including rendered HTML |
| `attachments/FCREPO-<n>/` | Attachments, named `<attachment id>_<file name>` |
| `tools/` | Scripts that produced the archive and the GitHub issues |

## Tools

Python 3.9+, no third-party packages. `import` needs an authenticated `gh` CLI.

```bash
python3 tools/migrate.py export
python3 tools/migrate.py archive
python3 tools/migrate.py convert
python3 tools/migrate.py import --repo fcrepo/jira-test
```

- `export` downloads every issue and attachment. It reads Jira anonymously. Set `JIRA_EMAIL` and
  `JIRA_TOKEN` to include issues that are not public. Existing attachments are not downloaded again.
- `archive` writes the HTML pages. `--mapping out/import-fcrepo-fcrepo.json` adds a link from each
  migrated issue to its GitHub issue.
- `convert` writes one GitHub issue payload (`.json`) and a preview (`.md`) per issue in scope to
  `out/github/`. In scope: status category not Done, created on or after `cutoff` in `config.json`.
- `import` creates the issues, then rewrites references between them and adds comments. Progress is
  saved in `out/import-<owner>-<repo>.json`; a rerun continues where it stopped. Importing into the
  tracker named in `config.json` requires `--production`. Users are assigned only with `--assign`.

Mappings of Jira users, issue types, components, labels and versions are in `tools/config.json`.
