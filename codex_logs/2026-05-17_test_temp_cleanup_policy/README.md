# Test Temporary Cleanup Policy Log

Date: 2026-05-17, Asia/Shanghai.

## Decision

Tests may create and automatically clean test-only temporary files and directories.

## Boundary

Allowed:

```text
system temp directory
test-owned temporary directory
```

Not allowed:

```text
hard deleting real project files under workspace_projects/
hard deleting reference project files
hard deleting user-created content
```

Real project files must still use `.trash` for reversible retirement.

## Next Step

Implement MVP-0 storage tests using Python temporary directories.
