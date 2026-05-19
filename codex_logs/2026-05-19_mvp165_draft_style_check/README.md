# MVP-16.5 Draft vs Self Style Check

Date: 2026-05-19, Asia/Shanghai.

## Goal

Compare one draft to the project's own self-style baseline using local statistics only.

This is not an LLM review and not a revision system. It is a deterministic metadata check for:

- chapter length,
- paragraph and sentence counts,
- dialogue-line ratio,
- average sentence and paragraph length,
- selected punctuation frequency.

## Files Changed

```text
src/novel_agent_workbench/self_style.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/__init__.py
tests/test_self_style_baseline.py
tests/test_application_service.py
README.md
src/README.md
tests/README.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## Storage

```text
data/style_checks/*.json
data/style_checks_index.json
```

Artifacts store numeric draft metrics, baseline ids, comparison statuses, and issue counts.

Artifacts do not store draft text, prompt text, generated content, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> check-draft-style <project_id> <draft_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-draft-style-checks <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-draft-style-check <project_id> <check_id>
```

`check-draft-style` uses the latest self-style baseline unless `--baseline-id` is provided.

## Safety Boundary

The service reads draft text in memory only to compute metrics. It does not call Providers, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, or write prompt logs.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline tests.test_application_service
```

Result:

```text
Ran 22 tests in 2.986s
OK
```

Full regression is recorded after this log is written.

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 220 tests in 21.340s
OK
```

Leak scan:

```text
Known Chutes key fragments and known real-corpus sample snippets: no matches in novel_agent_workbench or PROJECT_INDEX.md.
```

Prepublish summary:

```text
blocker_count=0
warning_count=4
finding_count=4
```

The four warnings are existing local Chutes runtime project warnings. They are not source publication blockers.

## Next

Add an optional local rule-to-revision-request bridge: style check findings can create a metadata-only revision request suggestion, but still must not call Providers or mutate drafts automatically.
