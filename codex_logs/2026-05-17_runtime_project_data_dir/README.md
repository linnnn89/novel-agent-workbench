# Runtime Project Data Directory Log

Date: 2026-05-17, Asia/Shanghai.

## Decision

The default runtime project data directory for the new implementation is:

```text
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

## Reason

This keeps new runtime data separate from the reference project and allows Git to ignore real user data by default.

## Files Updated

```text
.gitignore
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_runtime_project_data_dir\README.md
```

## Verification

Pending: commit this documentation and ignore-rule update.
