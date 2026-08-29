"""Shared, Tk-free formatting and input helpers used by both desktop front ends."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

from .chapters import chapter_id_number, chapter_number_width, format_chapter_id, format_chapter_number
from .context_assembler import DEFAULT_CHARS_PER_TOKEN
from .memory_bank import DEFAULT_MEMORY_TARGET_TOKENS, normalize_memory_target_tokens
from .storage import DEFAULT_PROJECTS_DIRNAME


MODEL_ROLE_OPTIONS = (
    ("writer", "正文生成"),
    ("scorer", "AI审稿"),
    ("reviser", "AI精修/改写"),
)
FIELD_LABELS = {
    "chapter_id": "章节",
    "title": "标题",
    "status": "状态",
    "planned_at": "计划时间",
    "updated_at": "更新时间",
    "created_at": "创建时间",
    "committed_at": "确认时间",
    "draft_id": "草稿",
    "review_id": "审稿",
    "review_type": "审稿类型",
    "decision": "决定",
    "reason_code": "原因",
    "revision_request_id": "改写请求",
    "task_id": "任务",
    "type_label": "类型",
    "used_in_context": "加入上下文",
    "text_chars": "字数",
    "target": "适用范围",
    "memory_weight": "权重",
    "source_label": "来源",
    "file_name": "文件",
    "chapter_count": "章节数",
    "provider": "服务",
    "model": "模型",
    "ok": "通过",
    "blocker": "阻断",
    "warning": "警告",
}


def default_projects_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "用户数据" / DEFAULT_PROJECTS_DIRNAME
    return Path(__file__).resolve().parents[2] / DEFAULT_PROJECTS_DIRNAME


def default_repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def format_record_sections(sections: list[tuple[str, list[dict[str, Any]], tuple[str, ...]]]) -> str:
    lines: list[str] = []
    for title, items, fields in sections:
        lines.append(title)
        lines.append("-" * len(title))
        if not items:
            lines.append("暂无记录。")
            lines.append("")
            continue
        for index, item in enumerate(items, start=1):
            parts = [
                f"{FIELD_LABELS.get(field, field)}={safe_record_value(item.get(field))}"
                for field in fields
                if safe_record_value(item.get(field))
            ]
            lines.append(f"{index}. " + " | ".join(parts))
        lines.append("")
    return "\n".join(lines).rstrip()


def memory_category_label(category_id: str) -> str:
    labels = {
        "world_building": "世界观",
        "character_relationships": "人物关系",
        "chapter_summary": "章节摘要",
        "style_memory": "风格记忆",
        "foreshadowing": "伏笔",
        "recent_chapters": "前文片段",
    }
    value = str(category_id or "").strip()
    return labels.get(value, value or "未分类")


def readable_chapter_label(chapter_id: str) -> str:
    value = str(chapter_id or "").strip()
    if not value:
        return "全局"
    number = chapter_id_number(value)
    if number is None:
        return value
    return f"第 {format_chapter_number(number)} 章"


def memory_progress_label(memory_item: dict[str, Any], chapters: list[dict[str, Any]]) -> str:
    last_chapter_id = str(memory_item.get("last_updated_chapter_id") or "").strip()
    last_number = memory_progress_number(memory_item)
    has_memory = bool(str(memory_item.get("text") or "").strip()) or int(memory_item.get("text_chars") or 0) > 0
    if last_number > 0:
        return (
            f"当前记忆银行已记录到 {readable_chapter_label(last_chapter_id)}。"
            f"建议从第 {format_chapter_number(last_number + 1)} 章开始勾选新定稿。"
        )
    if has_memory:
        return "当前记忆银行已有正文，但没有记录章节进度。请手动勾选尚未汇总过的定稿章节。"
    if chapters:
        return f"当前记忆银行尚未建立。建议从第 {format_chapter_number(1)} 章开始勾选定稿章节。"
    return "当前项目还没有已确认章节。先确认稿件后再更新记忆银行。"


def recommended_memory_chapter_ids(memory_item: dict[str, Any], chapters: list[dict[str, Any]]) -> list[str]:
    last_number = memory_progress_number(memory_item)
    has_memory = bool(str(memory_item.get("text") or "").strip()) or int(memory_item.get("text_chars") or 0) > 0
    if last_number <= 0 and has_memory:
        return []
    selected: list[str] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        number = chapter_sort_number(chapter_id)
        if chapter_id and number > last_number:
            selected.append(chapter_id)
    return selected


def memory_progress_number(memory_item: dict[str, Any]) -> int:
    value = memory_item.get("last_updated_chapter_number")
    if isinstance(value, int) and not isinstance(value, bool):
        return max(value, 0)
    chapter_id = str(memory_item.get("last_updated_chapter_id") or "")
    number = chapter_sort_number(chapter_id)
    return 0 if number == 999999 else number


def estimate_memory_text_tokens(text: str) -> int:
    value = str(text or "").strip()
    if not value:
        return 0
    cjk_chars = sum(1 for character in value if is_cjk_character(character))
    other_chars = sum(1 for character in value if not character.isspace() and not is_cjk_character(character))
    return cjk_chars + ceil(other_chars / DEFAULT_CHARS_PER_TOKEN)


def is_cjk_character(character: str) -> bool:
    if not character:
        return False
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
    )


def memory_token_advice(estimated_tokens: int, target_tokens: int = DEFAULT_MEMORY_TARGET_TOKENS) -> str:
    estimate = max(int(estimated_tokens or 0), 0)
    target = normalize_memory_target_tokens(target_tokens)
    if estimate <= 0:
        return f"当前约 0 tokens / 目标 {target} tokens。"
    if estimate <= target:
        return f"当前约 {estimate} tokens / 目标 {target} tokens，在目标内。"
    if estimate <= ceil(target * 1.2):
        return f"当前约 {estimate} tokens / 目标 {target} tokens，略超目标，建议缩写。"
    return f"当前约 {estimate} tokens / 目标 {target} tokens，明显过长，建议先缩写。"


def memory_auto_summary_range_label(chapter_ids: list[str]) -> str:
    ids = [str(chapter_id or "").strip() for chapter_id in chapter_ids if str(chapter_id or "").strip()]
    if not ids:
        return "本批章节"
    if len(ids) == 1:
        return readable_chapter_label(ids[0])
    return f"{readable_chapter_label(ids[0])} - {readable_chapter_label(ids[-1])}"


def format_auto_memory_summary_confirmation(chapter_ids: list[str]) -> str:
    ids = [str(chapter_id or "").strip() for chapter_id in chapter_ids if str(chapter_id or "").strip()]
    range_label = memory_auto_summary_range_label(ids)
    return (
        f"已累计 {len(ids)} 章未汇总到记忆银行，范围：{range_label}。\n\n"
        "继续后会调用当前 writer 模型服务，发送当前记忆银行正文和本批已确认章节正文，用于生成记忆银行草稿。"
        "\n\n生成结果只会先显示在审阅窗口；写入记忆银行仍需再次点击“保存到记忆银行”。\n\n"
        "现在开始生成？"
    )


def format_context_package_preview(preview: dict[str, Any]) -> str:
    budget = preview.get("token_budget") if isinstance(preview.get("token_budget"), dict) else {}
    sections = preview.get("sections") if isinstance(preview.get("sections"), list) else []
    skipped = preview.get("skipped") if isinstance(preview.get("skipped"), list) else []
    visible_skipped = [item for item in skipped if isinstance(item, dict) and not quiet_context_skip(item)]
    hidden_skipped_count = max(len(skipped) - len(visible_skipped), 0)
    lines = [
        "生成时会携带的上下文",
        "------------------",
        "这里只显示会进入正文生成 prompt 的资料。没有正文的旧记忆占位不会发送给 AI。",
        f"估算 token: {budget.get('estimated_used_tokens') or 0} / {budget.get('max_context_tokens') or '-'}",
        f"会发送资料: {len(sections)} 项",
    ]
    if hidden_skipped_count:
        lines.append(f"已隐藏未填写旧占位: {hidden_skipped_count} 项。这些条目没有正文，不会发送。")
    lines.extend(["", "会发送的内容", "------------"])
    if not sections:
        lines.append("暂无可加入上下文的记忆或资料。")
    for index, item in enumerate(sections, start=1):
        label = context_section_label(item)
        title = context_item_title(item)
        lines.append(
            f"{index}. {label} | 标题={safe_record_value(title)} | 字数={safe_record_value(item.get('char_count'))}"
        )
        text = str(item.get("text") or "").strip()
        if text:
            lines.extend(["内容:", text, ""])
    lines.extend(["", "未发送的资料", "------------"])
    if not visible_skipped:
        if hidden_skipped_count:
            lines.append("只有未填写的旧占位被隐藏；没有需要你处理的未发送资料。")
        else:
            lines.append("暂无未发送资料。")
    for index, item in enumerate(visible_skipped, start=1):
        title = context_item_title(item)
        lines.append(
            f"{index}. {context_section_label(item)} | 标题={safe_record_value(title)} | 原因={context_skip_reason_label(item)}"
        )
    return "\n".join(lines).rstrip()


def quiet_context_skip(item: dict[str, Any]) -> bool:
    return item.get("source_type") == "memory_bank" and item.get("skip_reason") == "manual_text_missing"


def context_section_label(item: dict[str, Any]) -> str:
    label = str(item.get("section_label") or "").strip()
    if label:
        return label
    source_type = str(item.get("source_type") or "")
    if source_type == "memory_bank":
        return "记忆银行"
    if source_type == "planning_library":
        return memory_category_label(str(item.get("category_id") or ""))
    if source_type == "confirmed_chapter":
        return "前文定稿"
    return safe_record_value(source_type) or "资料"


def context_item_title(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    if title:
        return title
    chapter_id = str(item.get("chapter_id") or "").strip()
    if chapter_id:
        return readable_chapter_label(chapter_id)
    category_id = str(item.get("category_id") or "").strip()
    if category_id:
        return memory_category_label(category_id)
    source_type = str(item.get("source_type") or "").strip()
    if source_type == "memory_bank":
        return "未命名记忆"
    return "未命名资料"


def context_skip_reason_label(item: dict[str, Any]) -> str:
    reason = str(item.get("skip_reason") or "")
    labels = {
        "manual_text_missing": "记忆正文为空，未发送",
        "memory_item_disabled": "已关闭加入上下文，未发送",
        "planning_item_disabled": "资料已关闭加入上下文，未发送",
        "planning_item_inactive": "资料未启用，未发送",
        "planning_text_missing": "资料正文为空，未发送",
        "planning_item_metadata_only": "当前设为只保留信息，不发送正文",
        "empty_or_metadata_only": "没有可发送正文",
        "token_budget_exceeded": "超过上下文 token 预算，未发送",
    }
    return labels.get(reason, "未加入上下文")


def safe_record_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return f"{len(value)} keys"
    if isinstance(value, list):
        return f"{len(value)} items"
    text = str(value).replace("\n", " ").strip()
    return text[:160]


def format_review_details(project_id: str, review: dict[str, Any]) -> str:
    decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
    provider = review.get("provider") if isinstance(review.get("provider"), dict) else {}
    scores = review.get("scores") if isinstance(review.get("scores"), dict) else {}
    issues = review.get("issues") if isinstance(review.get("issues"), list) else []
    summary = review.get("request_summary") if isinstance(review.get("request_summary"), dict) else {}
    lines = [
        "审稿意见",
        "--------",
        f"项目: {project_id}",
        f"章节: {review.get('chapter_id') or '-'}",
        f"草稿: {review.get('draft_id') or '-'}",
        f"审稿 ID: {review.get('review_id') or '-'}",
        f"审稿类型: {review.get('review_type') or 'local'}",
        f"状态: {review.get('status') or '-'}",
        f"建议: {review.get('recommendation') or '-'}",
        f"决定: {decision.get('status') or review.get('decision') or '-'}",
        f"原因: {decision.get('reason_code') or '-'}",
        "",
        "审稿说明",
        "--------",
    ]
    finish_reason = str(provider.get("finish_reason") or "").strip().lower()
    truncated_notice = (
        "注意：这次审稿在模型输出上限处被截断，意见可能不完整。"
        "请提高创作设置里的 Max Tokens 后重新审稿，或先按已有片段处理。"
    )
    comment = str(review.get("comment") or "暂无审稿说明。")
    if finish_reason in {"length", "max_tokens", "max_output_tokens"} and truncated_notice not in comment:
        lines.extend([truncated_notice, ""])
    lines.extend([comment, "", "评分", "----"])
    if scores:
        for key, value in scores.items():
            lines.append(f"{key}: {value}")
    else:
        lines.append("暂无评分。")
    lines.extend(["", "问题", "----"])
    if issues:
        for index, issue in enumerate(issues, start=1):
            if isinstance(issue, dict):
                lines.append(
                    f"{index}. [{issue.get('severity') or '-'}] "
                    f"{issue.get('code') or '-'} - {issue.get('message') or ''}"
                )
            else:
                lines.append(f"{index}. {issue}")
    else:
        lines.append("暂无问题。")
    lines.extend(
        [
            "",
            "模型/来源",
            "--------",
            f"角色: {provider.get('role') or '-'}",
            f"服务: {provider.get('provider') or '-'}",
            f"模型: {provider.get('model') or '-'}",
            f"字数统计: {summary.get('draft_chars') or '-'}",
        ]
    )
    return "\n".join(lines).strip()


def visible_chapter_record_rows(
    chapters: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    confirmed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    draft_chapter_ids = {str(item.get("chapter_id") or "") for item in drafts if item.get("chapter_id")}
    confirmed_chapter_ids = {str(item.get("chapter_id") or "") for item in confirmed if item.get("chapter_id")}
    visible_ids = draft_chapter_ids | confirmed_chapter_ids
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        if not chapter_id or chapter_id in seen:
            continue
        if chapter_id not in visible_ids and str(chapter.get("status") or "") != "planned":
            continue
        rows.append(chapter)
        seen.add(chapter_id)
    for chapter_id in sorted(visible_ids - seen, key=lambda value: (chapter_sort_number(value), value)):
        rows.append({"chapter_id": chapter_id, "status": "draft_ready"})
    return rows


def format_prompt_preview(render: dict[str, Any]) -> str:
    summary = render.get("prompt_summary") if isinstance(render.get("prompt_summary"), dict) else {}
    package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = package.get("sections") if isinstance(package.get("sections"), list) else []
    skipped = package.get("skipped") if isinstance(package.get("skipped"), list) else []
    messages = render.get("rendered_messages") if isinstance(render.get("rendered_messages"), list) else []
    system = next((item for item in messages if isinstance(item, dict) and item.get("label") == "system_prompt"), {})
    user = next((item for item in messages if isinstance(item, dict) and item.get("label") == "draft_prompt"), {})
    lines = [
        "系统消息",
        "------",
        str(system.get("content") or "（未填写）").strip(),
        "",
        "用户消息结构",
        "----------",
        "【创作资料】（总纲/人设等稳定资料在前，章节大纲/记忆/前文在后）",
    ]
    for label in ordered_section_labels(sections):
        lines.append("")
        lines.append(f"【{label}】")
        lines.append("（生成时会填入该类已选资料；空资料会自动忽略）")
    lines.extend(
        [
            "",
            "【目标章节】",
            "（生成时填入当前章节 ID）",
            "",
            "【用户本次要求】",
            str(user.get("content") or "（未填写）").strip(),
        ]
    )
    if not sections:
        lines.extend(["", "（当前没有可加入上下文的资料段）"])
    lines.extend(
        [
            "",
            "预算",
            "----",
            f"估算总 token: {summary.get('estimated_total_tokens')}",
            f"上下文段数: {summary.get('context_section_count')}",
            f"前文章数: {summary.get('recent_confirmed_chapter_count')}",
            f"跳过段数: {len(skipped)}",
        ]
    )
    return "\n".join(lines).strip()


def format_draft_regeneration_prompt(
    *,
    chapter_id: str,
    title: str = "",
    instruction: str = "",
    default_prompt: str = "",
) -> str:
    chapter_label = str(chapter_id or "").strip() or "当前章节"
    title_text = str(title or "").strip()
    base_prompt = str(default_prompt or "").strip()
    extra_instruction = str(instruction or "").strip()
    lines = [
        "请把目标章节当作尚未写过，从当前项目资料、章节规划、世界观/人物设定、记忆银行和前文章节中重新生成一个全新草稿。",
        f"目标章节：{chapter_label}" + (f" / {title_text}" if title_text else ""),
        "不要参考上一版正文。",
        "不要读取、模仿、贴补、续改或复用上一版草稿的句子、段落、节奏和描写套路。",
        "如果上下文里出现同一章节的旧稿或旧版本痕迹，请按无效旧稿忽略；只保持项目连续性和章节目标。",
        "输出一版完整章节正文，不要输出修改说明、差异说明或对上一版的评价。",
    ]
    if base_prompt:
        lines.extend(["", "【基础写作要求】", base_prompt])
    lines.extend(
        [
            "",
            "【本次重新生成要求】",
            extra_instruction or "重新生成同一章节，保持前文连续和资料设定一致，但不要参考上一版正文。",
        ]
    )
    return "\n".join(lines).strip()


def format_memory_generation_request_preview(preview: dict[str, Any]) -> str:
    messages = preview.get("messages") if isinstance(preview.get("messages"), list) else []
    sampling = preview.get("sampling") if isinstance(preview.get("sampling"), dict) else {}
    metadata = preview.get("metadata") if isinstance(preview.get("metadata"), dict) else {}
    summary = preview.get("summary") if isinstance(preview.get("summary"), dict) else {}
    system = next((item for item in messages if isinstance(item, dict) and item.get("role") == "system"), {})
    user = next((item for item in messages if isinstance(item, dict) and item.get("role") == "user"), {})
    metadata_lines = [f"- {key}: {metadata[key]}" for key in sorted(metadata) if key != "source_chapter_ids"]
    if "source_chapter_ids" in metadata:
        metadata_lines.append(f"- source_chapter_ids: {', '.join(str(item) for item in metadata['source_chapter_ids'])}")
    return "\n".join(
        [
            "请求角色",
            "--------",
            f"Provider role: {preview.get('provider_request_role') or 'writer'}",
            f"Logical role: {preview.get('logical_role') or 'writer'}",
            "",
            "采样参数",
            "--------",
            f"temperature: {sampling.get('temperature')}",
            f"top_p: {sampling.get('top_p')}",
            f"max_tokens: {sampling.get('max_tokens')}",
            f"stream: {sampling.get('stream')}",
            "",
            "结构摘要",
            "--------",
            f"system_prompt_chars: {summary.get('system_prompt_chars')}",
            f"prompt_chars: {summary.get('prompt_chars')}",
            f"target_token_budget: {summary.get('target_token_budget')}",
            f"source_chapter_count: {summary.get('source_chapter_count')}",
            "",
            "metadata（不进入 HTTP payload，只进入本地请求摘要）",
            "---------------------------------------------",
            "\n".join(metadata_lines) if metadata_lines else "（无）",
            "",
            "System message",
            "--------------",
            str(system.get("content") or "").strip() or "（空）",
            "",
            "User message",
            "------------",
            str(user.get("content") or "").strip() or "（空）",
        ]
    ).strip()


def format_memory_generation_manual_prompt(preview: dict[str, Any]) -> str:
    messages = preview.get("messages") if isinstance(preview.get("messages"), list) else []
    system = next((item for item in messages if isinstance(item, dict) and item.get("role") == "system"), {})
    user = next((item for item in messages if isinstance(item, dict) and item.get("role") == "user"), {})
    return "\n".join(
        [
            "这是实际 API 请求会使用的提示词内容。手动复制给其他模型时，请同时复制 System message 和 User message。",
            "",
            "System message",
            "--------------",
            str(system.get("content") or "").strip() or "（空）",
            "",
            "User message",
            "------------",
            str(user.get("content") or "").strip() or "（空）",
        ]
    ).strip()


def ordered_section_labels(sections: list[object]) -> list[str]:
    from .drafts import context_section_labels_in_render_order

    return context_section_labels_in_render_order(sections)


def default_planning_id(item_type: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{safe_secret_part(item_type)}_{stamp}"


def sorted_draft_versions(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(drafts, key=lambda item: (draft_version_number(item), str(item.get("created_at") or "")))


def chapter_sort_number(chapter_id: str) -> int:
    match = re.search(r"(\d+)$", chapter_id)
    if match:
        return int(match.group(1))
    return 999999


def latest_draft_title(drafts: list[dict[str, Any]]) -> str:
    if not drafts:
        return ""
    return str(drafts[-1].get("title") or "")


def draft_version_number(item: dict[str, Any]) -> int:
    value = item.get("version")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    label = str(item.get("version_label") or "")
    match = re.fullmatch(r"ver(\d+)", label)
    if match:
        return int(match.group(1))
    return 999999


def draft_version_text(item: dict[str, Any], index: int = 0) -> str:
    label = str(item.get("version_label") or "")
    if label:
        return label
    version = draft_version_number(item)
    if version != 999999:
        return f"ver{version}"
    return f"ver{index + 1}"


def parse_optional_int(value: str, label: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError as exc:
        raise ValueError(f"{label} 必须是整数。") from exc
    if parsed < 0:
        raise ValueError(f"{label} 不能小于 0。")
    return parsed


def parse_optional_float(value: str, label: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"{label} 必须是数字。") from exc
    if parsed < 0:
        raise ValueError(f"{label} 不能小于 0。")
    return parsed


def optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def suggest_next_chapter_id(chapters: list[dict[str, Any]]) -> str:
    max_seen = 0
    width = 3
    retry_candidates: list[tuple[int, str]] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        match = re.fullmatch(r"chapter_(\d+)", chapter_id)
        if not match:
            continue
        number_text = match.group(1)
        number = int(number_text)
        if is_empty_retriable_chapter(chapter):
            retry_candidates.append((number, chapter_id))
            continue
        max_seen = max(max_seen, number)
        width = max(width, len(number_text))
    if retry_candidates:
        _number, original_id = min(retry_candidates, key=lambda item: item[0])
        return original_id
    next_number = max_seen + 1
    return format_chapter_id(next_number, chapter_number_width([next_number], minimum=width))


def is_empty_retriable_chapter(chapter: dict[str, Any]) -> bool:
    return (
        str(chapter.get("status") or "") in {"planned", "drafting", "blocked"}
        and not str(chapter.get("latest_draft_id") or "")
        and not str(chapter.get("confirmed_chapter_id") or "")
    )


def safe_secret_part(value: str) -> str:
    text = "".join(char if char.isalnum() else "_" for char in str(value or "").strip().lower())
    return text.strip("_") or "model"


def provider_display_name(provider_id: str) -> str:
    labels = {
        "mock": "离线测试",
        "openai_compatible": "OpenAI 兼容云端 API",
        "chutes_openai": "Chutes API",
        "deepseek": "DeepSeek API",
        "openrouter": "OpenRouter API",
        "local_openai_compatible": "本地 OpenAI 兼容端口",
    }
    return labels.get(provider_id, provider_id or "-")


def provider_protocol_label(provider_id: str) -> str:
    if provider_id in {"openai_compatible", "chutes_openai", "deepseek", "openrouter", "local_openai_compatible"}:
        return "OpenAI Chat Completions 兼容"
    if provider_id == "mock":
        return "离线测试协议"
    return "-"


def format_project_summary(health: dict[str, Any]) -> str:
    summary = health.get("summary", {})
    drafts = health.get("drafts", {})
    status_label = {
        "ok": "可继续创作",
        "warning": "有提示，仍可继续",
        "blocked": "有待处理项",
    }.get(str(health.get("status") or ""), "未知")
    return "\n".join(
        [
            f"作品状态: {status_label}",
            f"章节数: {summary.get('chapter_count')}    草稿数: {summary.get('draft_count')}    审稿记录: {summary.get('review_count')}",
            f"已确认章节: {summary.get('committed_chapter_count')}",
            f"最新草稿: {drafts.get('latest_draft_id') or '-'}",
            f"最新审稿: {review_decision_label(drafts.get('latest_review_decision'))} / {drafts.get('latest_review_reason_code') or '-'}",
            "详细排障信息可在“帮助 > 开发者诊断”查看。",
        ]
    )


def format_provider_summary(health: dict[str, Any]) -> str:
    providers = health.get("provider") if isinstance(health.get("provider"), dict) else {}
    smoke = health.get("smoke_tests") or {}
    lines: list[str] = []
    writer_provider = providers.get("writer") if isinstance(providers.get("writer"), dict) else {}
    for role_id, role_label in MODEL_ROLE_OPTIONS:
        configured_provider = providers.get(role_id) if isinstance(providers.get(role_id), dict) else {}
        uses_writer_fallback = role_id != "writer" and not bool(configured_provider.get("configured"))
        provider = writer_provider if uses_writer_fallback else configured_provider
        provider_id = str(provider.get("provider") or "")
        secret_state = (
            "已设置"
            if provider.get("has_api_key")
            else "本地可留空"
            if provider_id in {"openai_compatible", "local_openai_compatible", "mock"}
            else "未设置"
        )
        if uses_writer_fallback and (provider_id or provider.get("model")):
            configured = "未单独配置，沿用正文生成"
        else:
            configured = "已配置" if provider.get("configured") or provider_id or provider.get("model") else "未配置"
        lines.extend(
            [
                f"[{role_label}] {configured}",
                f"接入方式: {provider_display_name(provider_id)}",
                f"协议: {provider_protocol_label(provider_id)}",
                f"模型 ID: {provider.get('model') or '-'}",
                f"服务地址: {provider.get('base_url_host') or '-'}",
                f"密钥: {secret_state}",
            ]
        )
        config_error = str(provider.get("config_error") or "")
        if config_error:
            lines.append(f"配置提示: {config_error}")
        lines.append("")
    network_state = "已尝试" if smoke.get("latest_network_attempted") else "未联网"
    lines.extend(
        [
            f"连接检查: {smoke.get('latest_status') or '-'} / {network_state}",
            "联网生成: 生成草稿、AI审稿、AI精修由用户点击后调用；记忆银行自动总结达到批次时也会先弹窗确认。",
            "说明: 保存模型服务不会联网；测试连接、生成草稿、AI审稿、AI精修和记忆银行总结都需要用户明确触发或确认。",
        ]
    )
    return "\n".join(lines).strip()


def review_decision_label(value: object) -> str:
    labels = {
        "accepted": "已通过",
        "rejected": "未通过",
        "needs_revision": "需修改",
        "pending": "待处理",
        "": "-",
    }
    return labels.get(str(value or ""), str(value or "-"))


def draft_status_label(value: object) -> str:
    labels = {
        "draft": "草稿",
        "committed": "已确认",
        "blocked": "已阻断",
        "needs_revision": "需修改",
        "": "-",
    }
    return labels.get(str(value or ""), str(value or "-"))


def format_diagnostic_details(result: dict[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    lines = [
        "开发者诊断",
        "----------",
        f"结果: {'通过' if result.get('ok') else '需要处理'}",
        f"阻断: {summary.get('blocker_count') or 0}",
        f"提示: {summary.get('warning_count') or 0}",
        f"发现项: {summary.get('finding_count') or 0}",
        "",
    ]
    if not findings:
        lines.append("暂无发现项。")
        return "\n".join(lines).strip()
    lines.extend(["发现项", "------"])
    for index, item in enumerate(findings, start=1):
        if not isinstance(item, dict):
            continue
        severity = diagnostic_severity_label(item.get("severity"))
        code = str(item.get("code") or "-")
        path = str(item.get("path") or "-")
        message = str(item.get("message") or "")
        lines.extend(
            [
                f"{index}. [{severity}] {code}",
                f"位置: {path}",
                f"说明: {message or '-'}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def diagnostic_severity_label(value: object) -> str:
    labels = {"blocker": "阻断", "warning": "提示", "finding": "发现"}
    return labels.get(str(value or ""), str(value or "-"))
