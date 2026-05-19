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
    created_at: str
    path: str
    status: str
    issue_count: int
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

    def check_draft_against_baseline(self, draft_id: str, *, baseline_id: str = "") -> DraftStyleCheckResult:
        self.store.initialize()
        with self.store.lock():
            baseline = self.read_baseline(baseline_id or self._latest_baseline_id())
            draft = DraftGenerationService(self.store).read_draft(draft_id)
            content = str(draft.get("content") or "")
            draft_metrics = analyze_text(content)
            baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
            checks = compare_metrics(draft_metrics, baseline_metrics)
            issue_count = sum(1 for item in checks if item.get("status") != "within_range")
            status = "within_baseline" if issue_count == 0 else "needs_attention"
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
                "draft_metrics": public_draft_metrics_summary(draft_metrics),
                "checks": checks,
                "issue_count": issue_count,
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
                "issue_count": issue_count,
                "path": str(artifact_path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_check_index_entry(entry)
            return DraftStyleCheckResult(
                check_id=check_id,
                draft_id=str(draft.get("draft_id") or draft_id),
                baseline_id=str(baseline.get("baseline_id") or ""),
                created_at=created_at,
                path=str(artifact_path),
                status=status,
                issue_count=issue_count,
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


def compare_metrics(draft_metrics: dict[str, Any], baseline_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        compare_distribution_metric(
            "nonspace_chars",
            "chapter length",
            float(draft_metrics.get("nonspace_char_count") or 0),
            baseline_metrics.get("nonspace_chars"),
        ),
        compare_distribution_metric(
            "paragraphs_per_chapter",
            "paragraph count",
            float(draft_metrics.get("paragraph_count") or 0),
            baseline_metrics.get("paragraphs_per_chapter"),
        ),
        compare_distribution_metric(
            "sentences_per_chapter",
            "sentence count",
            float(draft_metrics.get("sentence_count") or 0),
            baseline_metrics.get("sentences_per_chapter"),
        ),
        compare_distribution_metric(
            "dialogue_line_ratio",
            "dialogue line ratio",
            float(draft_metrics.get("dialogue_line_ratio") or 0),
            baseline_metrics.get("dialogue_line_ratio"),
        ),
        compare_distribution_metric(
            "avg_sentence_chars",
            "average sentence length",
            float(draft_metrics.get("avg_sentence_chars") or 0),
            baseline_metrics.get("avg_sentence_chars"),
        ),
        compare_distribution_metric(
            "avg_paragraph_chars",
            "average paragraph length",
            float(draft_metrics.get("avg_paragraph_chars") or 0),
            baseline_metrics.get("avg_paragraph_chars"),
        ),
    ]
    punctuation = draft_metrics.get("punctuation_per_1000_chars")
    baseline_punctuation = baseline_metrics.get("punctuation_per_1000_chars")
    if isinstance(punctuation, dict) and isinstance(baseline_punctuation, dict):
        for key in ("cn_question", "cn_exclamation", "ellipsis", "dash", "colon"):
            checks.append(compare_point_metric(f"punctuation.{key}", key, punctuation.get(key), baseline_punctuation.get(key)))
    return checks


def compare_distribution_metric(metric_id: str, label: str, value: float, baseline: object) -> dict[str, Any]:
    if not isinstance(baseline, dict) or not baseline:
        return unavailable_check(metric_id, label, value)
    p25 = float(baseline.get("p25") or 0)
    median = float(baseline.get("median") or 0)
    p75 = float(baseline.get("p75") or 0)
    status = "within_range"
    if value < p25:
        status = "low"
    elif value > p75:
        status = "high"
    return {
        "metric_id": metric_id,
        "label": label,
        "value": safe_round(value, digits=3),
        "baseline": {"p25": p25, "median": median, "p75": p75},
        "status": status,
        "severity": "info" if status == "within_range" else "warning",
        "delta_from_median": safe_round(value - median, digits=3),
    }


def compare_point_metric(metric_id: str, label: str, value: object, baseline: object) -> dict[str, Any]:
    numeric_value = float(value or 0)
    numeric_baseline = float(baseline or 0)
    tolerance = max(1.0, numeric_baseline * 0.5)
    status = "within_range"
    if numeric_value < numeric_baseline - tolerance:
        status = "low"
    elif numeric_value > numeric_baseline + tolerance:
        status = "high"
    return {
        "metric_id": metric_id,
        "label": label,
        "value": safe_round(numeric_value, digits=3),
        "baseline": {"target": safe_round(numeric_baseline, digits=3), "tolerance": safe_round(tolerance, digits=3)},
        "status": status,
        "severity": "info" if status == "within_range" else "warning",
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
