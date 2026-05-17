# Trash Suffix Decision Log

Date: 2026-05-17, Asia/Shanghai.

## Decision

Use `.trash` as the single suffix for reversible file retirement.

## Reason

`.trash` is short, clear, easy to search, and communicates recoverable retirement rather than pending hard deletion.

## Operational Consequence

If a file must be retired during MVP work, rename it like:

```text
example.py.trash
config.json.trash
```

Do not hard delete. Do not introduce other suffixes unless the user changes this rule.
