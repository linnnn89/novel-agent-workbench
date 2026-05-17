from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
    audit_checkpoints(store, checked_paths=checked_paths, findings=findings)
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


def audit_public_state(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    checked_paths.append("public_project_state")
    text = json.dumps(public_project_state(store), ensure_ascii=False, sort_keys=True)
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
