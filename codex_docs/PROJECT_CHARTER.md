# Project Charter

Date: 2026-05-17, Asia/Shanghai.

## Identity

`novel_agent_workbench` is a new implementation project. It uses the downloaded Tonade source only as reference material.

## Primary Goal

Build a local, personal, recoverable long-form novel writing workbench that can help finish a full-length novel without uncontrolled context pollution, project contamination, or brittle automation.

## Non-Negotiable Rules

1. Do not modify `I:\AI-NOVEL\Tonade_DSv4-flash_100w_novel_agent-main` in place.
2. Do not delete user data or generated work silently.
3. During early MVP work, do not perform real file deletion. Retire files by renaming with the `.trash` suffix.
4. Write Markdown after every meaningful change.
5. Keep business logic in backend modules, not frontend JavaScript.
6. Keep draft revisions separate from confirmed chapters.
7. Only confirmed chapters may update formal context, Memory Bank, RAG, game state, and export.
8. API keys must not be logged, exported, returned in app state, or stored in general config.
9. Cross-project import means copy with new ids, never runtime dynamic reference.
10. MVP work should be phased; do not jump into advanced World Book, Prompt Inspector, or browser automation before safety and context foundations are stable.

## Reference Project Usage

Allowed:

- read architecture,
- inspect behavior,
- run reference tests when useful,
- copy small code ideas after review,
- compare UI flow and data files.

Not allowed:

- edit files in the reference project,
- run destructive cleanup in it,
- migrate it in place,
- treat its `app_projects` as the active data store for the new build.

## First MVP Direction

MVP-0 should establish safe JSON storage, backup/checkpoint conventions, project lock, local secrets boundary, basic app/project layout, and tests proving safety behavior.

First engineering slice:

```text
ProjectStore + atomic JSON persistence + backup + project lock + secrets/config separation + unit tests
```

Second engineering slice:

```text
ProjectStore checkpoint ZIP + manifest + reversible restore
```

Third engineering slice:

```text
ProjectRegistry + default workspace_projects routing + registry.json + unit tests
```

Do not start MVP-0 with frontend, LLM calls, prompt design, or chapter generation.

MVP-0 verification mode:

```text
unit tests and minimal commands only; no frontend required
```

Runtime project data default:

```text
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

This directory is for real local project data and must not be tracked by Git.

Deletion policy:

```text
No real deletion in early MVP. Use .trash for reversible retirement.
```

Testing exception:

```text
Unit tests may create and clean isolated temporary files/directories. This exception does not apply to real runtime project data.
```

Checkpoint policy:

```text
Checkpoints exclude secrets by default. Restore must not hard delete; overwritten files are retired with .trash.
```

## Construction Strategy

Start from a clean skeleton. Use the reference project as a design and behavior sample only.

If code is copied from the reference project, the copied scope must be small, reviewed, and logged with:

```text
source file
target file
reason for reuse
risk checked
test added or reused
```

## Version Control

The active implementation folder uses local Git for snapshots and diffs.

Rules:

- local repository only unless the user explicitly asks for remote publishing,
- do not track secrets or local environment files,
- do not track generated runtime projects, exports, backups, or logs,
- check `git status` before and after meaningful code edits.
