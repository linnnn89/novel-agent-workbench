# MVP-13 Corpus Profiler

Date: 2026-05-19, Asia/Shanghai.

## Goal

Add a backend-only read-only profiler for external `.txt` novel corpora.

The profiler is intentionally not an importer. It returns metadata needed for later design work without copying source text into project storage.

## Files Changed

```text
src/novel_agent_workbench/corpus_profiler.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
tests/test_corpus_profiler.py
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

## Implemented Behavior

`profile_corpus(path, max_name_candidates=20)` returns:

```text
source file metadata
encoding detection
line and chapter structure counts
chapter length distribution
line length distribution
dialogue proxy counts
rough name candidate frequencies
safety flags
```

CLI:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> profile-corpus <txt-path> --max-name-candidates 12
```

## Safety Boundary

- No Provider call.
- No project initialization.
- No project file writes.
- No source text or chapter heading text copied into output.
- No drafts, confirmed chapters, Memory Bank, RAG, export, DOCX, or UI work.
- Name candidates are heuristic only and may contain false positives.

## Real Corpus Smoke

Read-only CLI smoke was run on:

```text
T:\迅雷\请给我二次元多点日常⊙俱式咸仁⊙全本(1).txt
```

Metadata result:

```text
encoding: gb18030
size_bytes: 2483448
line_count: 25213
nonempty_line_count: 24330
strict_chapter_heading_count: 400
loose_chapter_like_count: 405
chapter_count: 400
chapter_median_chars: 2846
chapter_mean_chars: 3092.89
dialogue_like_line_count: 13040
dialogue_like_line_ratio: 0.536
secret_like_pattern_found: false
```

No report artifact was stored for the real corpus.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_corpus_profiler
```

Result:

```text
Ran 2 tests in 0.013s
OK
```

Full test result should be recorded after the final full-suite run.

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 195 tests in 16.734s
OK
```

Leak scans:

```text
Chutes key fragments: no matches
real corpus excerpt phrases: no matches
```

## Known Limits

- Name extraction is a rough frequency heuristic and currently catches false positives.
- Chapter heading detection is regex-based and should be treated as a practical estimate.
- The profiler does not create durable profile artifacts yet.

## Next Step

Decide whether corpus profile reports should be saved as project artifacts, or remain transient CLI output until a stricter copyright/safety policy is designed.
