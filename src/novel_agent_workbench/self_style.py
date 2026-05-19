from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .drafts import DraftGenerationService
from .storage import ProjectStore, safe_filename, utc_stamp


STYLE_BASELINES_DIRNAME = "style_baselines"
STYLE_BASELINES_INDEX_FILENAME = "style_baselines_index.json"
STYLE_CHECKS_DIRNAME = "style_checks"
STYLE_CHECKS_INDEX_FILENAME = "style_checks_index.json"
SENTENCE_RE = re.compile(r"[^。！？!?\.]+[。！？!?\.]?")
SCENE_MODES = {"general", "daily", "romance", "battle", "climax", "exposition", "transition", "custom"}
STYLE_CHECK_POLICY_PATH = ("context_policy", "style_check_policy")


class SelfStyleBaselineError(RuntimeError):
    """Raised when a self-style baseline cannot be created or read."""


@dataclass(frozen=True, slots=True)
class SelfStyleBaselineResult:
    baseline_id: str
    created_at: str
    chapter_count: int
    path: str
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DraftStyleCheckResult:
    check_id: str
    draft_id: str
    baseline_id: str
    scene_mode: str
    created_at: str
    path: str
    status: str
    issue_count: int
    hint_count: int
    checks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfStyleBaselineService:
    """Create metadata-only style baselines from confirmed chapters."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def baselines_dir(self) -> Path:
        return self.store.data_dir / STYLE_BASELINES_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / STYLE_BASELINES_INDEX_FILENAME

    @property
    def checks_dir(self) -> Path:
        return self.store.data_dir / STYLE_CHECKS_DIRNAME

    @property
    def checks_index_path(self) -> Path:
        return self.store.data_dir / STYLE_CHECKS_INDEX_FILENAME

    def create_baseline(self) -> SelfStyleBaselineResult:
        self.store.initialize()
        with self.store.lock():
            chapters = self._confirmed_chapter_records()
            if not chapters:
                raise SelfStyleBaselineError("At least one confirmed chapter is required.")
            created_at = utc_stamp()
            baseline_id = f"{created_at}_{uuid4().hex[:12]}"
            per_chapter = [
                {
                    "chapter_id": item["chapter_id"],
                    "title": item["title"],
                    "metrics": analyze_text(str(item["text"])),
                }
                for item in chapters
            ]
            metrics = aggregate_metrics([item["metrics"] for item in per_chapter])
            artifact_path = self.baselines_dir / f"{safe_filename(baseline_id)}.json"
            artifact = {
                "schema_version": 1,
                "baseline_id": baseline_id,
                "status": "ready",
                "created_at": created_at,
                "source": {
                    "type": "confirmed_chapters",
                    "chapter_count": len(chapters),
                    "included_chapters": [
                        {
                            "chapter_id": str(item["chapter_id"]),
                            "title": str(item["title"]),
                            "committed_at": str(item["committed_at"]),
                        }
                        for item in chapters
                    ],
                },
                "metrics": metrics,
                "per_chapter_metrics": per_chapter,
                "safety": {
                    "local_only": True,
                    "provider_called": False,
                    "external_corpus_used": False,
                    "chapter_text_stored": False,
                    "prompt_text_stored": False,
                    "secret_text_stored": False,
                },
            }
            self.store.write_json(artifact_path, artifact)
            entry = {
                "baseline_id": baseline_id,
                "status": "ready",
                "created_at": created_at,
                "chapter_count": len(chapters),
                "path": str(artifact_path.relative_to(self.store.root)),
                "metrics": public_metrics_summary(metrics),
                "safety": artifact["safety"],
            }
            self._append_index_entry(entry)
            return SelfStyleBaselineResult(
                baseline_id=baseline_id,
                created_at=created_at,
                chapter_count=len(chapters),
                path=str(artifact_path),
                metrics=public_metrics_summary(metrics),
            )

    def list_baselines(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "style_baselines": []})
        if not isinstance(index, dict):
            return []
        items = index.get("style_baselines")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_baseline(self, baseline_id: str) -> dict[str, Any]:
        for item in self.list_baselines():
            if item.get("baseline_id") != baseline_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise SelfStyleBaselineError(f"Style baseline index entry has no path: {baseline_id}")
            artifact = self.store.read_json(path, default=None)
            if not isinstance(artifact, dict):
                raise SelfStyleBaselineError(f"Style baseline artifact is missing or invalid: {baseline_id}")
            return artifact
        raise SelfStyleBaselineError(f"Style baseline not found: {baseline_id}")

    def check_draft_against_baseline(
        self,
        draft_id: str,
        *,
        baseline_id: str = "",
        scene_mode: str = "general",
        enabled: bool | None = None,
        calibration_enabled: bool | None = None,
        show_hints: bool | None = None,
    ) -> DraftStyleCheckResult:
        self.store.initialize()
        with self.store.lock():
            policy = effective_style_check_policy(
                self.store,
                scene_mode=scene_mode,
                enabled=enabled,
                calibration_enabled=calibration_enabled,
                show_hints=show_hints,
            )
            if not policy["enabled"]:
                raise SelfStyleBaselineError("Style check is disabled by project policy.")
            mode = normalize_scene_mode(str(policy["scene_mode"]))
            baseline = self.read_baseline(baseline_id or self._latest_baseline_id())
            draft = DraftGenerationService(self.store).read_draft(draft_id)
            content = str(draft.get("content") or "")
            draft_metrics = analyze_text(content)
            baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
            checks = compare_metrics(
                draft_metrics,
                baseline_metrics,
                scene_mode=mode,
                calibration_enabled=bool(policy["calibration_enabled"]),
                show_hints=bool(policy["show_hints"]),
            )
            issue_count = sum(1 for item in checks if item.get("severity") == "warning")
            hint_count = sum(1 for item in checks if item.get("severity") == "hint")
            if issue_count:
                status = "needs_attention"
            elif hint_count:
                status = "style_hints"
            else:
                status = "within_baseline"
            created_at = utc_stamp()
            check_id = f"{created_at}_{uuid4().hex[:12]}"
            artifact_path = self.checks_dir / f"{safe_filename(check_id)}.json"
            artifact = {
                "schema_version": 1,
                "check_id": check_id,
                "status": status,
                "created_at": created_at,
                "draft": {
                    "draft_id": str(draft.get("draft_id") or draft_id),
                    "chapter_id": str(draft.get("chapter_id") or ""),
                    "title": str(draft.get("title") or ""),
                    "draft_status": str(draft.get("status") or ""),
                },
                "baseline": {
                    "baseline_id": str(baseline.get("baseline_id") or ""),
                    "created_at": str(baseline.get("created_at") or ""),
                    "chapter_count": baseline_metrics.get("chapter_count"),
                },
                "scene_mode": mode,
                "style_check_policy": policy,
                "calibration": scene_mode_policy(mode) if policy["calibration_enabled"] else disabled_calibration_policy(mode),
                "draft_metrics": public_draft_metrics_summary(draft_metrics),
                "checks": checks,
                "issue_count": issue_count,
                "hint_count": hint_count,
                "safety": {
                    "local_only": True,
                    "provider_called": False,
                    "external_corpus_used": False,
                    "draft_text_stored": False,
                    "baseline_text_stored": False,
                    "prompt_text_stored": False,
                    "secret_text_stored": False,
                    "auto_revision": False,
                    "auto_commit": False,
                },
            }
            self.store.write_json(artifact_path, artifact)
            entry = {
                "check_id": check_id,
                "status": status,
                "created_at": created_at,
                "draft_id": str(draft.get("draft_id") or draft_id),
                "chapter_id": str(draft.get("chapter_id") or ""),
                "title": str(draft.get("title") or ""),
                "baseline_id": str(baseline.get("baseline_id") or ""),
                "scene_mode": mode,
                "style_check_policy": {
                    "enabled": policy["enabled"],
                    "calibration_enabled": policy["calibration_enabled"],
                    "show_hints": policy["show_hints"],
                    "source": policy["source"],
                },
                "issue_count": issue_count,
                "hint_count": hint_count,
                "path": str(artifact_path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_check_index_entry(entry)
            return DraftStyleCheckResult(
                check_id=check_id,
                draft_id=str(draft.get("draft_id") or draft_id),
                baseline_id=str(baseline.get("baseline_id") or ""),
                scene_mode=mode,
                created_at=created_at,
                path=str(artifact_path),
                status=status,
                issue_count=issue_count,
                hint_count=hint_count,
                checks=checks,
            )

    def list_style_checks(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.checks_index_path, default={"schema_version": 1, "style_checks": []})
        if not isinstance(index, dict):
            return []
        items = index.get("style_checks")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_style_check(self, check_id: str) -> dict[str, Any]:
        for item in self.list_style_checks():
            if item.get("check_id") != check_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise SelfStyleBaselineError(f"Style check index entry has no path: {check_id}")
            artifact = self.store.read_json(path, default=None)
            if not isinstance(artifact, dict):
                raise SelfStyleBaselineError(f"Style check artifact is missing or invalid: {check_id}")
            return artifact
        raise SelfStyleBaselineError(f"Style check not found: {check_id}")

    def _confirmed_chapter_records(self) -> list[dict[str, Any]]:
        service = DraftGenerationService(self.store)
        records: list[dict[str, Any]] = []
        for entry in service.list_confirmed_chapters():
            chapter_id = str(entry.get("chapter_id") or "")
            if not chapter_id:
                continue
            chapter = service.read_confirmed_chapter(chapter_id)
            records.append(
                {
                    "chapter_id": chapter_id,
                    "title": str(entry.get("title") or chapter.get("title") or ""),
                    "committed_at": str(entry.get("committed_at") or chapter.get("committed_at") or ""),
                    "text": str(chapter.get("content") or ""),
                }
            )
        return records

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_baselines()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "style_baselines": items})

    def _append_check_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_style_checks()
        items.append(entry)
        self.store.write_json(self.checks_index_path, {"schema_version": 1, "style_checks": items})

    def _latest_baseline_id(self) -> str:
        baselines = self.list_baselines()
        if not baselines:
            raise SelfStyleBaselineError("At least one self style baseline is required.")
        latest = max(baselines, key=lambda item: str(item.get("created_at") or ""))
        baseline_id = str(latest.get("baseline_id") or "")
        if not baseline_id:
            raise SelfStyleBaselineError("Latest self style baseline has no baseline_id.")
        return baseline_id


def analyze_text(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    nonempty_lines = [line.strip() for line in lines if line.strip()]
    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)
    char_count = len(text)
    nonspace_char_count = sum(1 for char in text if not char.isspace())
    dialogue_lines = [line for line in nonempty_lines if is_dialogue_line(line)]
    punctuation = punctuation_counts(text)
    return {
        "char_count": char_count,
        "nonspace_char_count": nonspace_char_count,
        "line_count": len(lines),
        "nonempty_line_count": len(nonempty_lines),
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "dialogue_line_count": len(dialogue_lines),
        "dialogue_line_ratio": safe_ratio(len(dialogue_lines), len(nonempty_lines)),
        "avg_paragraph_chars": safe_round(sum(len(item) for item in paragraphs) / len(paragraphs))
        if paragraphs
        else 0,
        "avg_sentence_chars": safe_round(sum(len(item) for item in sentences) / len(sentences))
        if sentences
        else 0,
        "short_paragraph_ratio": safe_ratio(sum(1 for item in paragraphs if len(item) <= 40), len(paragraphs)),
        "long_paragraph_ratio": safe_ratio(sum(1 for item in paragraphs if len(item) >= 180), len(paragraphs)),
        "punctuation": punctuation,
        "punctuation_per_1000_chars": {
            key: safe_round(value * 1000 / max(nonspace_char_count, 1), digits=3)
            for key, value in punctuation.items()
        },
    }


def aggregate_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    char_counts = [int(item.get("nonspace_char_count") or 0) for item in items]
    paragraph_counts = [int(item.get("paragraph_count") or 0) for item in items]
    sentence_counts = [int(item.get("sentence_count") or 0) for item in items]
    dialogue_ratios = [float(item.get("dialogue_line_ratio") or 0) for item in items]
    avg_sentence_chars = [float(item.get("avg_sentence_chars") or 0) for item in items]
    avg_paragraph_chars = [float(item.get("avg_paragraph_chars") or 0) for item in items]
    punctuation_totals: dict[str, int] = {}
    for item in items:
        punctuation = item.get("punctuation") if isinstance(item.get("punctuation"), dict) else {}
        for key, value in punctuation.items():
            punctuation_totals[str(key)] = punctuation_totals.get(str(key), 0) + int(value or 0)
    total_nonspace_chars = sum(char_counts)
    return {
        "chapter_count": len(items),
        "nonspace_chars": distribution(char_counts),
        "paragraphs_per_chapter": distribution(paragraph_counts),
        "sentences_per_chapter": distribution(sentence_counts),
        "dialogue_line_ratio": distribution(dialogue_ratios, digits=3),
        "avg_sentence_chars": distribution(avg_sentence_chars),
        "avg_paragraph_chars": distribution(avg_paragraph_chars),
        "punctuation": punctuation_totals,
        "punctuation_per_1000_chars": {
            key: safe_round(value * 1000 / max(total_nonspace_chars, 1), digits=3)
            for key, value in punctuation_totals.items()
        },
    }


def public_metrics_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter_count": metrics.get("chapter_count"),
        "nonspace_chars": metrics.get("nonspace_chars") if isinstance(metrics.get("nonspace_chars"), dict) else {},
        "dialogue_line_ratio": metrics.get("dialogue_line_ratio")
        if isinstance(metrics.get("dialogue_line_ratio"), dict)
        else {},
        "avg_sentence_chars": metrics.get("avg_sentence_chars")
        if isinstance(metrics.get("avg_sentence_chars"), dict)
        else {},
        "avg_paragraph_chars": metrics.get("avg_paragraph_chars")
        if isinstance(metrics.get("avg_paragraph_chars"), dict)
        else {},
        "punctuation_per_1000_chars": metrics.get("punctuation_per_1000_chars")
        if isinstance(metrics.get("punctuation_per_1000_chars"), dict)
        else {},
    }


def public_draft_metrics_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "nonspace_char_count": metrics.get("nonspace_char_count"),
        "paragraph_count": metrics.get("paragraph_count"),
        "sentence_count": metrics.get("sentence_count"),
        "dialogue_line_ratio": metrics.get("dialogue_line_ratio"),
        "avg_sentence_chars": metrics.get("avg_sentence_chars"),
        "avg_paragraph_chars": metrics.get("avg_paragraph_chars"),
        "punctuation_per_1000_chars": metrics.get("punctuation_per_1000_chars")
        if isinstance(metrics.get("punctuation_per_1000_chars"), dict)
        else {},
    }


def compare_metrics(
    draft_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    *,
    scene_mode: str = "general",
    calibration_enabled: bool = True,
    show_hints: bool = True,
) -> list[dict[str, Any]]:
    mode = normalize_scene_mode(scene_mode)
    checks = [
        compare_distribution_metric(
            "nonspace_chars",
            "chapter length",
            float(draft_metrics.get("nonspace_char_count") or 0),
            baseline_metrics.get("nonspace_chars"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
        compare_distribution_metric(
            "paragraphs_per_chapter",
            "paragraph count",
            float(draft_metrics.get("paragraph_count") or 0),
            baseline_metrics.get("paragraphs_per_chapter"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
        compare_distribution_metric(
            "sentences_per_chapter",
            "sentence count",
            float(draft_metrics.get("sentence_count") or 0),
            baseline_metrics.get("sentences_per_chapter"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
        compare_distribution_metric(
            "dialogue_line_ratio",
            "dialogue line ratio",
            float(draft_metrics.get("dialogue_line_ratio") or 0),
            baseline_metrics.get("dialogue_line_ratio"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
        compare_distribution_metric(
            "avg_sentence_chars",
            "average sentence length",
            float(draft_metrics.get("avg_sentence_chars") or 0),
            baseline_metrics.get("avg_sentence_chars"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
        compare_distribution_metric(
            "avg_paragraph_chars",
            "average paragraph length",
            float(draft_metrics.get("avg_paragraph_chars") or 0),
            baseline_metrics.get("avg_paragraph_chars"),
            scene_mode=mode,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ),
    ]
    punctuation = draft_metrics.get("punctuation_per_1000_chars")
    baseline_punctuation = baseline_metrics.get("punctuation_per_1000_chars")
    if isinstance(punctuation, dict) and isinstance(baseline_punctuation, dict):
        for key in ("cn_question", "cn_exclamation", "ellipsis", "dash", "colon"):
            checks.append(
                compare_point_metric(
                    f"punctuation.{key}",
                    key,
                    punctuation.get(key),
                    baseline_punctuation.get(key),
                    scene_mode=mode,
                    calibration_enabled=calibration_enabled,
                    show_hints=show_hints,
                )
            )
    return checks


def compare_distribution_metric(
    metric_id: str,
    label: str,
    value: float,
    baseline: object,
    *,
    scene_mode: str,
    calibration_enabled: bool,
    show_hints: bool,
) -> dict[str, Any]:
    if not isinstance(baseline, dict) or not baseline:
        return unavailable_check(metric_id, label, value)
    p25 = float(baseline.get("p25") or 0)
    median = float(baseline.get("median") or 0)
    p75 = float(baseline.get("p75") or 0)
    policy = scene_mode_policy(scene_mode) if calibration_enabled else disabled_calibration_policy(scene_mode)
    lower_multiplier = tolerance_multiplier(policy, metric_id, "lower")
    upper_multiplier = tolerance_multiplier(policy, metric_id, "upper")
    minimum_span = 0.05 if "ratio" in metric_id else 1.0
    span = max(p75 - p25, abs(median) * 0.15, minimum_span)
    hard_low = max(0.0, p25 - span * lower_multiplier)
    hard_high = p75 + span * upper_multiplier
    status = "within_range"
    severity = "info"
    if value < p25:
        status = "soft_low"
        severity = "hint"
    elif value > p75:
        status = "soft_high"
        severity = "hint"
    if severity == "hint" and not show_hints:
        status = "within_range"
        severity = "info"
    if value < hard_low:
        status = "low"
        severity = "warning"
    elif value > hard_high:
        status = "high"
        severity = "warning"
    return {
        "metric_id": metric_id,
        "label": label,
        "value": safe_round(value, digits=3),
        "baseline": {
            "p25": p25,
            "median": median,
            "p75": p75,
            "hard_low": safe_round(hard_low, digits=3),
            "hard_high": safe_round(hard_high, digits=3),
        },
        "scene_mode": scene_mode,
        "status": status,
        "severity": severity,
        "delta_from_median": safe_round(value - median, digits=3),
    }


def compare_point_metric(
    metric_id: str,
    label: str,
    value: object,
    baseline: object,
    *,
    scene_mode: str,
    calibration_enabled: bool,
    show_hints: bool,
) -> dict[str, Any]:
    numeric_value = float(value or 0)
    numeric_baseline = float(baseline or 0)
    policy = scene_mode_policy(scene_mode) if calibration_enabled else disabled_calibration_policy(scene_mode)
    lower_multiplier = tolerance_multiplier(policy, metric_id, "lower")
    upper_multiplier = tolerance_multiplier(policy, metric_id, "upper")
    base_tolerance = max(1.0, numeric_baseline * 0.5)
    soft_low = max(0.0, numeric_baseline - base_tolerance)
    soft_high = numeric_baseline + base_tolerance
    hard_low = max(0.0, numeric_baseline - base_tolerance * lower_multiplier)
    hard_high = numeric_baseline + base_tolerance * upper_multiplier
    status = "within_range"
    severity = "info"
    if numeric_value < soft_low:
        status = "soft_low"
        severity = "hint"
    elif numeric_value > soft_high:
        status = "soft_high"
        severity = "hint"
    if severity == "hint" and not show_hints:
        status = "within_range"
        severity = "info"
    if numeric_value < hard_low:
        status = "low"
        severity = "warning"
    elif numeric_value > hard_high:
        status = "high"
        severity = "warning"
    return {
        "metric_id": metric_id,
        "label": label,
        "value": safe_round(numeric_value, digits=3),
        "baseline": {
            "target": safe_round(numeric_baseline, digits=3),
            "soft_low": safe_round(soft_low, digits=3),
            "soft_high": safe_round(soft_high, digits=3),
            "hard_low": safe_round(hard_low, digits=3),
            "hard_high": safe_round(hard_high, digits=3),
        },
        "scene_mode": scene_mode,
        "status": status,
        "severity": severity,
        "delta_from_target": safe_round(numeric_value - numeric_baseline, digits=3),
    }


def unavailable_check(metric_id: str, label: str, value: float) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "label": label,
        "value": safe_round(value, digits=3),
        "baseline": {},
        "status": "baseline_unavailable",
        "severity": "warning",
    }


def normalize_scene_mode(value: str) -> str:
    mode = str(value or "general").strip().lower().replace("-", "_")
    if mode not in SCENE_MODES:
        raise SelfStyleBaselineError(f"Unsupported scene_mode: {value!r}")
    return mode


def effective_style_check_policy(
    store: ProjectStore,
    *,
    scene_mode: str = "general",
    enabled: bool | None = None,
    calibration_enabled: bool | None = None,
    show_hints: bool | None = None,
) -> dict[str, Any]:
    config = store.read_config()
    policy = nested_dict(config, STYLE_CHECK_POLICY_PATH)
    selected_scene_mode = scene_mode or str(policy.get("default_scene_mode") or "general")
    if selected_scene_mode == "general" and scene_mode == "general":
        selected_scene_mode = str(policy.get("default_scene_mode") or "general")
    result = {
        "enabled": bool(policy.get("enabled", True)) if enabled is None else bool(enabled),
        "calibration_enabled": bool(policy.get("calibration_enabled", True))
        if calibration_enabled is None
        else bool(calibration_enabled),
        "show_hints": bool(policy.get("show_hints", True)) if show_hints is None else bool(show_hints),
        "scene_mode": normalize_scene_mode(selected_scene_mode),
        "severity_mode": str(policy.get("severity_mode") or "hint_first"),
        "auto_create_revision_request": bool(policy.get("auto_create_revision_request", False)),
        "source": "project_config_with_call_overrides",
    }
    return result


def nested_dict(source: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    current: object = source
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def scene_mode_policy(scene_mode: str) -> dict[str, Any]:
    mode = normalize_scene_mode(scene_mode)
    policy: dict[str, Any] = {
        "scene_mode": mode,
        "meaning": "local style check hints only; not a pass/fail grade",
        "default_lower_multiplier": 1.75,
        "default_upper_multiplier": 1.75,
        "metric_multipliers": {},
    }
    if mode == "daily":
        policy["metric_multipliers"] = {
            "dialogue_line_ratio": {"upper": 3.0},
            "avg_paragraph_chars": {"lower": 2.2},
        }
    elif mode == "romance":
        policy["metric_multipliers"] = {
            "dialogue_line_ratio": {"lower": 2.4, "upper": 2.4},
            "avg_sentence_chars": {"upper": 2.4},
            "avg_paragraph_chars": {"upper": 2.6},
            "punctuation.ellipsis": {"upper": 2.5},
        }
    elif mode == "battle":
        policy["metric_multipliers"] = {
            "nonspace_chars": {"lower": 2.8},
            "avg_sentence_chars": {"lower": 3.0},
            "avg_paragraph_chars": {"lower": 3.0},
            "punctuation.cn_exclamation": {"upper": 3.0},
            "punctuation.dash": {"upper": 2.5},
        }
    elif mode == "climax":
        policy["metric_multipliers"] = {
            "nonspace_chars": {"lower": 2.4, "upper": 2.4},
            "avg_sentence_chars": {"lower": 2.8},
            "avg_paragraph_chars": {"lower": 2.6},
            "punctuation.cn_exclamation": {"upper": 3.2},
            "punctuation.ellipsis": {"upper": 2.4},
            "punctuation.dash": {"upper": 2.4},
        }
    elif mode == "exposition":
        policy["metric_multipliers"] = {
            "dialogue_line_ratio": {"lower": 6.0},
            "avg_sentence_chars": {"upper": 3.0},
            "avg_paragraph_chars": {"upper": 3.2},
            "paragraphs_per_chapter": {"lower": 2.5},
        }
    elif mode == "transition":
        policy["metric_multipliers"] = {
            "nonspace_chars": {"lower": 3.5},
            "paragraphs_per_chapter": {"lower": 2.5},
            "sentences_per_chapter": {"lower": 2.5},
        }
    elif mode == "custom":
        policy["default_lower_multiplier"] = 2.5
        policy["default_upper_multiplier"] = 2.5
    return policy


def disabled_calibration_policy(scene_mode: str) -> dict[str, Any]:
    return {
        "scene_mode": normalize_scene_mode(scene_mode),
        "meaning": "calibration disabled; unified baseline tolerance is used",
        "default_lower_multiplier": 1.0,
        "default_upper_multiplier": 1.0,
        "metric_multipliers": {},
    }


def tolerance_multiplier(policy: dict[str, Any], metric_id: str, side: str) -> float:
    default_key = "default_lower_multiplier" if side == "lower" else "default_upper_multiplier"
    value = float(policy.get(default_key) or 1.75)
    metric_multipliers = policy.get("metric_multipliers")
    if not isinstance(metric_multipliers, dict):
        return value
    item = metric_multipliers.get(metric_id)
    if isinstance(item, dict) and side in item:
        return float(item[side])
    return value


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    paragraphs: list[str] = []
    for part in parts:
        clean = "\n".join(line.strip() for line in part.splitlines() if line.strip()).strip()
        if clean:
            paragraphs.append(clean)
    if not paragraphs:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return paragraphs


def split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]


def is_dialogue_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped[0] in {'"', "'", "“", "「", "『", "（"}:
        return True
    return "“" in stripped or "”" in stripped or "：" in stripped or ":" in stripped


def punctuation_counts(text: str) -> dict[str, int]:
    tracked = {
        "cn_period": "。",
        "cn_comma": "，",
        "cn_question": "？",
        "cn_exclamation": "！",
        "ellipsis": "…",
        "dash": "—",
        "quote_open": "“",
        "quote_close": "”",
        "colon": "：",
        "semicolon": "；",
        "ascii_question": "?",
        "ascii_exclamation": "!",
    }
    return {key: text.count(symbol) for key, symbol in tracked.items()}


def distribution(values: list[int] | list[float], *, digits: int = 2) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": 0, "p25": 0, "median": 0, "p75": 0, "max": 0, "avg": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], digits),
        "p25": safe_round(percentile(ordered, 0.25), digits=digits),
        "median": safe_round(percentile(ordered, 0.5), digits=digits),
        "p75": safe_round(percentile(ordered, 0.75), digits=digits),
        "max": round(ordered[-1], digits),
        "avg": safe_round(sum(ordered) / len(ordered), digits=digits),
    }


def percentile(values: list[int] | list[float], fraction: float) -> float:
    if not values:
        return 0
    if len(values) == 1:
        return float(values[0])
    index = (len(values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return float(values[lower]) * (1 - weight) + float(values[upper]) * weight


def safe_ratio(numerator: int, denominator: int) -> float:
    return safe_round(numerator / denominator, digits=3) if denominator else 0


def safe_round(value: float, *, digits: int = 2) -> float:
    return round(float(value), digits)
