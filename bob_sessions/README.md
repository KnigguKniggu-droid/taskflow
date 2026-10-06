# IBM Bob session transcripts

These files record the IBM Bob session that produced every commit after the `pre-bob-baseline` tag.

How they were produced:

- IBM Bob Shell 2.0.5 ran as an Agent Client Protocol server (`bob acp`) on this repository.
- Claude Code (Anthropic) operated the session at the participant's direction: it wrote each prompt,
  approved or denied each tool call by a fixed policy (edits only in implementation stages, nothing
  outside this repository), and ran independent checks between stages.
- IBM Bob did the engineering work: exploring the code, diagnosing the defect, writing the fixes, the tag
  filter, the tests, the project skills/command/mode, the reviews, and the documentation, and it made
  the commits (each ends with `Generated-by: IBM Bob`).
- Follow-up prompts (6b, 9c, 10b) pass on failures that the independent checks observed. They describe
  the failing behavior, not the fix.
- Prompts are verbatim. Bob's answers are verbatim apart from local paths, which are redacted to `<repo>` / `<home>`.

| # | Stage | Bob task id | Mode | Duration (s) |
|---|---|---|---|---|
| [01](01-S1-init.md) | Stage 1 - /init sent as a prompt (orientation) | `35c95d5c3a622e9af752f54d077ba755` | agent | 18.5 |
| [02](02-S1b-agents-md.md) | Stage 1b - project context file (AGENTS.md) | `35c95d5c3a622e9af752f54d077ba755` | agent | 41.8 |
| [03](03-S2-plan-explore.md) | Stage 2 - Plan mode: explore unfamiliar code | `870e1654850d5883fafca581610d91ef` | plan | 64.5 |
| [04](04-S3-diagnose.md) | Stage 3 - reproduce and diagnose (no edits) | `870e1654850d5883fafca581610d91ef` | agent | 21.4 |
| [05](05-S4-ask.md) | Stage 4 - Ask mode: semantics and repair options | `870e1654850d5883fafca581610d91ef` | ask | 33.3 |
| [06](06-S5-fix.md) | Stage 5 - Agent mode: root-cause repair + tests | `870e1654850d5883fafca581610d91ef` | agent | 74.6 |
| [07](07-S6-tag-feature.md) | Stage 6 - Agent mode: exact tag filter | `dbf247a01cb1111015f68ba571e74716` | agent | 99.0 |
| [08](08-S6b-tag-followup.md) | Stage 6b - follow-up on an observed tag false positive | `dbf247a01cb1111015f68ba571e74716` | agent | 36.9 |
| [09](09-S7-regression-quality.md) | Stage 7 - regression quality (mutation gaps) | `ab712a83d48af705675aa55cb3ed730d` | agent | 113.1 |
| [10](10-S8a-bob-tooling.md) | Stage 8a - Bob project skills, command and custom mode | `62a82ea9d1d74d2e08b35db7d26fdee1` | agent | 120.2 |
| [11](11-S8b-verify-command.md) | Stage 8b - running /verify-taskflow | `062b4235dc5d7b5f8327c5c0acd41468` | agent | 8.3 |
| [12](12-S9a-reviewer-mode.md) | Stage 9a - review in the custom TaskFlow Reviewer mode | `091565b2b3810fd6b97d932852274caa` | taskflow-reviewer | 81.6 |
| [13](13-S9b-subagent-review.md) | Stage 9b - parallel subagent review | `72776e99c6aefa41cf6e9d26c43952dc` | agent | 280.7 |
| [14](14-S9c-legacy-followup.md) | Stage 9c - follow-up on an observed existing-database failure | `72776e99c6aefa41cf6e9d26c43952dc` | agent | 116.7 |
| [15](15-S10-docs.md) | Stage 10 - documentation | `72776e99c6aefa41cf6e9d26c43952dc` | agent | 148.8 |
| [16](16-S10b-docs-followup.md) | Stage 10b - follow-up on a README contradiction | `72776e99c6aefa41cf6e9d26c43952dc` | agent | 43.1 |

## IBM Bob IDE session

A second session ran in IBM Bob IDE 2.2.1 on 2026-10-06 (UTC), on the same branch.

- Claude Code operated the IDE at the participant's direction through Windows UI automation
  (window screenshots, clicks and pasted text). It opened this repository, started the built-in
  review, chose the mode for each task and typed the prompts below. The participant had set Bob's
  permissions to auto-approve; for the approval prompts that still appeared, Claude Code read each
  pending request and approved it only if it stayed inside this repository and made no network
  call or push.
- The review was run against `origin/main` (the baseline) with `bob_sessions/**` excluded, so it
  covered Bob's own changes.
- The files were exported with Bob's own "Export Current Task" command; local paths are redacted.
- "Bob cost" is the per-task figure the IDE shows next to each task.
- The two IBM i mode answers are explorations of a possible port and integration. Nothing in them
  was applied or verified, and they may contain mistakes.

| # | IDE task | Bob task id | Mode | Bob cost | Commit |
|---|---|---|---|---|---|
| [17](17-ide-review.md) | Built-in `/review` (Review Code Changes workflow, findings panel), then fixes for its four findings | `3be51de56aa5997e63a4293cc2582ba4` | Agent (`/review`) | 3.67 | `ebfcdbf` |
| [18](18-ide-reviewer-mode.md) | Review of that fix in the custom TaskFlow Reviewer mode, then the fix for the one problem it found | `ee41fc82eab0bff7d8d8a18499d415e0` | TaskFlow Reviewer, then Agent | 0.75 | `031736a` |
| [19](19-ide-plan-deploy.md) | Deployment plan for a free hosting tier (plan file left uncommitted for the deployment step) | `9377c3f147de8f8db9633df6f7148d82` | Plan | 0.18 | - |
| [20](20-ide-ask-explain.md) | Plain-language explanation of the defect and fixes for the demo | `e797c1b93a9bd78bdfc63191ba941ba2` | Ask | 0.15 | - |
| [21](21-ide-ibmi-database.md) | Exploration: what would change to run the SQL on Db2 for i (not verified, not applied) | `acb21dff36766aeb8c3197ee02c7698d` | IBM i Database | 0.12 | - |
| [22](22-ide-ibmi-developer.md) | Exploration: calling the API from IBM i with SQL HTTP functions and RPG (not verified) | `ca044122e8cdeb353b069cfe684866ea` | IBM i Developer | 0.19 | - |
| [23](23-ide-configure-hooks.md) | `/configure-hooks`: PostToolUse hook that runs the regression check after Python edits | `eed39f58e868bbd85d73b88bf46e4cd7` | Agent (`/configure-hooks`) | 1.48 | `c1a483c` |

Screenshots: [review setup](screenshots/ide-review-setup.png) (14 files against `origin/main`),
[review summary and findings panel](screenshots/ide-review-summary.png).

## IBM Bob IDE session 2: building the product

A third Bob session ran in IBM Bob IDE on 2026-10-06 (UTC) after an outside review judged the
first version too small to be a credible product. Bob turned the API into a usable team task board:
a web UI, a task lifecycle with an activity history and a safe upgrade path for existing databases,
a deployable release with CI, and an adversarial release review.

- Claude Code operated the IDE the same way as before (UI automation; approvals read from Bob's
  task store first). It chose answers to Bob's design questions where Bob asked (recorded in each
  file), and its follow-up prompts reported observed failures from its own browser, mutation,
  upgrade and concurrency checks, never the fix.
- One mistake is recorded rather than hidden: in task 24 Claude Code first mis-clicked Bob's option
  to drop task editing, then corrected it in its next message.
- File 27 was rendered from Bob's local task store because the IDE export was not run for that task.

| # | IDE task | Bob task id | Mode | Commits |
|---|---|---|---|---|
| [24](24-ide-ui-plan-build.md) | Web UI: Plan mode design (taskboard-ui-plan.md), then Agent build in 7 milestones, its own /verify-taskflow review, and fixes for failures found in Claude's browser checks | `6c14124e69b1d66f0044b2b8b4491cc8` | Plan, then Agent | `5e461ad` `2524323` `2cbf953` `a31aa0f` `4306e9d` `16a708a` `8ddd831` `a1f56ab` `7f152a1` `a8c8460` `69c17a8` |
| [25](25-ide-lifecycle-plan.md) | Lifecycle and activity history: plan with three assessment subagents (migration, API compatibility, tests) | `e42def3f5f346aeb7b40477f32f3c61d` | Plan | - (plan committed in `66e06c1`) |
| [26](26-ide-lifecycle-build.md) | Lifecycle and activity history: Agent build in 5 milestones plus its own /verify-taskflow review | `0cd085f1cc831effae8819967a28033c` | Agent | `66e06c1` `3eafd01` `4e9931c` `5b150a2` `a44864c` `36ac3b2` `1ca5715` |
| [27](27-ide-lifecycle-mutation-gaps.md) | Tests for two behaviours Claude's mutation check found unpinned | `dfed5e5d0d3214fa92f6863cbe4e9af8` | Agent | `ac7341f` |
| [28](28-ide-lifecycle-ui-fixes.md) | Fixes for four UI problems found in Claude's browser check | `a535e3f639eb9f14ec2b0f9f3a97b1a7` | Agent | `d0ceec8` |
| [29](29-ide-release-ci.md) | Release: release plan, WSGI entry point, health endpoint, smoke test, PythonAnywhere docs, GitHub Actions CI | `33a059478862e00980eb9ea5791ba7e4` | Agent | `41591ed` `6094482` `6211791` |
| [30](30-ide-adversarial-review.md) | Adversarial release-readiness review with five subagent lenses; six defects fixed | `d1c6d047633ceda52365b6e410e6beba` | Agent | `7b6cddc` |
| [31](31-ide-race-fix.md) | Follow-up on an observed concurrency failure (duplicate activity rows); fixed with conditional updates | `fbb3a8b1e92f66f6e510fa1c5e5198e7` | Agent | `8f46140` |

Screenshots of the result: [task board](../docs/screenshots/taskboard-ui.jpg),
[lifecycle statuses](../docs/screenshots/taskboard-lifecycle.jpg).
