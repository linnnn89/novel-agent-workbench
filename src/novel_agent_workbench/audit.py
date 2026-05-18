from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .providers import CHUTES_PROVIDER_ID, REAL_GENERATION_FLAG, ModelRoleConfig, get_provider_adapter
from .project_state import public_project_state
from .storage import ProjectStore


SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r'"api_key"\s*:', re.IGNORECASE),
]
PROMPT_PATTERNS = [
    re.compile(r'"prompt"\s*:', re.IGNORECASE),
    re.compile(r'"prompt_text"\s*:', re.IGNORECASE),
    re.compile(r'"system_prompt"\s*:', re.IGNORECASE),
    re.compile(r"private .*prompt", re.IGNORECASE),
]
CONTENT_PATTERNS = [
    re.compile(r"\bcontent\b", re.IGNORECASE),
    re.compile(r"MOCK writer", re.IGNORECASE),
]


@dataclass(frozen=True, slots=True)
class AuditFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_project(store: ProjectStore) -> dict[str, Any]:
    """Read-only project safety audit."""

    checked_paths: list[str] = []
    findings: list[AuditFinding] = []
    check_text_file(
        store.config_path,
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_config", SECRET_PATTERNS)],
    )
    check_text_file(
        store.data_dir / "provider_call_log.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_prompt_in_provider_log", PROMPT_PATTERNS),
            ("possible_secret_in_provider_log", SECRET_PATTERNS),
        ],
    )
    check_text_file(
        store.data_dir / "commit_log.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_content_in_commit_log", CONTENT_PATTERNS),
            ("possible_secret_in_commit_log", SECRET_PATTERNS),
        ],
    )
    check_text_file(
        store.data_dir / "chapters_workflow.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_prompt_in_chapter_workflow", PROMPT_PATTERNS),
            ("possible_secret_in_chapter_workflow", SECRET_PATTERNS),
            ("possible_content_in_chapter_workflow", CONTENT_PATTERNS),
        ],
    )
    check_text_file(
        store.data_dir / "context_update_queue.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_prompt_in_context_update_queue", PROMPT_PATTERNS),
            ("possible_secret_in_context_update_queue", SECRET_PATTERNS),
            ("possible_content_in_context_update_queue", CONTENT_PATTERNS),
        ],
    )
    audit_context_previews(store, checked_paths=checked_paths, findings=findings)
    audit_reviews(store, checked_paths=checked_paths, findings=findings)
    audit_revision_requests(store, checked_paths=checked_paths, findings=findings)
    audit_revision_consistency(store, checked_paths=checked_paths, findings=findings)
    audit_checkpoints(store, checked_paths=checked_paths, findings=findings)
    audit_provider_adapter_config(store, checked_paths=checked_paths, findings=findings)
    audit_draft_confirmed_consistency(store, checked_paths=checked_paths, findings=findings)
    audit_public_state(store, checked_paths=checked_paths, findings=findings)
    return {
        "ok": not findings,
        "project_id": store.project_id,
        "findings": [finding.to_dict() for finding in findings],
        "checked_paths": checked_paths,
    }


def check_text_file(
    path: Path,
    *,
    checked_paths: list[str],
    findings: list[AuditFinding],
    pattern_groups: list[tuple[str, list[re.Pattern[str]]]],
) -> None:
    checked_paths.append(str(path))
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    for code, patterns in pattern_groups:
        for pattern in patterns:
            if pattern.search(text):
                findings.append(AuditFinding(code=code, path=str(path), message=f"Matched {pattern.pattern}"))
                break


def audit_reviews(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_review", PROMPT_PATTERNS),
        ("possible_secret_in_review", SECRET_PATTERNS),
        ("possible_content_in_review", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "reviews_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    reviews_dir = store.data_dir / "reviews"
    checked_paths.append(str(reviews_dir))
    if not reviews_dir.exists():
        return
    for path in sorted(reviews_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)


def audit_revision_requests(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_revision_request", PROMPT_PATTERNS),
        ("possible_secret_in_revision_request", SECRET_PATTERNS),
        ("possible_content_in_revision_request", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "revision_requests_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    requests_dir = store.data_dir / "revision_requests"
    checked_paths.append(str(requests_dir))
    if not requests_dir.exists():
        return
    for path in sorted(requests_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)


def audit_context_previews(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_context_preview", PROMPT_PATTERNS),
        ("possible_secret_in_context_preview", SECRET_PATTERNS),
        ("possible_content_in_context_preview", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "context_update_previews_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    previews_dir = store.data_dir / "context_update_previews"
    checked_paths.append(str(previews_dir))
    if not previews_dir.exists():
        return
    for path in sorted(previews_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)


def audit_revision_consistency(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    requests_index_path = store.data_dir / "revision_requests_index.json"
    drafts_index_path = store.data_dir / "drafts_index.json"
    requests_dir = store.data_dir / "revision_requests"
    requests_index = read_json_file(requests_index_path, checked_paths=checked_paths, findings=findings)
    drafts_index = read_json_file(drafts_index_path, checked_paths=checked_paths, findings=findings)
    request_entries = list_items(requests_index, "revision_requests")
    draft_entries = list_items(drafts_index, "drafts")
    draft_by_id = {str(item.get("draft_id")): item for item in draft_entries if item.get("draft_id")}
    request_paths = {normalize_project_path(str(item.get("path"))) for item in request_entries if item.get("path")}

    checked_paths.append(str(requests_dir))
    if requests_dir.exists():
        for artifact_path in sorted(requests_dir.glob("*.json")):
            relative = artifact_path.relative_to(store.root).as_posix()
            checked_paths.append(str(artifact_path))
            if relative not in request_paths:
                findings.append(
                    AuditFinding(
                        code="orphan_revision_request_artifact",
                        path=str(artifact_path),
                        message="Revision request artifact is not referenced by data/revision_requests_index.json.",
                    )
                )

    for entry in request_entries:
        revision_request_id = str(entry.get("revision_request_id") or "")
        review_id = str(entry.get("review_id") or "")
        source_draft_id = str(entry.get("draft_id") or "")
        chapter_id = str(entry.get("chapter_id") or "")
        path_value = entry.get("path")
        if not revision_request_id or not isinstance(path_value, str) or not path_value:
            findings.append(
                AuditFinding(
                    code="invalid_revision_request_index_entry",
                    path=str(requests_index_path),
                    message="Revision request index entry is missing revision_request_id or artifact path.",
                )
            )
            continue
        artifact_path = project_relative_artifact_path(store, path_value)
        if artifact_path is None:
            findings.append(
                AuditFinding(
                    code="unsafe_revision_request_artifact_path",
                    path=str(requests_index_path),
                    message=f"Revision request {revision_request_id} artifact path escapes project root.",
                )
            )
            continue
        artifact = read_json_file(artifact_path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            findings.append(
                AuditFinding(
                    code="missing_revision_request_artifact",
                    path=str(artifact_path),
                    message=f"Revision request {revision_request_id} artifact is missing.",
                )
            )
            continue
        if str(artifact.get("revision_request_id") or "") != revision_request_id:
            findings.append(
                AuditFinding(
                    code="revision_request_id_mismatch",
                    path=str(artifact_path),
                    message="Revision request artifact id does not match index entry.",
                )
            )
        if str(artifact.get("review_id") or "") != review_id:
            findings.append(
                AuditFinding(
                    code="revision_request_review_mismatch",
                    path=str(artifact_path),
                    message="Revision request artifact review_id does not match index entry.",
                )
            )
        if str(artifact.get("draft_id") or "") != source_draft_id:
            findings.append(
                AuditFinding(
                    code="revision_request_source_draft_mismatch",
                    path=str(artifact_path),
                    message="Revision request artifact draft_id does not match index entry.",
                )
            )
        if str(artifact.get("chapter_id") or "") != chapter_id:
            findings.append(
                AuditFinding(
                    code="revision_request_chapter_mismatch",
                    path=str(artifact_path),
                    message="Revision request artifact chapter_id does not match index entry.",
                )
            )
        if source_draft_id and source_draft_id not in draft_by_id:
            findings.append(
                AuditFinding(
                    code="revision_request_source_draft_missing",
                    path=str(requests_index_path),
                    message=f"Revision request {revision_request_id} references missing source draft {source_draft_id}.",
                )
            )

        status = str(artifact.get("status") or entry.get("status") or "")
        generated_draft_id = str(artifact.get("generated_draft_id") or entry.get("generated_draft_id") or "")
        if status == "draft_created" and not generated_draft_id:
            findings.append(
                AuditFinding(
                    code="revision_request_generated_draft_missing",
                    path=str(artifact_path),
                    message=f"Revision request {revision_request_id} is draft_created but has no generated_draft_id.",
                )
            )
            continue
        if not generated_draft_id:
            continue
        generated_entry = draft_by_id.get(generated_draft_id)
        if generated_entry is None:
            findings.append(
                AuditFinding(
                    code="revision_request_generated_draft_missing",
                    path=str(drafts_index_path),
                    message=f"Revision request {revision_request_id} references missing generated draft {generated_draft_id}.",
                )
            )
            continue
        generated_path_value = generated_entry.get("path")
        if not isinstance(generated_path_value, str) or not generated_path_value:
            findings.append(
                AuditFinding(
                    code="invalid_revision_generated_draft_index_entry",
                    path=str(drafts_index_path),
                    message=f"Generated draft {generated_draft_id} has no artifact path.",
                )
            )
            continue
        generated_path = project_relative_artifact_path(store, generated_path_value)
        if generated_path is None:
            findings.append(
                AuditFinding(
                    code="unsafe_revision_generated_draft_path",
                    path=str(drafts_index_path),
                    message=f"Generated draft {generated_draft_id} artifact path escapes project root.",
                )
            )
            continue
        generated_artifact = read_json_file(generated_path, checked_paths=checked_paths, findings=findings)
        if generated_artifact is None:
            findings.append(
                AuditFinding(
                    code="missing_revision_generated_draft_artifact",
                    path=str(generated_path),
                    message=f"Generated draft {generated_draft_id} artifact is missing.",
                )
            )
            continue
        revision_meta = generated_artifact.get("revision") if isinstance(generated_artifact.get("revision"), dict) else {}
        if str(generated_artifact.get("draft_id") or "") != generated_draft_id:
            findings.append(
                AuditFinding(
                    code="revision_generated_draft_id_mismatch",
                    path=str(generated_path),
                    message="Generated revision draft artifact id does not match drafts index.",
                )
            )
        if str(revision_meta.get("revision_request_id") or "") != revision_request_id:
            findings.append(
                AuditFinding(
                    code="revision_generated_draft_request_mismatch",
                    path=str(generated_path),
                    message="Generated revision draft does not point back to the revision request.",
                )
            )
        if str(revision_meta.get("source_draft_id") or "") != source_draft_id:
            findings.append(
                AuditFinding(
                    code="revision_generated_draft_source_mismatch",
                    path=str(generated_path),
                    message="Generated revision draft source_draft_id does not match the request.",
                )
            )
        if str(revision_meta.get("source_review_id") or "") != review_id:
            findings.append(
                AuditFinding(
                    code="revision_generated_draft_review_mismatch",
                    path=str(generated_path),
                    message="Generated revision draft source_review_id does not match the request.",
                )
            )


def audit_checkpoints(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    checkpoint_dir = store.backups_dir / "checkpoints"
    checked_paths.append(str(checkpoint_dir))
    if not checkpoint_dir.exists():
        return
    for checkpoint_path in sorted(checkpoint_dir.glob("*.zip")):
        checked_paths.append(str(checkpoint_path))
        try:
            with zipfile.ZipFile(checkpoint_path, "r") as archive:
                names = set(archive.namelist())
                manifest = read_checkpoint_manifest(archive)
        except zipfile.BadZipFile:
            findings.append(
                AuditFinding(
                    code="invalid_checkpoint_zip",
                    path=str(checkpoint_path),
                    message="Checkpoint ZIP cannot be opened.",
                )
            )
            continue
        if "data/secrets.local.json" in names and not manifest.get("include_secrets"):
            findings.append(
                AuditFinding(
                    code="secrets_in_checkpoint",
                    path=str(checkpoint_path),
                    message="Default checkpoints must not include data/secrets.local.json.",
                )
            )


def read_checkpoint_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    if "checkpoint_manifest.json" not in archive.namelist():
        return {}
    try:
        value = json.loads(archive.read("checkpoint_manifest.json").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def audit_draft_confirmed_consistency(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    drafts_index_path = store.data_dir / "drafts_index.json"
    confirmed_index_path = store.data_dir / "confirmed_chapters.json"
    confirmed_dir = store.data_dir / "confirmed_chapters"
    commit_log_path = store.data_dir / "commit_log.json"
    drafts_index = read_json_file(drafts_index_path, checked_paths=checked_paths, findings=findings)
    confirmed_index = read_json_file(confirmed_index_path, checked_paths=checked_paths, findings=findings)
    commit_log = read_json_file(commit_log_path, checked_paths=checked_paths, findings=findings)
    draft_entries = list_items(drafts_index, "drafts")
    confirmed_entries = list_items(confirmed_index, "chapters")
    commit_entries = list_items(commit_log, "commits")
    draft_by_id = {str(item.get("draft_id")): item for item in draft_entries if item.get("draft_id")}
    confirmed_by_draft = {str(item.get("source_draft_id")): item for item in confirmed_entries if item.get("source_draft_id")}
    committed_log_draft_ids = {str(item.get("draft_id")) for item in commit_entries if item.get("draft_id")}
    confirmed_paths = {normalize_project_path(str(item.get("path"))) for item in confirmed_entries if item.get("path")}

    checked_paths.append(str(confirmed_dir))
    if confirmed_dir.exists():
        for artifact_path in sorted(confirmed_dir.glob("*.json")):
            relative = artifact_path.relative_to(store.root).as_posix()
            checked_paths.append(str(artifact_path))
            if relative not in confirmed_paths:
                findings.append(
                    AuditFinding(
                        code="orphan_confirmed_artifact",
                        path=str(artifact_path),
                        message="Confirmed artifact is not referenced by data/confirmed_chapters.json.",
                    )
                )

    for draft_id, draft_entry in draft_by_id.items():
        status = str(draft_entry.get("status") or "")
        if status == "committed" and draft_id not in confirmed_by_draft:
            findings.append(
                AuditFinding(
                    code="committed_draft_without_confirmed_chapter",
                    path=str(drafts_index_path),
                    message=f"Draft {draft_id} is marked committed but has no confirmed chapter index entry.",
                )
            )

    for entry in confirmed_entries:
        chapter_id = str(entry.get("chapter_id") or "")
        source_draft_id = str(entry.get("source_draft_id") or "")
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            findings.append(
                AuditFinding(
                    code="invalid_confirmed_index_entry",
                    path=str(confirmed_index_path),
                    message=f"Confirmed chapter {chapter_id or '<unknown>'} has no artifact path.",
                )
            )
            continue
        artifact_path = (store.root / path_value).resolve()
        try:
            artifact_path.relative_to(store.root.resolve())
        except ValueError:
            findings.append(
                AuditFinding(
                    code="unsafe_confirmed_artifact_path",
                    path=str(confirmed_index_path),
                    message=f"Confirmed chapter {chapter_id or '<unknown>'} artifact path escapes project root.",
                )
            )
            continue
        artifact = read_json_file(artifact_path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            findings.append(
                AuditFinding(
                    code="missing_confirmed_artifact",
                    path=str(artifact_path),
                    message=f"Confirmed chapter {chapter_id or '<unknown>'} artifact is missing.",
                )
            )
            continue
        if str(artifact.get("chapter_id") or "") != chapter_id:
            findings.append(
                AuditFinding(
                    code="confirmed_chapter_id_mismatch",
                    path=str(artifact_path),
                    message="Confirmed artifact chapter_id does not match index entry.",
                )
            )
        if source_draft_id not in draft_by_id:
            findings.append(
                AuditFinding(
                    code="confirmed_source_draft_missing",
                    path=str(confirmed_index_path),
                    message=f"Confirmed chapter {chapter_id} references missing draft {source_draft_id}.",
                )
            )
        elif str(draft_by_id[source_draft_id].get("status") or "") != "committed":
            findings.append(
                AuditFinding(
                    code="confirmed_source_draft_not_committed",
                    path=str(confirmed_index_path),
                    message=f"Confirmed chapter {chapter_id} source draft is not marked committed.",
                )
            )
        if source_draft_id and source_draft_id not in committed_log_draft_ids:
            findings.append(
                AuditFinding(
                    code="confirmed_without_commit_log",
                    path=str(commit_log_path),
                    message=f"Confirmed chapter {chapter_id} has no commit log entry for draft {source_draft_id}.",
                )
            )


def audit_provider_adapter_config(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    checked_paths.append("provider_adapter_config")
    config = read_json_file(store.config_path, checked_paths=checked_paths, findings=findings)
    roles = config.get("model_roles") if isinstance(config, dict) and isinstance(config.get("model_roles"), dict) else {}
    secrets = store.read_secrets() if store.secrets_path.exists() else {}
    for role, raw_role_config in roles.items():
        if not isinstance(raw_role_config, dict):
            continue
        if "api_key" in raw_role_config:
            findings.append(
                AuditFinding(
                    code="raw_provider_api_key_in_config",
                    path=str(store.config_path),
                    message=f"Role {role} stores raw api_key in config.",
                )
            )
        settings = raw_role_config.get("settings")
        if isinstance(settings, dict) and "api_key" in settings:
            findings.append(
                AuditFinding(
                    code="raw_provider_api_key_in_config",
                    path=str(store.config_path),
                    message=f"Role {role} stores raw api_key in settings.",
                )
            )
        try:
            role_config = ModelRoleConfig.from_mapping(str(role), raw_role_config)
        except ValueError:
            findings.append(
                AuditFinding(
                    code="provider_invalid_role_config",
                    path=str(store.config_path),
                    message=f"Role {role} has invalid provider configuration.",
                )
            )
            continue
        if not role_config.provider:
            continue
        adapter = get_provider_adapter(role_config.provider)
        if adapter is None:
            findings.append(
                AuditFinding(
                    code="provider_adapter_unregistered",
                    path=str(store.config_path),
                    message=f"Role {role} uses unregistered provider adapter {role_config.provider!r}.",
                )
            )
            continue
        if not adapter.enabled:
            findings.append(
                AuditFinding(
                    code="provider_adapter_disabled",
                    path=str(store.config_path),
                    message=f"Role {role} uses disabled provider adapter {role_config.provider!r}; audit did not test network.",
                )
            )
        real_generation_enabled = bool(role_config.settings.get(REAL_GENERATION_FLAG))
        if real_generation_enabled and (str(role) != "writer" or role_config.provider != CHUTES_PROVIDER_ID):
            findings.append(
                AuditFinding(
                    code="real_generation_unsupported",
                    path=str(store.config_path),
                    message="Real generation is only allowed for writer with chutes_openai in this phase.",
                )
            )
        if adapter.requires_secret and not role_config.api_key_ref:
            findings.append(
                AuditFinding(
                    code="provider_missing_secret_ref",
                    path=str(store.config_path),
                    message=f"Role {role} provider {role_config.provider!r} requires project_secret.<name>.",
                )
            )
            if real_generation_enabled:
                findings.append(
                    AuditFinding(
                        code="real_generation_enabled_missing_secret",
                        path=str(store.config_path),
                        message=f"Role {role} has real generation enabled but no api_key_ref.",
                    )
                )
        if role_config.api_key_ref:
            try:
                secret_name = role_config.secret_name()
            except ValueError:
                findings.append(
                    AuditFinding(
                        code="provider_invalid_secret_ref",
                        path=str(store.config_path),
                        message=f"Role {role} has invalid api_key_ref.",
                    )
                )
                continue
            if secret_name not in secrets or not str(secrets.get(secret_name) or ""):
                findings.append(
                    AuditFinding(
                        code="provider_missing_secret",
                        path=str(store.config_path),
                        message=f"Role {role} references a missing or empty project secret.",
                    )
                )
                if real_generation_enabled:
                    findings.append(
                        AuditFinding(
                            code="real_generation_enabled_missing_secret",
                            path=str(store.config_path),
                            message=f"Role {role} has real generation enabled but the referenced secret is missing or empty.",
                        )
                    )


def read_json_file(path: Path, *, checked_paths: list[str], findings: list[AuditFinding]) -> dict[str, Any] | None:
    checked_paths.append(str(path))
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        findings.append(AuditFinding(code="invalid_json", path=str(path), message="JSON file cannot be parsed."))
        return None
    return value if isinstance(value, dict) else None


def list_items(source: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    value = source.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalize_project_path(value: str) -> str:
    return value.replace("\\", "/")


def project_relative_artifact_path(store: ProjectStore, value: str) -> Path | None:
    try:
        path = (store.root / value).resolve()
        path.relative_to(store.root.resolve())
    except (OSError, ValueError):
        return None
    return path


def audit_public_state(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    checked_paths.append("public_project_state")
    text = json.dumps(public_project_state(store, initialize=False), ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                AuditFinding(
                    code="possible_secret_in_public_state",
                    path="public_project_state",
                    message=f"Matched {pattern.pattern}",
                )
            )
            break
    for pattern in (re.compile(r"\bprompt\b", re.IGNORECASE), re.compile(r"\bcontent\b", re.IGNORECASE)):
        if pattern.search(text):
            findings.append(
                AuditFinding(
                    code="possible_prompt_or_content_in_public_state",
                    path="public_project_state",
                    message=f"Matched {pattern.pattern}",
                )
            )
            break
