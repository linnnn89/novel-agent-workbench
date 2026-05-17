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

    mark_chapter = subparsers.add_parser("mark-chapter-planned")
    mark_chapter.add_argument("project_id")
    mark_chapter.add_argument("chapter_id")
    mark_chapter.add_argument("--title", default="")

    chapter_status = subparsers.add_parser("chapter-status")
    chapter_status.add_argument("project_id")
    chapter_status.add_argument("chapter_id")

    list_chapters = subparsers.add_parser("list-chapters")
    list_chapters.add_argument("project_id")

    configure = subparsers.add_parser("configure-mock-writer")
    configure.add_argument("project_id")
    configure.add_argument("--model", default="mock-writer")

    configure_provider = subparsers.add_parser("configure-provider-role")
    configure_provider.add_argument("project_id")
    configure_provider.add_argument("role", choices=["writer", "scorer", "reviser"])
    configure_provider.add_argument("--provider", required=True)
    configure_provider.add_argument("--model", required=True)
    configure_provider.add_argument("--api-key-ref", default="")
    configure_provider.add_argument("--base-url", default="")

    set_secret = subparsers.add_parser("set-project-secret")
    set_secret.add_argument("project_id")
    set_secret.add_argument("name")
    value_group = set_secret.add_mutually_exclusive_group(required=True)
    value_group.add_argument("--value")
    value_group.add_argument("--value-stdin", action="store_true")

    enable_real = subparsers.add_parser("enable-real-provider")
    enable_real.add_argument("project_id")
    enable_real.add_argument("role", choices=["writer"])
    enable_real.add_argument("--provider", required=True)

    disable_real = subparsers.add_parser("disable-real-provider")
    disable_real.add_argument("project_id")
    disable_real.add_argument("role", choices=["writer"])
    disable_real.add_argument("--provider", default="chutes_openai")

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

    provider_status = subparsers.add_parser("provider-status")
    provider_status.add_argument("project_id")
    provider_status.add_argument("role", choices=["writer", "scorer", "reviser"])

    provider_dry_run = subparsers.add_parser("provider-dry-run")
    provider_dry_run.add_argument("project_id")
    provider_dry_run.add_argument("role", choices=["writer", "scorer", "reviser"])
    provider_dry_run.add_argument("--prompt", required=True)
    provider_dry_run.add_argument("--system-prompt", default="")
    provider_dry_run.add_argument("--max-tokens", type=int, default=None)
    provider_dry_run.add_argument("--temperature", type=float, default=None)

    provider_real_test = subparsers.add_parser("provider-real-test")
    provider_real_test.add_argument("project_id")
    provider_real_test.add_argument("role", choices=["writer", "scorer", "reviser"])
    provider_real_test.add_argument("--prompt", default="Return exactly OK.")
    provider_real_test.add_argument("--system-prompt", default="")
    provider_real_test.add_argument("--max-tokens", type=int, default=16)
    provider_real_test.add_argument("--temperature", type=float, default=0)

    chutes_once = subparsers.add_parser("chutes-generate-once")
    chutes_once.add_argument("project_id")
    chutes_once.add_argument("--chapter-id", required=True)
    chutes_once.add_argument("--prompt", required=True)
    chutes_once.add_argument("--title", default="")
    chutes_once.add_argument("--system-prompt", default="")
    chutes_once.add_argument("--model", default="Qwen/Qwen3-32B-TEE")
    chutes_once.add_argument("--base-url", default="https://llm.chutes.ai/v1")
    chutes_once.add_argument("--secret-name", default="chutes_key")
    secret_value_group = chutes_once.add_mutually_exclusive_group()
    secret_value_group.add_argument("--secret-value")
    secret_value_group.add_argument("--secret-value-stdin", action="store_true")
    chutes_once.add_argument("--max-tokens", type=int, default=96)
    chutes_once.add_argument("--temperature", type=float, default=0.2)
    chutes_once.add_argument("--allow-network", action="store_true")
    clear_group = chutes_once.add_mutually_exclusive_group()
    clear_group.add_argument("--clear-secret-after-run", dest="clear_secret_after_run", action="store_true", default=True)
    clear_group.add_argument("--keep-secret-after-run", dest="clear_secret_after_run", action="store_false")

    subparsers.add_parser("list-provider-adapters")

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
    if command == "mark-chapter-planned":
        return app.mark_chapter_planned(args.project_id, args.chapter_id, title=args.title)
    if command == "chapter-status":
        return app.chapter_status(args.project_id, args.chapter_id)
    if command == "list-chapters":
        return app.list_chapters(args.project_id)
    if command == "configure-mock-writer":
        return app.configure_mock_writer(args.project_id, model=args.model)
    if command == "configure-provider-role":
        return app.configure_provider_role(
            args.project_id,
            args.role,
            provider=args.provider,
            model=args.model,
            api_key_ref=args.api_key_ref,
            base_url=args.base_url,
        )
    if command == "set-project-secret":
        value = sys.stdin.read().strip() if args.value_stdin else args.value
        return app.set_project_secret(args.project_id, args.name, value)
    if command == "enable-real-provider":
        return app.enable_real_provider(args.project_id, args.role, provider=args.provider)
    if command == "disable-real-provider":
        return app.disable_real_provider(args.project_id, args.role, provider=args.provider)
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
    if command == "provider-status":
        return app.provider_status(args.project_id, args.role)
    if command == "provider-dry-run":
        return app.provider_dry_run(
            args.project_id,
            args.role,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "provider-real-test":
        return app.provider_real_test(
            args.project_id,
            args.role,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "chutes-generate-once":
        secret_value = sys.stdin.read().strip() if args.secret_value_stdin else (args.secret_value or "")
        return app.chutes_generate_once(
            args.project_id,
            chapter_id=args.chapter_id,
            title=args.title,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            model=args.model,
            base_url=args.base_url,
            secret_name=args.secret_name,
            secret_value=secret_value,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            allow_network=args.allow_network,
            clear_secret_after_run=args.clear_secret_after_run,
        )
    if command == "list-provider-adapters":
        return app.list_provider_adapters()
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
