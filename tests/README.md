# Tests

This folder will contain tests for the new implementation.

Minimum early test targets:

- atomic JSON write recovery,
- backup creation,
- project lock behavior,
- API key masking and secrets isolation,
- draft revisions having no confirmed-state side effects,
- confirmed revision commit behavior.

Current MVP-0 command:

```powershell
py -3.13 -m unittest discover -s tests
```

Current implemented tests cover the storage kernel only. Draft/confirmed tests belong to a later MVP slice.

Checkpoint tests currently cover:

- manifest creation,
- default secret exclusion,
- explicit secret inclusion,
- restore to checkpoint state,
- `.trash` retirement of overwritten files,
- project mismatch rejection,
- unsafe checkpoint path rejection.
