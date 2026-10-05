# Stage 10 - documentation

- Bob task (ACP session) id: `72776e99c6aefa41cf6e9d26c43952dc`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:24:15+00:00 - duration 148.8 s - stop reason: end_turn
- Tool calls: 35; permission requests: 23 (denied: 2)

## Prompt (written by the Claude Code orchestrator)

```text
Now update the documentation to match the code as it is now: README.md (the API table and query parameters including tag filtering, its exact-match semantics, case normalization, and the behavior for blank and invalid tag values; examples for a tag filter and a combined assignee_id + tag filter; the feature status section; testing instructions), AGENTS.md (the stale items your documentation review found: feature status, API table, conventions), and a new CHANGELOG.md entry summarizing the overdue fix, the existing-database fix, the tag filter, the new tests, and the Bob project tooling under .bob/. Also add .bob/tmp/ to .gitignore. Don't describe anything that isn't implemented. Run the full suite once more, then commit only these documentation changes with a clear message whose last line is: Generated-by: IBM Bob
```

## Tool calls by Bob

- `read` Finding files in <repo> with pattern "*.md" - completed
- `read` Reading file <repo> - completed
- `read` Reading file <repo>\AGENTS.md - completed
- `read` Reading file <repo>\.gitignore - completed
- `read` Reading file <repo>\README.md - completed
- `read` Reading file <repo>\app\services.py (80, 115) - completed
- `read` Reading file <repo>\app\services.py (190, 215) - completed
- `read` Reading file <repo>\app\services.py (1, 30) - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" log --oneline pre-bob-baseline..HEAD - completed
- `read` Reading file <repo>\.bob\commands\verify-taskflow.md - completed
- `read` Reading file <repo>\.bob - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" log --oneline --format="%h %s" pre-bob-baseline..HEAD - completed
- `read` Finding files in <repo>\.bob with pattern "**/*" - completed
- `read` Reading file <repo>\.bob\custom_modes.yaml - completed
- `other` Updating todo list - failed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\README.md - completed
- `other` Updating todo list - completed
- `edit` Applying diff to <repo>\AGENTS.md - completed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\CHANGELOG.md - completed
- `other` Updating todo list - completed
- `edit` Applying diff to <repo>\.gitignore - failed
- `execute` Add-Content -Path ".gitignore" -Value "`n# Bob scratch files (generated during sessions; not project artefacts)`n.bob/tmp/" - completed
- `execute` Get-Content ".gitignore" | Select-Object -Last 6 - completed
- `other` Updating todo list - completed
- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks 2>&1 | Select-String "Ran|OK|FAIL|ERROR" - failed
- `execute` .venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py 2>&1 | Select-String "passed|failed|PASS|FAIL|REGRESSION|ALL CHECKS" - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" add README.md AGENTS.md CHANGELOG.md .gitignore - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" status --short - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" commit -m "docs: update README, AGENTS.md, add CHANGELOG and .gitignore entry

README.md
- API table: add ?tag=<tag> to GET - failed
- `execute` $msg = @'
docs: update README, AGENTS.md, add CHANGELOG and .gitignore entry

README.md
- API table: add ?tag=<tag> to GET /tasks description
- Add Filtering ta - failed
- `edit` Writing file <repo>\.bob\tmp\commit_msg.txt - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" commit -F ".bob\tmp\commit_msg.txt" - completed
- `other` Updating todo list - completed

## Bob's answer (verbatim)

Let me read all the relevant files before writing anything.Now read the current services.py and tests to confirm exact current behaviour before writing docs:Also check the git log for good CHANGELOG context:I now have everything I need. Let me build all the documentation changes:Now update the three stale spots in AGENTS.md:Now create CHANGELOG.md:Now add `.bob/tmp/` to `.gitignore`:Good. Now run the full suite:26/26 unit tests · 23/23 smoke checks — all green. Now commit:Commit `ede8b08`. Here is a summary of every change made.

---

### What changed

**[`README.md`](README.md)**

| Section | Change |
|---|---|
| API table `GET /tasks` | Now shows `?assignee_id=<id>` **and/or** `?tag=<tag>` |
| New § **Filtering tasks** | Documents the two query params in a table; calls out exact-match semantics, case normalisation, blank→no-filter, invalid→400, and combined usage |
| Examples | Added `?tag=backend`, `?tag=backend&assignee_id=1` curl examples; updated PowerShell examples |
| Testing § | Extended to describe the full scope of the suite (tag filtering, schema migration, upgrade behaviour) |
| ~~Feature status~~ | Removed the stale "planned but not implemented" stub — all features are now implemented |
| Project layout | Added `.bob/` line |

**[`AGENTS.md`](AGENTS.md)**

| Location | Change |
|---|---|
| API table `GET /tasks` | Added `?tag=<tag>` to the description |
| Coding Conventions | Added bullet for `parse_tag_param` alongside `parse_id_param` |
| Feature Status table | Changed tag filter row from **Planned, not yet implemented** → **Implemented** |

**[`CHANGELOG.md`](CHANGELOG.md)** *(new)*

Covers: overdue/NULL schema fix, existing-database INSERT fix, tag filter feature, all new test cases (`TagFilterTestCase`, `SchemaInitTestCase`, `OldSchemaRegressionTestCase`, `TaskApiTestCase` additions), and the Bob tooling added under `.bob/`.

**[`.gitignore`](.gitignore)**

Added `.bob/tmp/` so scratch files generated during Bob sessions are never committed.

**26/26 unit tests · 23/23 regression checks — ALL PASSED**
