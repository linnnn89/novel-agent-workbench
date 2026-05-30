# 2026-05-30 Open-source build BAT and Python 3.10 floor

## Scope

Prepared the Windows build flow for GitHub publication.

## Changes

- Added `BUILD_NovelAgentWorkbench.bat` as the one-click foreground build entrypoint.
- Kept all build paths repository-relative.
- Relaxed `requires-python` from `>=3.13` to `>=3.10`.
- Replaced `datetime.UTC` with `datetime.timezone.utc` for Python 3.10 compatibility.
- Updated setup/build docs away from machine-specific absolute paths.
- Preserved `dist\NovelAgentWorkbench\用户数据` during rebuild.

## Verification

```text
cmd /c SETUP_ENV.bat --no-pause
cmd /c BUILD_NovelAgentWorkbench.bat --no-pause
py -3.10 -B -c "import sys, unittest; sys.path.insert(0, r'I:\AI-NOVEL\novel_agent_workbench\src'); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=1).run(suite); sys.exit(0 if result.wasSuccessful() else 1)"
```

Results:

```text
SETUP_ENV.bat completed.
BUILD_NovelAgentWorkbench.bat completed.
Built dist\NovelAgentWorkbench\NovelAgentWorkbench.exe.
Python 3.10 tests: Ran 10 tests, OK.
dist\NovelAgentWorkbench\用户数据 exists after rebuild.
```

## README install section update

The public README now includes explicit Chinese and English Windows installation/running instructions:

- minimum environment: Windows 10/11, Python 3.10 or newer, first-build network access for packaging dependencies;
- one-click build: `BUILD_NovelAgentWorkbench.bat`;
- final runnable EXE: `dist\NovelAgentWorkbench\NovelAgentWorkbench.exe`;
- development-only setup: `SETUP_ENV.bat`;
- non-interactive verification: `SETUP_ENV.bat --no-pause` and `BUILD_NovelAgentWorkbench.bat --no-pause`;
- source-mode desktop launch: `.venv\Scripts\novel-agent-workbench-desktop.exe`.

The README also now includes first-screen Chinese/English highlight bullets and developer entry points so GitHub visitors can quickly distinguish user value from extension points.

## Chinese search-card positioning update

The README first screen was rewritten in plainer Chinese for Chinese novel-writing users:

- positions the app as a local AI writing workbench for web-novel and long-form authors;
- says it is not merely a chat box that writes one passage;
- foregrounds outlines, characters, world-building, Memory Bank, chapter drafts, AI review, rewrite candidates, confirmed-text workflow, local data, and one-click Windows build;
- adds a recommended GitHub About description:

```text
给网文/长篇作者用的本地 AI 小说写作工作台：管大纲、人物世界观、记忆库、章节草稿、AI审稿和重写，数据本地保存，Windows 一键运行。
```
