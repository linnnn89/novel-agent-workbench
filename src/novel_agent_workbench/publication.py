from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audit import audit_project
from .storage import InvalidProjectIdError, ProjectStore


REQUIRED_GITIGNORE_PATTERNS = [
    "workspace_projects/",
    "secrets.local.json",
    "*.local.json",
    ".env",
    ".env.*",
    "exports/",
    "backups/",
    "run_logs/",
    "usage_logs/",
    "*.log",
    "build/",
    "dist/",
    "*.egg-info/",
    "*.spec",
    ".coverage",
    "htmlcov/",
]

BLOCKING_PROJECT_AUDIT_CODES = {
    "non_publishable_corpus_sample_present",
    "corpus_sample_source_path_stored",
    "corpus_boundary_source_path_stored",
    "corpus_boundary_text_field_stored",
    "corpus_profile_source_path_stored",
    "corpus_profile_candidate_names_stored",
    "provider_smoke_test_text_stored",
    "provider_smoke_test_status_invalid",
    "provider_smoke_test_passed_state_invalid",
    "provider_smoke_test_classification_invalid",
    "provider_smoke_test_safety_flag_invalid",
}

NON_PUBLISHING_PROJECT_AUDIT_WARNING_CODES = {
    "provider_adapter_disabled",
    "provider_missing_secret",
    "provider_missing_secret_ref",
}

SKIP_REPO_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "workspace_projects",
    "app_projects",
    "exports",
    "backups",
    "run_logs",
    "usage_logs",
    "build",
    "dist",
    "htmlcov",
}


@dataclass(frozen=True, slots=True)
class PrepublishFinding:
    code: str
    path: str
    message: str
    severity: str = "blocker"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepublish_check(repo_root: str | Path, *, projects_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    project_root = Path(projects_root).resolve() if projects_root is not None else root / "workspace_projects"
    checked_paths: list[str] = []
    findings: list[PrepublishFinding] = []
    check_gitignore(root, checked_paths=checked_paths, findings=findings)
    check_repo_tree(root, checked_paths=checked_paths, findings=findings)
    check_projects(project_root, checked_paths=checked_paths, findings=findings)
    return {
        "ok": not any(finding.severity == "blocker" for finding in findings),
        "repo_root": str(root),
        "projects_root": str(project_root),
        "findings": [finding.to_dict() for finding in findings],
        "checked_paths": checked_paths,
        "summary": {
            "finding_count": len(findings),
            "blocker_count": sum(1 for finding in findings if finding.severity == "blocker"),
            "warning_count": sum(1 for finding in findings if finding.severity == "warning"),
        },
    }


def check_gitignore(root: Path, *, checked_paths: list[str], findings: list[PrepublishFinding]) -> None:
    path = root / ".gitignore"
    checked_paths.append(str(path))
    if not path.exists():
        findings.append(
            PrepublishFinding(
                code="gitignore_missing",
                path=str(path),
                message=".gitignore is required before GitHub publication.",
            )
        )
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = {line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")}
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in lines:
            findings.append(
                PrepublishFinding(
                    code="gitignore_required_pattern_missing",
                    path=str(path),
                    message=f"Missing required ignore pattern: {pattern}",
                )
            )


def check_repo_tree(root: Path, *, checked_paths: list[str], findings: list[PrepublishFinding]) -> None:
    checked_paths.append(str(root))
    if not root.exists():
        findings.append(
            PrepublishFinding(
                code="repo_root_missing",
                path=str(root),
                message="Repository root does not exist.",
            )
        )
        return
    for path in walk_publishable_files(root):
        relative = path.relative_to(root).as_posix()
        checked_paths.append(str(path))
        if path.name == "secrets.local.json":
            findings.append(
                PrepublishFinding(
                    code="repo_secret_file_present",
                    path=relative,
                    message="secrets.local.json must not be in publishable source tree.",
                )
            )
        if path.name.startswith(".env"):
            findings.append(
                PrepublishFinding(
                    code="repo_env_file_present",
                    path=relative,
                    message=".env files must not be in publishable source tree.",
                )
            )
        if "corpus_samples" in path.parts:
            findings.append(
                PrepublishFinding(
                    code="repo_corpus_sample_present",
                    path=relative,
                    message="Real-corpus samples must not be in publishable source tree.",
                )
            )


def walk_publishable_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_REPO_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def check_projects(projects_root: Path, *, checked_paths: list[str], findings: list[PrepublishFinding]) -> None:
    checked_paths.append(str(projects_root))
    if not projects_root.exists():
        return
    for child in sorted(projects_root.iterdir()):
        if not child.is_dir():
            continue
        project_id = child.name
        if (child / "data" / "corpus_samples").exists():
            findings.append(
                PrepublishFinding(
                    code="runtime_corpus_sample_present",
                    path=str(child / "data" / "corpus_samples"),
                    message=f"Project {project_id} contains test-only corpus samples.",
                )
            )
        if not (child / "project.json").exists():
            continue
        try:
            store = ProjectStore.open(projects_root, project_id)
        except InvalidProjectIdError as exc:
            findings.append(
                PrepublishFinding(
                    code="runtime_project_id_invalid",
                    path=str(child),
                    message=str(exc),
                )
            )
            continue
        audit = audit_project(store)
        checked_paths.extend(str(item) for item in audit.get("checked_paths", []) if isinstance(item, str))
        for finding in audit.get("findings", []):
            if not isinstance(finding, dict):
                continue
            finding_code = str(finding.get("code") or "")
            if finding_code in NON_PUBLISHING_PROJECT_AUDIT_WARNING_CODES:
                continue
            findings.append(
                PrepublishFinding(
                    code=f"project_audit_{finding_code}",
                    path=str(finding.get("path") or child),
                    message=f"Project {project_id}: {finding.get('message') or finding_code}",
                    severity=project_audit_severity(finding_code),
                )
            )


def project_audit_severity(code: str) -> str:
    if code in BLOCKING_PROJECT_AUDIT_CODES:
        return "blocker"
    if code.startswith("possible_secret"):
        return "blocker"
    if code.startswith("possible_prompt"):
        return "blocker"
    if code.startswith("possible_content"):
        return "blocker"
    return "warning"
