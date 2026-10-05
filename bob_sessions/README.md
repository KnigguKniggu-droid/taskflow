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
