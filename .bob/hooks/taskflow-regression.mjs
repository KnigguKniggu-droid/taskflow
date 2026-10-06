/**
 * PostToolUse hook: run the TaskFlow regression check after Bob edits
 * any Python file under app/ or tests/.
 *
 * Triggered by: write_file, apply_diff, search_and_replace, insert_content
 * Configured in: .bob/settings.json
 */
import { spawnSync } from "node:child_process";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const file = String(input.tool_input?.path ?? "");

// Only trigger for Python files under app/ or tests/
if (/^(app|tests)[\\/].*\.py$/.test(file)) {
    const result = spawnSync(
        ".venv\\Scripts\\python.exe",
        [".bob\\skills\\taskflow-regression-check\\regression_check.py"],
        { encoding: "utf8" }
    );
    const out = (result.stdout ?? "") + (result.stderr ?? result.error?.message ?? "");
    if (out.trim()) process.stdout.write(out);
}
