from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .providers import (
    ModelRoleConfig,
    get_model_role_config,
    get_provider_adapter,
    safe_url_host,
)
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
    check_text_file(
        store.data_dir / "memory_bank.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_prompt_in_memory_bank", PROMPT_PATTERNS),
            ("possible_secret_in_memory_bank", SECRET_PATTERNS),
        ],
    )
    audit_planning_library(store, checked_paths=checked_paths, findings=findings)
    audit_context_previews(store, checked_paths=checked_paths, findings=findings)
    audit_corpus_boundaries(store, checked_paths=checked_paths, findings=findings)
    audit_corpus_profiles(store, checked_paths=checked_paths, findings=findings)
    audit_corpus_samples(store, checked_paths=checked_paths, findings=findings)
    audit_self_style_baselines(store, checked_paths=checked_paths, findings=findings)
    audit_draft_style_checks(store, checked_paths=checked_paths, findings=findings)
    audit_style_suggestions(store, checked_paths=checked_paths, findings=findings)
    audit_manual_rewrite_tasks(store, checked_paths=checked_paths, findings=findings)
    audit_manual_rewrite_comparisons(store, checked_paths=checked_paths, findings=findings)
    audit_review_handoffs(store, checked_paths=checked_paths, findings=findings)
    audit_final_assembly_gates(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_runbooks(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_authorizations(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_execution_preflights(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_execution_attempts(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_real_execution_readiness(store, checked_paths=checked_paths, findings=findings)
    audit_final_provider_real_executions(store, checked_paths=checked_paths, findings=findings)
    audit_provider_smoke_tests(store, checked_paths=checked_paths, findings=findings)
    audit_formal_context_plans(store, checked_paths=checked_paths, findings=findings)
    audit_formal_context_tasks(store, checked_paths=checked_paths, findings=findings)
    audit_memory_apply_previews(store, checked_paths=checked_paths, findings=findings)
    audit_reviews(store, checked_paths=checked_paths, findings=findings)
    audit_revision_requests(store, checked_paths=checked_paths, findings=findings)
    audit_revision_consistency(store, checked_paths=checked_paths, findings=findings)
    audit_context_generation_drafts(store, checked_paths=checked_paths, findings=findings)
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


def audit_planning_library(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    path = store.data_dir / "planning_library.json"
    check_text_file(
        path,
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_planning_library", SECRET_PATTERNS)],
    )
    library = read_json_file(path, checked_paths=checked_paths, findings=findings)
    items = list_items(library, "items")
    active_reference_ids = (
        library.get("active_reference_ids")
        if isinstance(library, dict) and isinstance(library.get("active_reference_ids"), list)
        else []
    )
    expected_ids: list[str] = []
    seen_ids: set[str] = set()
    for item in items:
        planning_id = str(item.get("planning_id") or item.get("id") or "")
        if not planning_id:
            findings.append(
                AuditFinding(
                    code="planning_library_item_missing_id",
                    path=str(path),
                    message="Planning Library item has no planning_id.",
                )
            )
            continue
        if planning_id in seen_ids:
            findings.append(
                AuditFinding(
                    code="planning_library_duplicate_id",
                    path=str(path),
                    message=f"Planning Library item id is duplicated: {planning_id}",
                )
            )
        seen_ids.add(planning_id)
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        if enabled and bool(item.get("active")):
            expected_ids.append(planning_id)
        safety = item.get("safety") if isinstance(item.get("safety"), dict) else {}
        if safety.get("provider_called") is not False or safety.get("auto_commit") is not False:
            findings.append(
                AuditFinding(
                    code="planning_library_safety_flag_invalid",
                    path=str(path),
                    message="Planning Library items must remain manual/local and must not auto-commit.",
                )
            )
    if [str(item) for item in active_reference_ids] != expected_ids:
        findings.append(
            AuditFinding(
                code="planning_library_active_reference_ids_stale",
                path=str(path),
                message="Planning Library active_reference_ids does not match active enabled items.",
            )
        )


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
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is not None:
            audit_review_manual_rewrite_gate(store, artifact, path=str(path), checked_paths=checked_paths, findings=findings)


def audit_review_manual_rewrite_gate(
    store: ProjectStore,
    review: dict[str, Any],
    *,
    path: str,
    checked_paths: list[str],
    findings: list[AuditFinding],
) -> None:
    draft_id = str(review.get("draft_id") or "")
    if not draft_id:
        return
    draft_entry = None
    draft_index = read_json_file(store.data_dir / "drafts_index.json", checked_paths=checked_paths, findings=findings)
    for item in list_items(draft_index, "drafts"):
        if str(item.get("draft_id") or "") == draft_id:
            draft_entry = item
            break
    if draft_entry is None:
        return
    path_value = draft_entry.get("path")
    if not isinstance(path_value, str) or not path_value:
        return
    draft_path = project_relative_artifact_path(store, path_value)
    if draft_path is None:
        return
    draft = read_json_file(draft_path, checked_paths=checked_paths, findings=findings)
    manual_rewrite = draft.get("manual_rewrite") if isinstance(draft, dict) and isinstance(draft.get("manual_rewrite"), dict) else {}
    if str(manual_rewrite.get("mode") or "") != "manual_rewrite_draft_candidate":
        return
    request_summary = review.get("request_summary") if isinstance(review.get("request_summary"), dict) else {}
    gate = request_summary.get("manual_rewrite_review_gate") if isinstance(request_summary.get("manual_rewrite_review_gate"), dict) else {}
    if gate.get("required") is not True or gate.get("allowed") is not True:
        findings.append(
            AuditFinding(
                code="manual_rewrite_review_gate_missing",
                path=path,
                message="Review of a manual rewrite submitted draft must record an allowed manual rewrite review gate.",
            )
        )
        return
    if str(gate.get("matched_gate") or "") not in {"selected_for_review_comparison", "pending_review_handoff"}:
        findings.append(
            AuditFinding(
                code="manual_rewrite_review_gate_invalid",
                path=path,
                message="Manual rewrite review gate must be selected_for_review comparison or pending_review handoff.",
            )
        )


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


def audit_corpus_profiles(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_corpus_profile", PROMPT_PATTERNS),
        ("possible_secret_in_corpus_profile", SECRET_PATTERNS),
        ("possible_content_in_corpus_profile", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "corpus_profiles_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    profiles_dir = store.data_dir / "corpus_profiles"
    checked_paths.append(str(profiles_dir))
    if not profiles_dir.exists():
        return
    for path in sorted(profiles_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        source = artifact.get("source") if isinstance(artifact.get("source"), dict) else {}
        if source.get("original_path_stored") or "path" in source:
            findings.append(
                AuditFinding(
                    code="corpus_profile_source_path_stored",
                    path=str(path),
                    message="Corpus profile artifact must not store external source paths.",
                )
            )
        name_candidates = (
            artifact.get("name_candidates") if isinstance(artifact.get("name_candidates"), dict) else {}
        )
        if name_candidates.get("top_included") or "top" in name_candidates:
            findings.append(
                AuditFinding(
                    code="corpus_profile_candidate_names_stored",
                    path=str(path),
                    message="Persistent corpus profile artifacts must not store candidate-name text.",
                )
            )


def audit_corpus_boundaries(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_corpus_boundary", PROMPT_PATTERNS),
        ("possible_secret_in_corpus_boundary", SECRET_PATTERNS),
        ("possible_content_in_corpus_boundary", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "corpus_boundaries_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    boundaries_dir = store.data_dir / "corpus_boundaries"
    checked_paths.append(str(boundaries_dir))
    if not boundaries_dir.exists():
        return
    for path in sorted(boundaries_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        source = artifact.get("source") if isinstance(artifact.get("source"), dict) else {}
        if source.get("original_path_stored") or "path" in source:
            findings.append(
                AuditFinding(
                    code="corpus_boundary_source_path_stored",
                    path=str(path),
                    message="Corpus boundary artifact must not store external source paths.",
                )
            )
        if contains_forbidden_corpus_boundary_key(artifact):
            findings.append(
                AuditFinding(
                    code="corpus_boundary_text_field_stored",
                    path=str(path),
                    message="Corpus boundary artifact must not store heading text or excerpts.",
                )
            )


def contains_forbidden_corpus_boundary_key(value: object) -> bool:
    forbidden = {"heading_text", "excerpt", "source_text", "chapter_text"}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_corpus_boundary_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_corpus_boundary_key(item) for item in value)
    return False


def audit_corpus_samples(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    check_text_file(
        store.data_dir / "corpus_samples_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_corpus_sample_index", SECRET_PATTERNS)],
    )
    samples_dir = store.data_dir / "corpus_samples"
    checked_paths.append(str(samples_dir))
    if not samples_dir.exists():
        return
    for path in sorted(samples_dir.glob("*.json")):
        check_text_file(
            path,
            checked_paths=checked_paths,
            findings=findings,
            pattern_groups=[("possible_secret_in_corpus_sample", SECRET_PATTERNS)],
        )
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if artifact.get("publish_blocker") is True or artifact.get("test_only") is True:
            findings.append(
                AuditFinding(
                    code="non_publishable_corpus_sample_present",
                    path=str(path),
                    message="Temporary real-corpus sample must be removed before GitHub publication.",
                )
            )
        source = artifact.get("source") if isinstance(artifact.get("source"), dict) else {}
        if source.get("source_path_stored") or "path" in source:
            findings.append(
                AuditFinding(
                    code="corpus_sample_source_path_stored",
                    path=str(path),
                    message="Corpus sample artifact must not store external source paths.",
                )
            )


def audit_self_style_baselines(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    check_text_file(
        store.data_dir / "style_baselines_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_self_style_baseline_index", SECRET_PATTERNS)],
    )
    baselines_dir = store.data_dir / "style_baselines"
    checked_paths.append(str(baselines_dir))
    if not baselines_dir.exists():
        return
    for path in sorted(baselines_dir.glob("*.json")):
        check_text_file(
            path,
            checked_paths=checked_paths,
            findings=findings,
            pattern_groups=[("possible_secret_in_self_style_baseline", SECRET_PATTERNS)],
        )
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="self_style_baseline_text_stored",
                    path=str(path),
                    message="Self style baseline artifacts must store statistics only, not chapter/prompt text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("external_corpus_used") is not False or safety.get("provider_called") is not False:
            findings.append(
                AuditFinding(
                    code="self_style_baseline_boundary_invalid",
                    path=str(path),
                    message="Self style baseline must be local-only and must not use external corpora or Providers.",
                )
            )
def audit_draft_style_checks(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    check_text_file(
        store.data_dir / "style_checks_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_draft_style_check_index", SECRET_PATTERNS)],
    )
    checks_dir = store.data_dir / "style_checks"
    checked_paths.append(str(checks_dir))
    if not checks_dir.exists():
        return
    for path in sorted(checks_dir.glob("*.json")):
        check_text_file(
            path,
            checked_paths=checked_paths,
            findings=findings,
            pattern_groups=[("possible_secret_in_draft_style_check", SECRET_PATTERNS)],
        )
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="draft_style_check_text_stored",
                    path=str(path),
                    message="Draft style check artifacts must store statistics only, not draft/prompt text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("external_corpus_used") is not False or safety.get("provider_called") is not False:
            findings.append(
                AuditFinding(
                    code="draft_style_check_boundary_invalid",
                    path=str(path),
                    message="Draft style check must be local-only and must not use external corpora or Providers.",
                )
            )
        if safety.get("auto_revision") is not False or safety.get("auto_commit") is not False:
            findings.append(
                AuditFinding(
                    code="draft_style_check_side_effect_flag_invalid",
                    path=str(path),
                    message="Draft style check must not auto-revise or auto-commit.",
                )
            )


def audit_style_suggestions(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    check_text_file(
        store.data_dir / "style_suggestions_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[("possible_secret_in_style_suggestion_index", SECRET_PATTERNS)],
    )
    suggestions_dir = store.data_dir / "style_suggestions"
    checked_paths.append(str(suggestions_dir))
    if not suggestions_dir.exists():
        return
    for path in sorted(suggestions_dir.glob("*.json")):
        check_text_file(
            path,
            checked_paths=checked_paths,
            findings=findings,
            pattern_groups=[
                ("possible_prompt_in_style_suggestion", PROMPT_PATTERNS),
                ("possible_secret_in_style_suggestion", SECRET_PATTERNS),
            ],
        )
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="style_suggestion_text_stored",
                    path=str(path),
                    message="Style suggestion artifacts must not store draft, prompt, or corpus text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("external_corpus_used") is not False or safety.get("provider_called") is not False:
            findings.append(
                AuditFinding(
                    code="style_suggestion_boundary_invalid",
                    path=str(path),
                    message="Style suggestions must be local-only and must not use external corpora or Providers.",
                )
            )
        if safety.get("auto_revision") is not False or safety.get("auto_commit") is not False:
            findings.append(
                AuditFinding(
                    code="style_suggestion_side_effect_flag_invalid",
                    path=str(path),
                    message="Style suggestions must not auto-revise or auto-commit.",
                )
            )


def audit_manual_rewrite_tasks(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_manual_rewrite_task", PROMPT_PATTERNS),
        ("possible_secret_in_manual_rewrite_task", SECRET_PATTERNS),
        ("possible_content_in_manual_rewrite_task", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "manual_rewrite_tasks_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    tasks_dir = store.data_dir / "manual_rewrite_tasks"
    checked_paths.append(str(tasks_dir))
    if not tasks_dir.exists():
        return
    for path in sorted(tasks_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="manual_rewrite_task_text_stored",
                    path=str(path),
                    message="Manual rewrite tasks must not store draft, prompt, or corpus text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("provider_called") is not False or safety.get("external_corpus_used") is not False:
            findings.append(
                AuditFinding(
                    code="manual_rewrite_task_boundary_invalid",
                    path=str(path),
                    message="Manual rewrite tasks must be local-only and must not use Providers or external corpora.",
                )
            )
        if (
            safety.get("auto_apply") is not False
            or safety.get("auto_generate_draft") is not False
            or safety.get("auto_commit") is not False
        ):
            findings.append(
                AuditFinding(
                    code="manual_rewrite_task_side_effect_flag_invalid",
                    path=str(path),
                    message="Manual rewrite tasks must not auto-apply, auto-generate, or auto-commit.",
                )
            )


def audit_manual_rewrite_comparisons(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_manual_rewrite_comparison", PROMPT_PATTERNS),
        ("possible_secret_in_manual_rewrite_comparison", SECRET_PATTERNS),
        ("possible_content_in_manual_rewrite_comparison", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "manual_rewrite_comparisons_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    comparisons_dir = store.data_dir / "manual_rewrite_comparisons"
    checked_paths.append(str(comparisons_dir))
    if not comparisons_dir.exists():
        return
    for path in sorted(comparisons_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="manual_rewrite_comparison_text_stored",
                    path=str(path),
                    message="Manual rewrite comparisons must not store draft, prompt, or corpus text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("provider_called") is not False or safety.get("external_corpus_used") is not False:
            findings.append(
                AuditFinding(
                    code="manual_rewrite_comparison_boundary_invalid",
                    path=str(path),
                    message="Manual rewrite comparisons must be local-only and must not use Providers or external corpora.",
                )
            )
        if (
            safety.get("auto_apply") is not False
            or safety.get("auto_generate_draft") is not False
            or safety.get("auto_revision_request") is not False
            or safety.get("auto_commit") is not False
        ):
            findings.append(
                AuditFinding(
                    code="manual_rewrite_comparison_side_effect_flag_invalid",
                    path=str(path),
                    message="Manual rewrite comparisons must not auto-apply, auto-generate, auto-revise, or auto-commit.",
                )
            )
        if (
            safety.get("confirmed_touched") is not False
            or safety.get("memory_bank_touched") is not False
            or safety.get("rag_touched") is not False
            or safety.get("exports_touched") is not False
        ):
            findings.append(
                AuditFinding(
                    code="manual_rewrite_comparison_formal_context_flag_invalid",
                    path=str(path),
                    message="Manual rewrite comparisons must not touch confirmed chapters, Memory Bank, RAG, or exports.",
                )
            )


def audit_review_handoffs(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_review_handoff", PROMPT_PATTERNS),
        ("possible_secret_in_review_handoff", SECRET_PATTERNS),
        ("possible_content_in_review_handoff", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "review_handoffs_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    handoffs_dir = store.data_dir / "review_handoffs"
    checked_paths.append(str(handoffs_dir))
    if not handoffs_dir.exists():
        return
    for path in sorted(handoffs_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_self_style_text(artifact):
            findings.append(
                AuditFinding(
                    code="review_handoff_text_stored",
                    path=str(path),
                    message="Review handoffs must not store draft, prompt, or corpus text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        if safety.get("provider_called") is not False or safety.get("external_corpus_used") is not False:
            findings.append(
                AuditFinding(
                    code="review_handoff_boundary_invalid",
                    path=str(path),
                    message="Review handoffs must be local-only and must not use Providers or external corpora.",
                )
            )
        if (
            safety.get("auto_review") is not False
            or safety.get("auto_apply") is not False
            or safety.get("auto_generate_draft") is not False
            or safety.get("auto_revision_request") is not False
            or safety.get("auto_commit") is not False
        ):
            findings.append(
                AuditFinding(
                    code="review_handoff_side_effect_flag_invalid",
                    path=str(path),
                    message="Review handoffs must not auto-review, auto-generate, auto-revise, or auto-commit.",
                )
            )
        if (
            safety.get("confirmed_touched") is not False
            or safety.get("memory_bank_touched") is not False
            or safety.get("rag_touched") is not False
            or safety.get("exports_touched") is not False
        ):
            findings.append(
                AuditFinding(
                    code="review_handoff_formal_context_flag_invalid",
                    path=str(path),
                    message="Review handoffs must not touch confirmed chapters, Memory Bank, RAG, or exports.",
                )
            )


def audit_final_assembly_gates(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_assembly_gate", PROMPT_PATTERNS),
        ("possible_secret_in_final_assembly_gate", SECRET_PATTERNS),
        ("possible_content_in_final_assembly_gate", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_assembly_gates_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    gates_dir = store.data_dir / "final_assembly_gates"
    checked_paths.append(str(gates_dir))
    if not gates_dir.exists():
        return
    for path in sorted(gates_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_assembly_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_assembly_gate_text_stored",
                    path=str(path),
                    message="Final assembly gates must store digests and metadata only, not prompt/context text.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_assembly_gate_safety_flag_invalid",
                        path=str(path),
                        message=f"Final assembly gate safety flag must be false: {key}",
                    )
                )
        if str(artifact.get("status") or "") == "approved":
            approval = artifact.get("approval") if isinstance(artifact.get("approval"), dict) else {}
            if str(approval.get("status") or "") != "approved" or not str(approval.get("approved_at") or ""):
                findings.append(
                    AuditFinding(
                        code="final_assembly_gate_approval_invalid",
                        path=str(path),
                        message="Approved final assembly gate must contain approval metadata.",
                    )
                )


def contains_forbidden_final_assembly_text_key(value: object) -> bool:
    forbidden = {"prompt", "system_prompt", "text", "content", "context_text", "prompt_text", "chapter_text"}
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_assembly_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_assembly_text_key(item) for item in value)
    return False


def audit_final_provider_runbooks(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_runbook", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_runbook", SECRET_PATTERNS),
        ("possible_content_in_final_provider_runbook", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_runbooks_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    runbooks_dir = store.data_dir / "final_provider_runbooks"
    checked_paths.append(str(runbooks_dir))
    if not runbooks_dir.exists():
        return
    for path in sorted(runbooks_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_runbook_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_runbook_text_stored",
                    path=str(path),
                    message="Final Provider runbooks must store digests and metadata only, not prompt/context/chapter text.",
                )
            )
        if str(artifact.get("status") or "") != "pending_operator_authorization":
            findings.append(
                AuditFinding(
                    code="final_provider_runbook_status_invalid",
                    path=str(path),
                    message="Final Provider runbook status must remain pending_operator_authorization.",
                )
            )
        source_gate = artifact.get("source_gate") if isinstance(artifact.get("source_gate"), dict) else {}
        if str(source_gate.get("status") or "") != "approved" or not str(source_gate.get("approved_at") or ""):
            findings.append(
                AuditFinding(
                    code="final_provider_runbook_gate_not_approved",
                    path=str(path),
                    message="Final Provider runbooks must be derived from an approved final assembly gate.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "real_llm_called",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_provider_runbook_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider runbook safety flag must be false: {key}",
                    )
                )


def contains_forbidden_final_provider_runbook_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "raw_response",
        "request_body",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_runbook_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_runbook_text_key(item) for item in value)
    return False


def audit_final_provider_authorizations(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_authorization", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_authorization", SECRET_PATTERNS),
        ("possible_content_in_final_provider_authorization", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_authorizations_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    authorizations_dir = store.data_dir / "final_provider_authorizations"
    checked_paths.append(str(authorizations_dir))
    if not authorizations_dir.exists():
        return
    for path in sorted(authorizations_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_authorization_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_text_stored",
                    path=str(path),
                    message="Final Provider authorizations must store digests and metadata only, not prompt/context/chapter text.",
                )
            )
        if str(artifact.get("status") or "") != "authorized_pending_execution":
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_status_invalid",
                    path=str(path),
                    message="Final Provider authorization status must remain authorized_pending_execution.",
                )
            )
        source_gate = artifact.get("source_gate") if isinstance(artifact.get("source_gate"), dict) else {}
        if str(source_gate.get("status") or "") != "approved" or not str(source_gate.get("approved_at") or ""):
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_gate_not_approved",
                    path=str(path),
                    message="Final Provider authorizations must reference an approved source gate.",
                )
            )
        source_runbook = artifact.get("source_runbook") if isinstance(artifact.get("source_runbook"), dict) else {}
        if str(source_runbook.get("status") or "") != "pending_operator_authorization":
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_runbook_status_invalid",
                    path=str(path),
                    message="Final Provider authorizations must reference a pending operator runbook.",
                )
            )
        checkpoint = artifact.get("checkpoint") if isinstance(artifact.get("checkpoint"), dict) else {}
        if not str(checkpoint.get("checkpoint_id") or "") or checkpoint.get("include_secrets") is not False:
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_checkpoint_invalid",
                    path=str(path),
                    message="Final Provider authorization must record a no-secrets pre-authorization checkpoint.",
                )
            )
        execution_boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        if (
            execution_boundary.get("execution_started") is not False
            or execution_boundary.get("requires_separate_operator_execute_authorization") is not True
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_authorization_execution_boundary_invalid",
                    path=str(path),
                    message="Final Provider authorization must not start execution or enable the real Provider.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "real_llm_called",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_provider_authorization_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider authorization safety flag must be false: {key}",
                    )
                )


def contains_forbidden_final_provider_authorization_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "raw_response",
        "request_body",
        "plain_token",
        "token",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_authorization_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_authorization_text_key(item) for item in value)
    return False


def audit_final_provider_execution_preflights(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_execution_preflight", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_execution_preflight", SECRET_PATTERNS),
        ("possible_content_in_final_provider_execution_preflight", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_execution_preflights_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    preflights_dir = store.data_dir / "final_provider_execution_preflights"
    checked_paths.append(str(preflights_dir))
    if not preflights_dir.exists():
        return
    for path in sorted(preflights_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_execution_preflight_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_execution_preflight_text_stored",
                    path=str(path),
                    message="Final Provider execution preflights must store digests and metadata only, not prompt/context/chapter text.",
                )
            )
        status = str(artifact.get("status") or "")
        if status not in {"passed_pending_execute_authorization", "blocked"}:
            findings.append(
                AuditFinding(
                    code="final_provider_execution_preflight_status_invalid",
                    path=str(path),
                    message="Final Provider execution preflight status must be passed_pending_execute_authorization or blocked.",
                )
            )
        checks = artifact.get("check_results") if isinstance(artifact.get("check_results"), list) else []
        issues = [item for item in checks if isinstance(item, dict) and item.get("passed") is not True]
        if status == "passed_pending_execute_authorization" and issues:
            findings.append(
                AuditFinding(
                    code="final_provider_execution_preflight_passed_with_issues",
                    path=str(path),
                    message="Passed final Provider execution preflight must not contain failed checks.",
                )
            )
        if status == "blocked" and not issues:
            findings.append(
                AuditFinding(
                    code="final_provider_execution_preflight_blocked_without_issues",
                    path=str(path),
                    message="Blocked final Provider execution preflight must contain failed checks.",
                )
            )
        execution_boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        if (
            execution_boundary.get("preflight_only") is not True
            or execution_boundary.get("execution_started") is not False
            or execution_boundary.get("requires_separate_operator_execute_authorization") is not True
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_execution_preflight_boundary_invalid",
                    path=str(path),
                    message="Final Provider execution preflight must remain a preflight-only, no-execution artifact.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "real_llm_called",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_provider_execution_preflight_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider execution preflight safety flag must be false: {key}",
                    )
                )


def contains_forbidden_final_provider_execution_preflight_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "raw_response",
        "request_body",
        "plain_token",
        "token",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_execution_preflight_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_execution_preflight_text_key(item) for item in value)
    return False


def audit_final_provider_execution_attempts(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_execution_attempt", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_execution_attempt", SECRET_PATTERNS),
        ("possible_content_in_final_provider_execution_attempt", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_execution_attempts_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    attempts_dir = store.data_dir / "final_provider_execution_attempts"
    checked_paths.append(str(attempts_dir))
    if not attempts_dir.exists():
        return
    for path in sorted(attempts_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_execution_attempt_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_execution_attempt_text_stored",
                    path=str(path),
                    message="Final Provider execution attempts must store metadata only, not prompt/context/chapter text.",
                )
            )
        if str(artifact.get("status") or "") != "aborted_real_llm_disabled":
            findings.append(
                AuditFinding(
                    code="final_provider_execution_attempt_status_invalid",
                    path=str(path),
                    message="Final Provider execution attempt status must remain aborted_real_llm_disabled.",
                )
            )
        if str(artifact.get("abort_reason_code") or "") != "real_llm_disabled_by_policy":
            findings.append(
                AuditFinding(
                    code="final_provider_execution_attempt_abort_reason_invalid",
                    path=str(path),
                    message="Final Provider execution attempt must record real_llm_disabled_by_policy.",
                )
            )
        source_preflight = artifact.get("source_preflight") if isinstance(artifact.get("source_preflight"), dict) else {}
        if str(source_preflight.get("status") or "") != "passed_pending_execute_authorization" or int(source_preflight.get("issue_count") or 0) != 0:
            findings.append(
                AuditFinding(
                    code="final_provider_execution_attempt_preflight_invalid",
                    path=str(path),
                    message="Final Provider execution attempts must reference a passed zero-issue preflight.",
                )
            )
        execution_boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        if (
            execution_boundary.get("stub_only") is not True
            or execution_boundary.get("execution_started") is not False
            or execution_boundary.get("execution_aborted") is not True
            or execution_boundary.get("provider_called") is not False
            or execution_boundary.get("requires_explicit_real_llm_authorization") is not True
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_execution_attempt_boundary_invalid",
                    path=str(path),
                    message="Final Provider execution attempt must remain a fail-closed abort stub.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "real_llm_called",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_provider_execution_attempt_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider execution attempt safety flag must be false: {key}",
                    )
                )


def contains_forbidden_final_provider_execution_attempt_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "raw_response",
        "request_body",
        "plain_token",
        "token",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_execution_attempt_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_execution_attempt_text_key(item) for item in value)
    return False


def audit_final_provider_real_execution_readiness(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_real_execution_readiness", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_real_execution_readiness", SECRET_PATTERNS),
        ("possible_content_in_final_provider_real_execution_readiness", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_real_execution_readiness_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    readiness_dir = store.data_dir / "final_provider_real_execution_readiness"
    checked_paths.append(str(readiness_dir))
    if not readiness_dir.exists():
        return
    for path in sorted(readiness_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_real_execution_readiness_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_text_stored",
                    path=str(path),
                    message="Final Provider real execution readiness must store metadata only, not prompt/context/chapter text.",
                )
            )
        status = str(artifact.get("status") or "")
        if status not in {"ready_for_manual_real_llm_authorization", "blocked"}:
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_status_invalid",
                    path=str(path),
                    message="Final Provider real execution readiness status is invalid.",
                )
            )
        issue_count = int(artifact.get("issue_count") or 0)
        if status == "ready_for_manual_real_llm_authorization" and issue_count != 0:
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_ready_with_issues",
                    path=str(path),
                    message="Ready real execution readiness reports must have zero issues.",
                )
            )
        if status == "blocked" and issue_count == 0:
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_blocked_without_issues",
                    path=str(path),
                    message="Blocked real execution readiness reports must record at least one issue.",
                )
            )
        source_attempt = artifact.get("source_attempt") if isinstance(artifact.get("source_attempt"), dict) else {}
        if (
            str(source_attempt.get("status") or "") != "aborted_real_llm_disabled"
            or str(source_attempt.get("abort_reason_code") or "") != "real_llm_disabled_by_policy"
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_attempt_invalid",
                    path=str(path),
                    message="Real execution readiness must derive from a fail-closed aborted execution attempt.",
                )
            )
        execution_boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        if (
            execution_boundary.get("readiness_only") is not True
            or execution_boundary.get("execution_started") is not False
            or execution_boundary.get("provider_called") is not False
            or execution_boundary.get("real_llm_called") is not False
            or execution_boundary.get("requires_explicit_real_llm_authorization") is not True
            or execution_boundary.get("requires_key_before_execution") is not True
            or execution_boundary.get("requires_network_before_execution") is not True
            or execution_boundary.get("writes_draft") is not False
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_boundary_invalid",
                    path=str(path),
                    message="Real execution readiness must remain no-network and no-execution.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        for key in (
            "provider_called",
            "real_llm_called",
            "secret_value_read",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ):
            if safety.get(key) is not False:
                findings.append(
                    AuditFinding(
                        code="final_provider_real_execution_readiness_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider real execution readiness safety flag must be false: {key}",
                    )
                )


def contains_forbidden_final_provider_real_execution_readiness_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "raw_response",
        "request_body",
        "plain_token",
        "token",
        "api_key",
        "secret_value",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_real_execution_readiness_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_real_execution_readiness_text_key(item) for item in value)
    return False


def audit_final_provider_real_executions(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    pattern_groups = [
        ("possible_prompt_in_final_provider_real_execution", PROMPT_PATTERNS),
        ("possible_secret_in_final_provider_real_execution", SECRET_PATTERNS),
        ("possible_content_in_final_provider_real_execution", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "final_provider_real_executions_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    executions_dir = store.data_dir / "final_provider_real_executions"
    checked_paths.append(str(executions_dir))
    if not executions_dir.exists():
        return
    for path in sorted(executions_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_final_provider_real_execution_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_text_stored",
                    path=str(path),
                    message="Final Provider real execution artifacts must store metadata only, not prompt/context/chapter text.",
                )
            )
        if str(artifact.get("status") or "") != "draft_created":
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_status_invalid",
                    path=str(path),
                    message="Final Provider real execution status must be draft_created in this phase.",
                )
            )
        source_readiness = artifact.get("source_readiness") if isinstance(artifact.get("source_readiness"), dict) else {}
        if (
            str(source_readiness.get("status") or "") != "ready_for_manual_real_llm_authorization"
            or int(source_readiness.get("issue_count") or 0) != 0
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_readiness_invalid",
                    path=str(path),
                    message="Final Provider real execution must derive from a ready zero-issue readiness report.",
                )
            )
        trigger = artifact.get("operator_trigger") if isinstance(artifact.get("operator_trigger"), dict) else {}
        legacy_authorization = (
            artifact.get("operator_authorization") if isinstance(artifact.get("operator_authorization"), dict) else {}
        )
        user_triggered = trigger.get("user_triggered") is True or legacy_authorization.get("allow_network") is True
        if not user_triggered:
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_authorization_invalid",
                    path=str(path),
                    message="Final Provider real execution must record a user-triggered execution.",
                )
            )
        execution_boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        boundary_user_triggered = (
            execution_boundary.get("user_triggered") is True
            and execution_boundary.get("network_gate_removed") is True
        )
        legacy_boundary = (
            execution_boundary.get("real_provider_enabled_temporarily") is True
            and execution_boundary.get("real_provider_disabled_after_run") is True
        )
        if (
            execution_boundary.get("execution_started") is not True
            or execution_boundary.get("provider_called") is not True
            or execution_boundary.get("real_llm_called") is not True
            or execution_boundary.get("writes_draft") is not True
            or execution_boundary.get("auto_commit") is not False
            or (not boundary_user_triggered and not legacy_boundary)
        ):
            findings.append(
                AuditFinding(
                    code="final_provider_real_execution_boundary_invalid",
                    path=str(path),
                    message="Final Provider real execution boundary metadata is invalid.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        expected_true = {"provider_called", "real_llm_called", "secret_value_read", "writes_draft"}
        safety_keys = [
            "provider_called",
            "real_llm_called",
            "secret_value_read",
            "prompt_text_stored",
            "context_text_stored",
            "chapter_text_stored",
            "secret_text_stored",
            "writes_draft",
            "auto_commit",
            "memory_bank_touched",
            "rag_touched",
            "exports_touched",
            "ui_touched",
            "docx_touched",
        ]
        if "operator_trigger" in artifact or "user_triggered" in safety:
            expected_true.add("user_triggered")
            safety_keys.insert(2, "user_triggered")
        if "real_provider_enabled" in safety:
            expected_true.add("real_provider_enabled")
            safety_keys.insert(2, "real_provider_enabled")
        for key in safety_keys:
            expected = key in expected_true
            if safety.get(key) is not expected:
                findings.append(
                    AuditFinding(
                        code="final_provider_real_execution_safety_flag_invalid",
                        path=str(path),
                        message=f"Final Provider real execution safety flag is invalid: {key}",
                    )
                )


def contains_forbidden_final_provider_real_execution_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "context_text",
        "prompt_text",
        "chapter_text",
        "generated_text",
        "raw_response",
        "request_body",
        "plain_token",
        "token",
        "api_key",
        "secret_value",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_final_provider_real_execution_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_final_provider_real_execution_text_key(item) for item in value)
    return False


def audit_provider_smoke_tests(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_provider_smoke_test", PROMPT_PATTERNS),
        ("possible_secret_in_provider_smoke_test", SECRET_PATTERNS),
        ("possible_content_in_provider_smoke_test", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "provider_smoke_tests_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    smoke_dir = store.data_dir / "provider_smoke_tests"
    checked_paths.append(str(smoke_dir))
    if not smoke_dir.exists():
        return
    passed_artifacts_with_snapshot: list[tuple[dict[str, Any], str]] = []
    for path in sorted(smoke_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)
        artifact = read_json_file(path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            continue
        if contains_forbidden_provider_smoke_test_text_key(artifact):
            findings.append(
                AuditFinding(
                    code="provider_smoke_test_text_stored",
                    path=str(path),
                    message="Provider smoke-test artifacts must store metadata only, not prompt/response/request/draft text.",
                )
            )
        status = str(artifact.get("status") or "")
        if status not in {"passed", "failed", "blocked_network_not_authorized"}:
            findings.append(
                AuditFinding(
                    code="provider_smoke_test_status_invalid",
                    path=str(path),
                    message="Provider smoke-test status is invalid.",
                )
            )
        network_attempted = bool(artifact.get("network_attempted"))
        ok = bool(artifact.get("ok"))
        trigger = artifact.get("operator_trigger") if isinstance(artifact.get("operator_trigger"), dict) else {}
        legacy_authorization = (
            artifact.get("operator_authorization") if isinstance(artifact.get("operator_authorization"), dict) else {}
        )
        user_triggered = trigger.get("user_triggered") is True or legacy_authorization.get("allow_network") is True
        if status == "passed" and (ok is not True or network_attempted is not True or not user_triggered):
            findings.append(
                AuditFinding(
                    code="provider_smoke_test_passed_state_invalid",
                    path=str(path),
                    message="Passed Provider smoke tests must record ok=true, network_attempted=true, and user_triggered=true.",
                )
            )
        if status == "blocked_network_not_authorized" and (
            ok is not False or network_attempted is not False or legacy_authorization.get("allow_network") is not False
        ):
            findings.append(
                AuditFinding(
                    code="provider_smoke_test_blocked_state_invalid",
                    path=str(path),
                    message="Legacy blocked Provider smoke tests must not be ok, must not attempt network, and must record allow_network=false.",
                )
            )
        classification = artifact.get("classification") if isinstance(artifact.get("classification"), dict) else {}
        if (
            classification.get("sample_only") is not True
            or classification.get("non_committable") is not True
            or classification.get("writes_draft") is not False
            or classification.get("auto_commit") is not False
        ):
            findings.append(
                AuditFinding(
                    code="provider_smoke_test_classification_invalid",
                    path=str(path),
                    message="Provider smoke tests must be sample-only, non-committable, and must not write or commit drafts.",
                )
            )
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        expected_values = {
            "provider_called": network_attempted,
            "real_llm_called": network_attempted,
            "prompt_text_stored": False,
            "system_prompt_text_stored": False,
            "response_text_stored": False,
            "secret_text_stored": False,
            "draft_created": False,
            "auto_commit": False,
            "confirmed_chapter_created": False,
            "memory_bank_touched": False,
            "rag_touched": False,
            "exports_touched": False,
            "ui_touched": False,
            "docx_touched": False,
        }
        if "operator_trigger" in artifact or "user_triggered" in safety:
            expected_values["user_triggered"] = True
        if "allow_network_required" in safety:
            expected_values["allow_network_required"] = True
        if "allow_network_authorized" in safety:
            expected_values["allow_network_authorized"] = legacy_authorization.get("allow_network") is True
        for key, expected in expected_values.items():
            if safety.get(key) is not expected:
                findings.append(
                    AuditFinding(
                        code="provider_smoke_test_safety_flag_invalid",
                        path=str(path),
                        message=f"Provider smoke-test safety flag is invalid: {key}",
                    )
                )
        snapshot = artifact.get("config_snapshot") if isinstance(artifact.get("config_snapshot"), dict) else {}
        if status == "passed" and snapshot:
            passed_artifacts_with_snapshot.append((artifact, str(path)))
    audit_latest_provider_smoke_config_drift(store, passed_artifacts_with_snapshot, findings=findings)


def audit_latest_provider_smoke_config_drift(
    store: ProjectStore,
    passed_artifacts_with_snapshot: list[tuple[dict[str, Any], str]],
    *,
    findings: list[AuditFinding],
) -> None:
    if not passed_artifacts_with_snapshot:
        return
    latest, path = max(passed_artifacts_with_snapshot, key=lambda item: str(item[0].get("created_at") or ""))
    snapshot = latest.get("config_snapshot") if isinstance(latest.get("config_snapshot"), dict) else {}
    role = str(latest.get("role") or snapshot.get("role") or "")
    if not role:
        return
    try:
        role_config = get_model_role_config(store, role)
    except Exception as exc:
        findings.append(
            AuditFinding(
                code="provider_smoke_test_config_drift",
                path=path,
                message=f"Provider smoke-test config drift detected for role {role}: {exc.__class__.__name__}.",
            )
        )
        return
    current = {
        "provider": role_config.provider,
        "model": role_config.model,
        "base_url_host": safe_url_host(role_config.base_url),
        "api_key_ref": role_config.api_key_ref,
    }
    drift_keys = [
        key
        for key, value in current.items()
        if str(snapshot.get(key)) != str(value)
    ]
    if drift_keys:
        findings.append(
            AuditFinding(
                code="provider_smoke_test_config_drift",
                path=path,
                message=f"Latest passed Provider smoke-test config differs from current role config: {','.join(drift_keys)}.",
            )
        )


def contains_forbidden_provider_smoke_test_text_key(value: object) -> bool:
    forbidden = {
        "prompt",
        "system_prompt",
        "text",
        "content",
        "prompt_text",
        "system_prompt_text",
        "response_text",
        "generated_text",
        "raw_response",
        "request_body",
        "api_key",
        "secret",
        "secret_value",
        "draft_id",
        "source_draft_id",
        "confirmed_chapter_id",
        "confirmed_id",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if contains_forbidden_provider_smoke_test_text_key(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_provider_smoke_test_text_key(item) for item in value)
    return False


def contains_forbidden_self_style_text(value: object) -> bool:
    forbidden_keys = {"text", "chapter_text", "prompt", "prompt_text", "system_prompt", "excerpt", "sample_text"}
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in forbidden_keys and bool(item):
                return True
            if key_text.endswith("_text_stored") and item is True:
                return True
            if contains_forbidden_self_style_text(item):
                return True
    elif isinstance(value, list):
        return any(contains_forbidden_self_style_text(item) for item in value)
    return False


def audit_formal_context_plans(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_formal_context_plan", PROMPT_PATTERNS),
        ("possible_secret_in_formal_context_plan", SECRET_PATTERNS),
        ("possible_content_in_formal_context_plan", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "formal_context_plans_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    plans_dir = store.data_dir / "formal_context_plans"
    checked_paths.append(str(plans_dir))
    if not plans_dir.exists():
        return
    for path in sorted(plans_dir.glob("*.json")):
        check_text_file(path, checked_paths=checked_paths, findings=findings, pattern_groups=pattern_groups)


def audit_formal_context_tasks(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    check_text_file(
        store.data_dir / "formal_context_task_queue.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=[
            ("possible_prompt_in_formal_context_task_queue", PROMPT_PATTERNS),
            ("possible_secret_in_formal_context_task_queue", SECRET_PATTERNS),
            ("possible_content_in_formal_context_task_queue", CONTENT_PATTERNS),
        ],
    )


def audit_memory_apply_previews(store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]) -> None:
    pattern_groups = [
        ("possible_prompt_in_memory_apply_preview", PROMPT_PATTERNS),
        ("possible_secret_in_memory_apply_preview", SECRET_PATTERNS),
        ("possible_content_in_memory_apply_preview", CONTENT_PATTERNS),
    ]
    check_text_file(
        store.data_dir / "memory_apply_previews_index.json",
        checked_paths=checked_paths,
        findings=findings,
        pattern_groups=pattern_groups,
    )
    previews_dir = store.data_dir / "memory_apply_previews"
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


CONTEXT_GENERATION_FORBIDDEN_KEYS = {
    "text",
    "content",
    "prompt",
    "prompt_text",
    "system_prompt",
    "memory_text",
    "context_text",
    "rendered_prompt",
    "rendered_messages",
    "request_body",
    "raw_response",
}


def audit_context_generation_drafts(
    store: ProjectStore, *, checked_paths: list[str], findings: list[AuditFinding]
) -> None:
    drafts_index_path = store.data_dir / "drafts_index.json"
    drafts_index = read_json_file(drafts_index_path, checked_paths=checked_paths, findings=findings)
    draft_entries = list_items(drafts_index, "drafts")
    for entry in draft_entries:
        if not entry.get("context_aware"):
            continue
        draft_id = str(entry.get("draft_id") or "")
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            findings.append(
                AuditFinding(
                    code="invalid_context_generation_draft_index_entry",
                    path=str(drafts_index_path),
                    message=f"Context-aware draft {draft_id or '<unknown>'} has no artifact path.",
                )
            )
            continue
        artifact_path = project_relative_artifact_path(store, path_value)
        if artifact_path is None:
            findings.append(
                AuditFinding(
                    code="unsafe_context_generation_draft_path",
                    path=str(drafts_index_path),
                    message=f"Context-aware draft {draft_id or '<unknown>'} artifact path escapes project root.",
                )
            )
            continue
        artifact = read_json_file(artifact_path, checked_paths=checked_paths, findings=findings)
        if artifact is None:
            findings.append(
                AuditFinding(
                    code="missing_context_generation_draft_artifact",
                    path=str(artifact_path),
                    message=f"Context-aware draft {draft_id or '<unknown>'} artifact is missing.",
                )
            )
            continue
        metadata = artifact.get("context_generation")
        if not isinstance(metadata, dict):
            findings.append(
                AuditFinding(
                    code="context_generation_metadata_missing",
                    path=str(artifact_path),
                    message=f"Context-aware draft {draft_id or '<unknown>'} has no context_generation metadata.",
                )
            )
            continue
        if str(metadata.get("mode") or "") != "mock_context_aware_generation":
            findings.append(
                AuditFinding(
                    code="context_generation_mode_invalid",
                    path=str(artifact_path),
                    message="Context generation metadata mode is not the approved mock-only mode.",
                )
            )
        if metadata.get("text_in_artifact_metadata") is not False:
            findings.append(
                AuditFinding(
                    code="context_generation_text_flag_invalid",
                    path=str(artifact_path),
                    message="Context generation metadata must explicitly record text_in_artifact_metadata=false.",
                )
            )
        index_count = entry.get("context_section_count")
        metadata_count = metadata.get("context_section_count")
        if isinstance(index_count, int) and isinstance(metadata_count, int) and index_count != metadata_count:
            findings.append(
                AuditFinding(
                    code="context_generation_section_count_mismatch",
                    path=str(artifact_path),
                    message="Context generation section count does not match drafts index.",
                )
            )
        audit_context_generation_metadata_text(metadata, path=str(artifact_path), findings=findings)
        audit_context_generation_forbidden_keys(metadata, path=str(artifact_path), findings=findings)


def audit_context_generation_metadata_text(
    metadata: dict[str, Any], *, path: str, findings: list[AuditFinding]
) -> None:
    text = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                AuditFinding(
                    code="possible_secret_in_context_generation",
                    path=path,
                    message=f"Matched {pattern.pattern}",
                )
            )
            break
    for pattern in PROMPT_PATTERNS:
        if pattern.search(text):
            findings.append(
                AuditFinding(
                    code="possible_prompt_in_context_generation",
                    path=path,
                    message=f"Matched {pattern.pattern}",
                )
            )
            break


def audit_context_generation_forbidden_keys(
    value: object, *, path: str, findings: list[AuditFinding]
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in CONTEXT_GENERATION_FORBIDDEN_KEYS:
                findings.append(
                    AuditFinding(
                        code="context_generation_forbidden_metadata_key",
                        path=path,
                        message=f"Context generation metadata contains forbidden key: {key}",
                    )
                )
            audit_context_generation_forbidden_keys(item, path=path, findings=findings)
    elif isinstance(value, list):
        for item in value:
            audit_context_generation_forbidden_keys(item, path=path, findings=findings)


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
        if adapter.requires_secret and not role_config.api_key_ref:
            findings.append(
                AuditFinding(
                    code="provider_missing_secret_ref",
                    path=str(store.config_path),
                    message=f"Role {role} provider {role_config.provider!r} requires project_secret.<name>.",
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
