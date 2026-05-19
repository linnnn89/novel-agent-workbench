# Real Corpus Profile And Boundary Smoke

Date: 2026-05-19, Asia/Shanghai.

## Authorization

The user explicitly allowed reading the two supplied real web-novel `.txt` files for testing.

Scope of this test:

```text
read-only source TXT access
temporary project root only
metadata-only profile artifacts
no-text boundary artifacts
audit-project verification
```

Not allowed or not done:

```text
no source TXT modification
no source text copied into repository
no chapter heading text copied into repository
no candidate-name text copied into repository
no external source path stored in persistent test artifacts
no Provider call
no draft or confirmed chapter creation
no Memory Bank/RAG/export update
```

## Command Shape

Temporary projects were created under `%TEMP%`, not under the real `workspace_projects` directory.

Commands exercised through the backend CLI:

```powershell
create-project
save-corpus-profile
save-corpus-boundaries
read-corpus-profile
read-corpus-boundaries
audit-project
```

## Results

### User Corpus 1

```text
source_sha256: D3B168ABF1D2ACEB0384E67FD4E2D368AA3E586BC783EC7AE297F19E2C0AB781
encoding: gb18030
line_count: 56107
strict_chapter_heading_count: 3
boundary_chapter_count: 3
profile_status: profile_ready
boundary_status: boundaries_ready
audit_ok: true
audit_finding_count: 0
```

Safety flags:

```text
source_path_stored: false
candidate_names_stored: false
source_text_copied: false
heading_text_included: false
```

Observation:

```text
The strict chapter-heading regex finds very few headings for this corpus. Later chapter detection needs a looser or corpus-specific boundary strategy before any import/sampling feature depends on it.
```

### User Corpus 2

```text
source_sha256: 51EB8AE6EA7118F997CED7EB49E4DF475350411CF0416A822F41570435ED3BF5
encoding: gb18030
line_count: 25213
strict_chapter_heading_count: 400
boundary_chapter_count: 400
profile_status: profile_ready
boundary_status: boundaries_ready
audit_ok: true
audit_finding_count: 0
```

Safety flags:

```text
source_path_stored: false
candidate_names_stored: false
source_text_copied: false
heading_text_included: false
```

Observation:

```text
The strict heading regex works well for this corpus and produces a complete no-text boundary index.
```

## Verification Summary

Both authorized files can be processed through the current conservative corpus pipeline:

```text
external txt -> profile metadata artifact -> no-text boundary artifact -> audit-project
```

Both temporary test projects passed audit.

## Next Decision Needed

The current implementation intentionally stops before storing real excerpts, summaries, style samples, character facts, or world-building facts.

Before the next phase, the user should decide whether and how much real corpus text may be persisted:

```text
none: keep offsets/statistics only
short excerpts: save bounded local samples for manual review
derived summaries: allow generated/manual summaries but not verbatim text
style analysis: allow metadata-only style features first
```
