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
