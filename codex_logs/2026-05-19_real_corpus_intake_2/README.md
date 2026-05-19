# Real Corpus Intake 2

Date: 2026-05-19, Asia/Shanghai.

## Source

User provided a second real web-novel fanfiction text file for future MVP-13 testing.

```text
T:/迅雷/请给我二次元多点日常⊙俱式咸仁⊙全本(1).txt
```

## File Metadata

```text
Size bytes: 2483448
LastWriteTime: 2024-10-03 22:35:44
Detected encoding: GB18030
Approx line count: 25213
Strict chapter heading line count: 400
Loose chapter-like count: 405
SHA256: 51EB8AE6EA7118F997CED7EB49E4DF475350411CF0416A822F41570435ED3BF5
```

## Structure Notes

Strict chapter-heading regex:

```text
(?m)^\s*第[0-9一二三四五六七八九十百千万零〇两]+[章节卷回幕].{0,40}$
```

This file appears much more structurally regular than the first intake corpus. It is currently the better candidate for MVP-13 corpus profiling and section-boundary tests.

## Safety Boundary

- The original text remains outside the Git worktree.
- No source text was copied into this repository.
- No Memory Bank, RAG, draft, confirmed chapter, or Provider call was created from this corpus.
- Future tests should use metadata-only profiling unless the user explicitly authorizes importing excerpts or derived summaries.

## Recommended Next Step

Use this corpus first for MVP-13 read-only Corpus Profiler:

```text
encoding detection
chapter heading extraction
chapter length distribution
dialogue/narration proxy statistics
candidate character-name frequency
metadata-only report
```

Do not copy the full text into project storage or Git.
