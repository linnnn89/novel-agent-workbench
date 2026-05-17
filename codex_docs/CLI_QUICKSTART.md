# CLI Quickstart

Date: 2026-05-17, Asia/Shanghai.

## Scope

This is a backend-only local workflow. It does not start a UI, does not call a real model, does not use the network, and does not cost API credits.

Current Provider mode:

```text
mock only
```

## PowerShell Setup

Run commands from:

```powershell
cd I:\AI-NOVEL\novel_agent_workbench
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
```

Use Python 3.13:

```powershell
py -3.13 -m novel_agent_workbench.cli --help
```

Recommended safe practice path for experiments:

```powershell
$env:TEMP\naw_manual_test
```

Real project path when ready:

```powershell
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

`workspace_projects` is ignored by Git.

## One-Command Smoke

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
```

Expected high-level result:

```text
ok: true
draft_count: 1
committed_chapter_count: 1
```

The JSON output should not contain the original prompt text.

## Step-By-Step Flow

Create a project:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-project demo_project --title "Demo Novel"
```

Configure mock writer:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-mock-writer demo_project
```

Generate a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test generate-draft demo_project --chapter-id chapter_001 --title "Opening" --prompt "Write a short mock opening."
```

Copy the returned `draft_id`, then inspect safe state:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test state demo_project
```

List drafts:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-drafts demo_project
```

Read a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-draft demo_project <draft_id>
```

Explicitly commit a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test commit-draft demo_project <draft_id>
```

List confirmed chapters:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-confirmed demo_project
```

Read a confirmed chapter:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-confirmed demo_project chapter_001
```

Audit a project:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test audit-project demo_project
```

Expected clean audit:

```text
ok: true
findings: []
```

## Safety And Cleanup Policy

Do not hard delete real project files during early MVP.

If a real file must be retired later, rename it with `.trash`.

Unit tests and manual experiments under system temp directories are allowed to use temporary cleanup. Do not treat that exception as permission to delete real `workspace_projects` data.

## Common Errors

Writer is not configured:

```text
ProviderError: Model role has no provider configured.
```

Fix:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> configure-mock-writer <project_id>
```

Duplicate commit:

```text
DraftGenerationError: Draft is not committable
```

Meaning: the draft was already committed, or another confirmed chapter already owns the same `chapter_id`.

Unsafe project id:

```text
InvalidProjectIdError
```

Use only letters, numbers, `_`, and `-`. Do not use slashes, colons, spaces, `.` or `..`.

