# HelicOps Guardrail Enforcement

This project uses HelicOps for code quality and security enforcement via MCP.

## MANDATORY: All code writes must go through the HelicOps MCP pipeline

Do NOT use `write_file` or `replace` directly. They will be blocked.

Instead, use this workflow for every file write:

1. `helicops_get_applicable_guardrails(file_path, operation_type)` — know what rules apply
2. `helicops_propose_write(file_path, language, diff_or_content)` — submit for review
3. `helicops_validate_write(proposal_id)` — get pass/block decision
4. `helicops_commit_write(proposal_id)` — write to disk only after validation passes

If `validate_write` returns violations, fix them and re-propose. Do not use overrides without explicit user approval.
