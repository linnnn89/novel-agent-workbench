from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .application_service import WorkbenchApplicationService
from .storage import DEFAULT_PROJECTS_DIRNAME


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except Exception as exc:
        write_json({"ok": False, "error_type": exc.__class__.__name__, "message": str(exc)}, stderr=True)
        return 1
    write_json({"ok": True, "result": result})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel-agent-workbench", description="Backend-only workbench CLI.")
    parser.add_argument(
        "--projects-root",
        default=DEFAULT_PROJECTS_DIRNAME,
        help="Project data root. Defaults to ./workspace_projects relative to the current directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-project")
    create.add_argument("project_id")
    create.add_argument("--title", default="")

    subparsers.add_parser("list-projects")

    state = subparsers.add_parser("state")
    state.add_argument("project_id")

    configure = subparsers.add_parser("configure-mock-writer")
    configure.add_argument("project_id")
    configure.add_argument("--model", default="mock-writer")

    generate = subparsers.add_parser("generate-draft")
    generate.add_argument("project_id")
    generate.add_argument("--chapter-id", required=True)
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--title", default="")
    generate.add_argument("--system-prompt", default="")
    generate.add_argument("--max-tokens", type=int, default=None)
    generate.add_argument("--temperature", type=float, default=None)

    list_drafts = subparsers.add_parser("list-drafts")
    list_drafts.add_argument("project_id")

    read_draft = subparsers.add_parser("read-draft")
    read_draft.add_argument("project_id")
    read_draft.add_argument("draft_id")

    commit = subparsers.add_parser("commit-draft")
    commit.add_argument("project_id")
    commit.add_argument("draft_id")

    list_confirmed = subparsers.add_parser("list-confirmed")
    list_confirmed.add_argument("project_id")

    read_confirmed = subparsers.add_parser("read-confirmed")
    read_confirmed.add_argument("project_id")
    read_confirmed.add_argument("chapter_id")

    audit = subparsers.add_parser("audit-project")
    audit.add_argument("project_id")

    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("project_id")
    smoke.add_argument("--title", default="")
    smoke.add_argument("--chapter-id", default="chapter_001")
    smoke.add_argument("--chapter-title", default="")
    smoke.add_argument("--prompt", required=True)
    smoke.add_argument("--commit", action="store_true")

    return parser


def run_command(args: argparse.Namespace) -> Any:
    app = WorkbenchApplicationService.open(Path(args.projects_root))
    command = args.command
    if command == "create-project":
        return app.create_project(args.project_id, title=args.title)
    if command == "list-projects":
        return app.list_projects()
    if command == "state":
        return app.project_state(args.project_id)
    if command == "configure-mock-writer":
        return app.configure_mock_writer(args.project_id, model=args.model)
    if command == "generate-draft":
        return app.generate_draft(
            args.project_id,
            chapter_id=args.chapter_id,
            title=args.title,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "list-drafts":
        return app.list_drafts(args.project_id)
    if command == "read-draft":
        return app.read_draft(args.project_id, args.draft_id)
    if command == "commit-draft":
        return app.commit_draft(args.project_id, args.draft_id)
    if command == "list-confirmed":
        return app.list_confirmed_chapters(args.project_id)
    if command == "read-confirmed":
        return app.read_confirmed_chapter(args.project_id, args.chapter_id)
    if command == "audit-project":
        return app.audit_project(args.project_id)
    if command == "smoke":
        return run_smoke(app, args)
    raise ValueError(f"Unknown command: {command}")


def run_smoke(app: WorkbenchApplicationService, args: argparse.Namespace) -> dict[str, Any]:
    created = app.create_project(args.project_id, title=args.title)
    writer = app.configure_mock_writer(args.project_id)
    draft = app.generate_draft(
        args.project_id,
        chapter_id=args.chapter_id,
        title=args.chapter_title,
        prompt=args.prompt,
    )
    committed = app.commit_draft(args.project_id, draft["draft_id"]) if args.commit else None
    state = app.project_state(args.project_id)
    return {
        "project": {"project_id": created["project_id"], "title": created["title"], "path": created["path"]},
        "writer": {"provider": writer["provider"], "model": writer["model"], "configured": bool(writer["provider"])},
        "draft": draft,
        "committed": committed,
        "state": state,
    }


def write_json(value: Any, *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
