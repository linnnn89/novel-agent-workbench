# No Real Deletion Policy Log

Date: 2026-05-17, Asia/Shanghai.

## User Decision

Do not allow real file deletion for now.

If a file is confirmed unnecessary, retire it by renaming it with a clear suffix such as:

```text
.trash
```

The file should remain restorable and easy to recognize.

Follow-up decision: `.trash` is the single standard suffix. Do not use `.ontodelete` unless the user changes this rule later.

## Operational Consequence

Early MVP code and manual operations should not use actual delete behavior for project files.

Deletion-like user actions should be designed as reversible retirement/archiving.

## Files Updated

```text
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_no_real_deletion_policy\README.md
```

## Next Step

When implementing `ProjectStore`, include this policy in storage operation design: no hard delete API in MVP-0.
