# Real Corpus Intake

Date: 2026-05-19, Asia/Shanghai.

## Source

User provided a real web-novel fanfiction text file for future MVP-13 testing.

```text
T:/迅雷/告白失败的浅一会失忆⊙渔夫绅士⊙全本.txt
```

## File Metadata

```text
Size bytes: 4649593
LastWriteTime: 2024-10-03 22:35:47
Detected encoding: GB18030
Approx line count: 56107
SHA256: D3B168ABF1D2ACEB0384E67FD4E2D368AA3E586BC783EC7AE297F19E2C0AB781
```

## Structure Notes

Strict chapter-heading regex:

```text
(?m)^\s*第[0-9一二三四五六七八九十百千万零〇两]+[章节卷回幕].{0,40}$
```

Only a few strict matches were detected. This means the file should not be treated as a standard `第X章` corpus without a dedicated structure-detection pass.

## Safety Boundary

- The original text remains outside the Git worktree.
- No source text was copied into this repository.
- No Memory Bank, RAG, draft, confirmed chapter, or Provider call was created from this corpus.
- Future tests should use derived metadata, short operator-approved excerpts, or temporary test directories unless the user explicitly authorizes a corpus import.

## Recommended Next Step

MVP-13 should start with a read-only corpus profiler:

```text
detect encoding
line/paragraph statistics
candidate section boundaries
dialogue/narration ratio
character-name frequency candidates
safe metadata-only report
```

The profiler should not copy the full text into project storage or Git.
