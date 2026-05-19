from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any


STRICT_CHAPTER_HEADING_RE = re.compile(r"^\s*第[0-9一二三四五六七八九十百千万零〇两]+[章节卷回幕].{0,40}$")
LOOSE_CHAPTER_RE = re.compile(r"第[0-9一二三四五六七八九十百千万零〇两]+[章节卷回幕]")
CJK_SPEAKER_RE = re.compile(r"([\u4e00-\u9fff]{2,4})(?:说|问|道|喊|叫|笑|叹|想|看|点头|摇头)")
ASCII_NAME_RE = re.compile(r"\b[A-Z][A-Za-z0-9_\-]{1,24}\b")
DIALOGUE_MARK_RE = re.compile(r"[“”]")
SECRET_LIKE_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{6,}|cpk_[A-Za-z0-9_.\-]{12,})\b")

COMMON_CJK_FALSE_NAMES = {
    "只是",
    "但是",
    "就是",
    "不是",
    "没有",
    "自己",
    "这个",
    "那个",
    "什么",
    "然后",
    "已经",
    "因为",
    "所以",
    "如果",
    "少女",
    "少年",
    "老师",
    "同学",
    "妹妹",
    "姐姐",
    "哥哥",
    "爷爷",
    "奶奶",
    "大家",
    "对方",
    "男人",
    "女人",
}


class CorpusProfilerError(RuntimeError):
    """Raised when a corpus file cannot be profiled safely."""


@dataclass(frozen=True, slots=True)
class CorpusProfileResult:
    source: dict[str, Any]
    encoding: dict[str, Any]
    structure: dict[str, Any]
    chapter_stats: dict[str, Any]
    line_stats: dict[str, Any]
    dialogue_proxy: dict[str, Any]
    name_candidates: dict[str, Any]
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_corpus(path: str | Path, *, max_name_candidates: int = 20) -> CorpusProfileResult:
    source_path = Path(path)
    if not source_path.exists() or not source_path.is_file():
        raise CorpusProfilerError(f"Corpus file not found: {source_path}")
    data = source_path.read_bytes()
    decoded = decode_text(data)
    text = decoded["text"]
    lines = split_lines(text)
    nonempty_lines = [line for line in lines if line.strip()]
    headings = strict_heading_lines(lines)
    heading_indexes = {heading["line_index"] for heading in headings}
    body_text_without_headings = "\n".join(
        line for index, line in enumerate(lines) if index not in heading_indexes
    )
    chapter_lengths = chapter_char_lengths(lines, headings)
    return CorpusProfileResult(
        source={
            "path": str(source_path),
            "file_name": source_path.name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest().upper(),
        },
        encoding={
            "detected": decoded["encoding"],
            "utf8_strict_ok": decoded["utf8_strict_ok"],
        },
        structure={
            "line_count": len(lines),
            "nonempty_line_count": len(nonempty_lines),
            "char_count": len(text),
            "strict_chapter_heading_count": len(headings),
            "loose_chapter_like_count": len(LOOSE_CHAPTER_RE.findall(text)),
            "first_heading_line_numbers": [heading["line_number"] for heading in headings[:10]],
            "heading_text_included": False,
        },
        chapter_stats=safe_distribution(chapter_lengths),
        line_stats=line_distribution(nonempty_lines),
        dialogue_proxy=dialogue_stats(nonempty_lines),
        name_candidates=name_candidates(body_text_without_headings, max_items=max_name_candidates),
        safety={
            "source_text_copied": False,
            "chapter_heading_text_included": False,
            "provider_called": False,
            "writes_project_files": False,
            "secret_like_pattern_found": bool(SECRET_LIKE_RE.search(text)),
        },
    )


def decode_text(data: bytes) -> dict[str, Any]:
    try:
        return {"encoding": "utf-8", "utf8_strict_ok": True, "text": data.decode("utf-8")}
    except UnicodeDecodeError:
        try:
            return {"encoding": "gb18030", "utf8_strict_ok": False, "text": data.decode("gb18030")}
        except UnicodeDecodeError as exc:
            raise CorpusProfilerError("Corpus file is not valid UTF-8 or GB18030 text.") from exc


def split_lines(text: str) -> list[str]:
    return re.split(r"\r?\n", text)


def strict_heading_lines(lines: list[str]) -> list[dict[str, int]]:
    headings: list[dict[str, int]] = []
    for index, line in enumerate(lines, start=1):
        if STRICT_CHAPTER_HEADING_RE.match(line):
            headings.append({"line_number": index, "line_index": index - 1})
    return headings


def chapter_char_lengths(lines: list[str], headings: list[dict[str, int]]) -> list[int]:
    if not headings:
        return []
    lengths: list[int] = []
    for index, heading in enumerate(headings):
        start = int(heading["line_index"]) + 1
        end = int(headings[index + 1]["line_index"]) if index + 1 < len(headings) else len(lines)
        chapter_text = "\n".join(lines[start:end])
        lengths.append(len(chapter_text))
    return lengths


def safe_distribution(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min_chars": 0,
            "max_chars": 0,
            "mean_chars": 0,
            "median_chars": 0,
            "p10_chars": 0,
            "p90_chars": 0,
        }
    ordered = sorted(values)
    return {
        "count": len(values),
        "min_chars": ordered[0],
        "max_chars": ordered[-1],
        "mean_chars": round(sum(values) / len(values), 2),
        "median_chars": int(median(values)),
        "p10_chars": percentile(ordered, 0.10),
        "p90_chars": percentile(ordered, 0.90),
    }


def percentile(ordered_values: list[int], fraction: float) -> int:
    if not ordered_values:
        return 0
    index = round((len(ordered_values) - 1) * fraction)
    return int(ordered_values[index])


def line_distribution(lines: list[str]) -> dict[str, Any]:
    lengths = [len(line.strip()) for line in lines]
    return {
        "nonempty_count": len(lines),
        "line_char_distribution": safe_distribution(lengths),
        "short_line_count": sum(1 for length in lengths if 0 < length <= 20),
        "long_line_count": sum(1 for length in lengths if length >= 120),
    }


def dialogue_stats(lines: list[str]) -> dict[str, Any]:
    if not lines:
        return {
            "dialogue_like_line_count": 0,
            "dialogue_like_line_ratio": 0.0,
            "quote_mark_line_count": 0,
            "colon_line_count": 0,
        }
    quote_lines = sum(1 for line in lines if DIALOGUE_MARK_RE.search(line))
    colon_lines = sum(1 for line in lines if "：" in line or ":" in line)
    dialogue_like = sum(1 for line in lines if DIALOGUE_MARK_RE.search(line) or "：" in line or ":" in line)
    return {
        "dialogue_like_line_count": dialogue_like,
        "dialogue_like_line_ratio": round(dialogue_like / len(lines), 4),
        "quote_mark_line_count": quote_lines,
        "colon_line_count": colon_lines,
    }


def name_candidates(text: str, *, max_items: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for match in CJK_SPEAKER_RE.finditer(text):
        candidate = match.group(1)
        if candidate in COMMON_CJK_FALSE_NAMES:
            continue
        counts[candidate] = counts.get(candidate, 0) + 1
    for match in ASCII_NAME_RE.finditer(text):
        candidate = match.group(0)
        if candidate.upper() in {"PS", "VIP"}:
            continue
        counts[candidate] = counts.get(candidate, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[: max(max_items, 0)]
    return {
        "method": "speaker_verb_and_ascii_token_frequency",
        "candidate_count": len(counts),
        "top": [{"name": name, "count": count} for name, count in ordered],
    }
