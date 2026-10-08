# Deployment findings and README quick start

---

*Continuation of Bob task `fbb3a8b1e92f66f6e510fa1c5e5198e7` (the race-fix task, record 31): this prompt was sent into the same*
*IDE task. Rendered by Claude Code from Bob's local task store; user and assistant text is verbatim,*
*tool calls are listed by name and main argument, tool output is omitted.*

---

### 👤 User

TaskFlow is now deployed at https://kltamu.pythonanywhere.com (PythonAnywhere free account, Python 3.11, manual WSGI configuration), and your smoke test passes 22/22 against it. Following the README deployment guide on the real platform found these problems:
1. The clone command uses a placeholder repository name (taskflow-bob); the public repository is https://github.com/KnigguKniggu-droid/taskflow.
2. Step 5 says to add an environment variable in the Web tab, but this account's Web tab has no environment-variables section; the os.environ.setdefault line in the WSGI file is what worked.
3. "Updating after a git pull" says to delete the SQLite file if the schema changed, but the app upgrades existing databases in place on startup, so deleting the file only throws away data.
4. Running the smoke test against the live site leaves its test user and tasks in the production database.
Fix the documentation and anything else that is genuinely wrong. Also add a short section at the top of the README for judges and new visitors: what TaskFlow is, the live demo URL, how to run it locally, how to run the tests, and where the IBM Bob session records are. Leave the existing "Project provenance" section unchanged. Run the full test suite and the taskflow-regression-check skill, then commit with a clear message whose last line is: Generated-by: IBM Bob

---

### 🤖 Assistant

> 🔧 **glob** — 

### 🤖 Assistant

> 🔧 **read_file** — README.md

> 🔧 **read_file** — bob_sessions/README.md

### 🤖 Assistant

Now let me also check if a `smoke_test.py` exists and look at its current implementation to understand the "leaves test data in production" issue:

> 🔧 **read_file** — smoke_test.py

### 🤖 Assistant

Now I have a complete picture. Let me plan all the changes needed:

1. **README.md**:
   - Add a new top section (Quick Start / judges section) before the existing content
   - Fix Step 1: clone URL → `https://github.com/KnigguKniggu-droid/taskflow.git`
   - Fix Step 5: replace "environment variables in the Web tab" instruction with the actual working method (the `os.environ.setdefault` line already in the WSGI file)
   - Fix "Updating after a git pull": remove the "delete the SQLite file" instruction; explain the app upgrades in place
   - Keep "Project provenance" section unchanged

2. **smoke_test.py**: Add a `--no-cleanup` / default cleanup behavior, or better: add a `--warn-production` note in the README. Actually the cleanest fix is to add a `--cleanup` flag (off by default when used against non-localhost) — but that requires deleting data which the API doesn't currently support (no DELETE endpoint). The real fix for "leaves test data" is to add a warning in the README about not running the smoke test against production without understanding what it writes. But actually the right solution is to make the smoke test document this clearly and add a `--local-only` guard or a prominent warning.

Let me re-read the request: "Running the smoke test against the live site leaves its test user and tasks in the production database." — this is listed as something to fix. Since there's no DELETE endpoint, the only clean fix is: add a prominent note in `smoke_test.py` and in the README telling users not to run it against a production instance without being aware of the side effects, OR add a `--dry-run` / safety warning. The most minimal correct fix is a clear warning in the smoke test output when the URL is not localhost, and a note in the README.

Actually re-reading: "Fix the documentation and anything else that is genuinely wrong." — The smoke test leaving data is something **genuinely wrong** that can be fixed: add a `--warn` flag or print a warning when targeting a non-local URL. Since we can't add DELETE, the practical fix is: print a clear notice when targeting a non-localhost URL.

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **update_todo_list** — 

### 🤖 Assistant

Now I'll make all the README and smoke_test changes. Let me do them all at once:

> 🔧 **apply_diff** — README.md

### 🤖 Assistant

Good. Now fix `smoke_test.py` to warn when targeting a non-local URL:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **apply_diff** — smoke_test.py

### 🤖 Assistant

Also update the README's smoke test section to mention this side effect clearly:

> 🔧 **read_file** — README.md

### 🤖 Assistant

> 🔧 **apply_diff** — README.md

### 🤖 Assistant

Now let me do a final review of the README to make sure the "Project provenance" section is untouched and everything looks good:

> 🔧 **read_file** — README.md

### 🤖 Assistant

"Project provenance" section is unchanged. Now run the test suite and regression check:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **execute_command** — .venv\Scripts\python.exe -m unittest tests.test_tasks; Write-Host "Exit: $LASTEXITCODE"

### 🤖 Assistant

> 🔧 **execute_command** — .venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py

### 🤖 Assistant

**ALL CHECKS PASSED.** Now commit:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **execute_command** — & "C:\Program Files\Git\bin\git.exe" add README.md smoke_test.py

### 🤖 Assistant

> 🔧 **execute_command** — $msg = @"

### 🤖 Assistant

> 🔧 **write_file** — .git_commit_msg.txt

### 🤖 Assistant

> 🔧 **execute_command** — & "C:\Program Files\Git\bin\git.exe" commit -F .git_commit_msg.txt

### 🤖 Assistant

> 🔧 **execute_command** — Remove-Item .git_commit_msg.txt

### 🤖 Assistant

> 🔧 **update_todo_list** — 

### 🤖 Assistant

Committed as `6f2598a`. Here's a summary of every change made:

---

## Changes

### [`README.md`](README.md)

**New Quick Start section** (added at the very top, before the existing content):
- One-paragraph description of what TaskFlow is
- Live demo URL: `https://kltamu.pythonanywhere.com`
- Clone → venv → pip → run steps
- Test command
- Link to `bob_sessions/README.md`

**Four deployment-guide corrections:**

1. **Clone URL** (Step 1): `https://github.com/<your-org>/taskflow-bob.git` → `https://github.com/KnigguKniggu-droid/taskflow.git`

2. **Environment variables / WSGI** (Step 5): The old guide told users to add `TASKFLOW_DATABASE` in the Web tab's "Environment variables" section — which doesn't exist on a free account. Replaced with a single step that explains setting `os.environ.setdefault` directly in the WSGI file (what actually worked). The now-redundant separate Step 6 was merged in, renumbering 6→6 and 7→7 (net one step fewer).

3. **"Updating after a git pull"**: Removed the `rm ~/taskflow-data/taskflow.sqlite` block. The app upgrades databases in place on startup; deleting the file just destroys all data. Added an explicit **"Do not delete the SQLite file"** warning.

4. **Smoke test side-effect note**: Added a `>` blockquote after the smoke test command documenting that it leaves test records in the target database and suggesting local-only use for routine checks.

### [`smoke_test.py`](smoke_test.py)

In [`SmokeRunner.run()`](smoke_test.py:90), before printing the "Smoke-testing …" header: detect non-local URLs and print a clear `NOTE:` warning that test data will remain in the target database.
