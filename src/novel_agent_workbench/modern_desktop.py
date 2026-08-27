from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from .application_service import WorkbenchApplicationService
from .desktop_app import (
    default_planning_id,
    default_projects_root,
    default_repo_root,
    draft_status_label,
    draft_version_text,
    estimate_memory_text_tokens,
    format_auto_memory_summary_confirmation,
    format_context_package_preview,
    format_diagnostic_details,
    format_draft_regeneration_prompt,
    format_memory_generation_manual_prompt,
    format_memory_generation_request_preview,
    format_project_summary,
    format_prompt_preview,
    format_provider_summary,
    format_record_sections,
    format_review_details,
    parse_optional_float,
    parse_optional_int,
    latest_draft_title,
    memory_progress_label,
    memory_token_advice,
    optional_float,
    optional_int,
    recommended_memory_chapter_ids,
    readable_chapter_label,
    sorted_draft_versions,
    suggest_next_chapter_id,
    visible_chapter_record_rows,
)
from .memory_bank import normalize_memory_target_tokens
from .model_settings import FEATURE_DEFINITIONS
from .reviews import REVIEW_TRUNCATED_NOTICE, review_output_truncated
from .storage import utc_stamp



APP_TITLE = "小说创作工作台"
MODEL_ROLE_OPTIONS = (("writer", "正文生成"), ("scorer", "AI审稿"), ("reviser", "AI精修/改写"))
RECORD_PAGES = (
    ("connection", "连接检查", True),
    ("confirmed", "已确认章节", True),
    ("chapters", "章节列表", True),
    ("reviews", "审稿与改写", True),
    ("checklist", "出稿清单", True),
    ("export", "导出设置", True),
    ("calls", "模型调用记录", True),
    ("guide", "使用说明", False),
    ("run_log", "运行记录", False),
    ("diagnostics", "开发者诊断", False),
)
USER_GUIDE_TEXT = """基本流程
--------
1. 在左侧选择或新建作品。
2. 在资料库里录入总纲、章节计划、世界观、人物设定和项目记忆库。
3. 在创作设置里配置系统提示词、上下文数量、Temperature、Top P、Top K 等参数。
4. 在模型设置里填写接入商、API Key，并分配正文生成、审稿、精修、记忆生成使用的模型。
5. 点击“生成新章节”，需要时可先预览将发送给模型的结构，再生成草稿。
6. 草稿经过审稿、改写、确认后，才会进入后续上下文和定稿流程。
7. 记忆库可查看已保存记忆、预览发送结构，再按勾选章节生成或压缩。

安全边界
--------
保存设置不会联网。
测试连接、真实生成和导出动作都需要你主动触发。
API Key 只保存在软件级本地密钥文件，不写入作品配置或运行记录。"""
DEFAULT_PREFS = {
    "theme": "system",
    "fontFamily": "literary",
    "fontSize": 16,
    "focusMode": False,
    "hideInspector": False,
    "editorWidth": "comfort",
}
_ACTIVE_WINDOW = None


def modern_ui_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        for candidate in (
            meipass / "novel_agent_workbench" / "modern_ui",
            Path(sys.executable).resolve().parent / "novel_agent_workbench" / "modern_ui",
            Path(sys.executable).resolve().parent / "modern_ui",
        ):
            if candidate.exists():
                return candidate
    return Path(__file__).resolve().parent / "modern_ui"


def _ok(data: Any = None, **extra: Any) -> dict[str, Any]:
    payload = {"ok": True, "data": data}
    payload.update(extra)
    return payload


def _fail(message: str, **extra: Any) -> dict[str, Any]:
    payload = {"ok": False, "error": str(message)}
    payload.update(extra)
    return payload


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _slug_project_id(title: str, existing: set[str]) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", title.strip())
    slug = re.sub(r"_+", "_", slug).strip("_-")[:24].lower()
    if not slug or not slug[0].isalnum():
        slug = "novel"
    candidate = slug
    index = 2
    while candidate in existing:
        candidate = f"{slug}_{index}"
        index += 1
    return candidate


def _sampling_kwargs(settings: dict[str, Any]) -> dict[str, Any]:
    sampling = settings.get("sampling") if isinstance(settings.get("sampling"), dict) else {}
    context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
    return {
        "temperature": optional_float(sampling.get("temperature")),
        "top_p": optional_float(sampling.get("top_p")),
        "top_k": optional_int(sampling.get("top_k")),
        "min_p": optional_float(sampling.get("min_p")),
        "max_tokens": optional_int(sampling.get("max_tokens")),
        "presence_penalty": optional_float(sampling.get("presence_penalty")),
        "frequency_penalty": optional_float(sampling.get("frequency_penalty")),
        "repetition_penalty": optional_float(sampling.get("repetition_penalty")),
        "stream": True,
        "max_context_tokens": optional_int(context_settings.get("max_context_tokens")),
    }


def _normalize_generation_payload(raw: dict[str, Any]) -> dict[str, Any]:
    prompting = raw.get("prompting") if isinstance(raw.get("prompting"), dict) else {}
    sampling = raw.get("sampling") if isinstance(raw.get("sampling"), dict) else {}
    context = raw.get("context") if isinstance(raw.get("context"), dict) else {}
    review = raw.get("review") if isinstance(raw.get("review"), dict) else {}
    return {
        "prompting": {
            "system_prompt": str(prompting.get("system_prompt") or ""),
            "default_user_prompt": str(prompting.get("default_user_prompt") or ""),
            "skip_empty_sections": True,
            "section_format": "chinese_labeled_blocks",
        },
        "sampling": {
            "temperature": parse_optional_float(str(sampling.get("temperature") or ""), "Temperature"),
            "top_p": parse_optional_float(str(sampling.get("top_p") or ""), "Top P"),
            "top_k": parse_optional_int(str(sampling.get("top_k") or ""), "Top K"),
            "min_p": parse_optional_float(str(sampling.get("min_p") or ""), "Min P"),
            "max_tokens": parse_optional_int(str(sampling.get("max_tokens") or ""), "Max Tokens"),
            "presence_penalty": parse_optional_float(str(sampling.get("presence_penalty") or ""), "Presence Penalty"),
            "frequency_penalty": parse_optional_float(str(sampling.get("frequency_penalty") or ""), "Frequency Penalty"),
            "repetition_penalty": parse_optional_float(str(sampling.get("repetition_penalty") or ""), "Repetition Penalty"),
            "stream": bool(sampling.get("stream")),
        },
        "context": {
            "max_context_tokens": parse_optional_int(str(context.get("max_context_tokens") or ""), "上下文 Token 上限"),
            "recent_confirmed_chapter_count": parse_optional_int(
                str(context.get("recent_confirmed_chapter_count") or ""),
                "自动带入前文章数",
            ),
            "include_planning_library": True,
            "include_memory_bank": True,
            "include_world_and_character": True,
            "include_recent_chapters": bool(context.get("include_recent_chapters", True)),
        },
        "review": {
            "scorer_enabled": bool(review.get("scorer_enabled")),
            "manual_review_when_disabled": True,
            "system_prompt": str(review.get("system_prompt") or ""),
            "task_prompt": str(review.get("task_prompt") or ""),
        },
    }


def _chapter_sort_key(chapter_id: str) -> tuple[int, int, str]:
    match = re.search(r"(\d+)$", chapter_id)
    if match:
        return (0, int(match.group(1)), chapter_id)
    return (1, 0, chapter_id)


def build_workspace_tree(app: WorkbenchApplicationService) -> list[dict[str, Any]]:
    projects = []
    for item in app.list_projects():
        project_id = str(item.get("project_id") or "")
        if not project_id:
            continue
        projects.append(
            {
                "project_id": project_id,
                "title": str(item.get("title") or project_id),
                "updated_at": str(item.get("updated_at") or ""),
                "chapters": build_project_chapters(app, project_id),
            }
        )
    return projects


def build_project_chapters(app: WorkbenchApplicationService, project_id: str) -> list[dict[str, Any]]:
    try:
        confirmed = app.list_confirmed_chapters(project_id)
    except Exception:
        confirmed = []
    try:
        drafts = app.list_drafts(project_id)
    except Exception:
        drafts = []

    confirmed_by_chapter = {str(item.get("chapter_id") or ""): item for item in confirmed if item.get("chapter_id")}
    confirmed_draft_ids = {str(item.get("source_draft_id") or "") for item in confirmed if item.get("source_draft_id")}
    drafts_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for draft in drafts:
        chapter_id = str(draft.get("chapter_id") or "") or "_unassigned"
        drafts_by_chapter.setdefault(chapter_id, []).append(draft)

    chapter_ids = sorted(set(confirmed_by_chapter) | {key for key in drafts_by_chapter if key != "_unassigned"}, key=_chapter_sort_key)
    chapters: list[dict[str, Any]] = []
    for chapter_id in chapter_ids:
        chapter = confirmed_by_chapter.get(chapter_id, {})
        versions = sorted_draft_versions(drafts_by_chapter.get(chapter_id, []))
        title = str(chapter.get("title") or latest_draft_title(versions) or chapter_id)
        chapters.append(
            {
                "chapter_id": chapter_id,
                "title": title,
                "status": "confirmed" if chapter_id in confirmed_by_chapter else "draft",
                "drafts": [
                    {
                        "draft_id": str(draft.get("draft_id") or ""),
                        "title": str(draft.get("title") or ""),
                        "status": "committed" if str(draft.get("draft_id") or "") in confirmed_draft_ids else str(draft.get("status") or "draft"),
                        "version_label": draft_version_text(draft, index),
                    }
                    for index, draft in enumerate(versions)
                    if draft.get("draft_id")
                ],
            }
        )
    return chapters


class WorkbenchBridge:
    def __init__(self, *, projects_root: Path, repo_root: Path) -> None:
        self.projects_root = projects_root
        self.repo_root = repo_root
        self.app = WorkbenchApplicationService.open(projects_root)
        self._busy = False
        self._busy_lock = threading.Lock()
        self._run_log: list[str] = []

    def bind_window(self, window: Any) -> None:
        global _ACTIVE_WINDOW
        _ACTIVE_WINDOW = window

    def _prefs_path(self) -> Path:
        return self.projects_root.parent / "ui_preferences.json"

    def _read_prefs(self) -> dict[str, Any]:
        prefs = dict(DEFAULT_PREFS)
        path = self._prefs_path()
        if not path.exists():
            return prefs
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return prefs
        if isinstance(loaded, dict):
            prefs.update({key: loaded[key] for key in DEFAULT_PREFS if key in loaded})
        return prefs

    def _write_prefs(self, prefs: dict[str, Any]) -> dict[str, Any]:
        merged = self._read_prefs()
        merged.update(prefs)
        path = self._prefs_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def _push(self, event: str, payload: Any = None) -> None:
        if _ACTIVE_WINDOW is None:
            return
        script = f"window.__workbenchPush({json.dumps(event)}, {json.dumps(_jsonable(payload), ensure_ascii=False)})"
        try:
            _ACTIVE_WINDOW.evaluate_js(script)
        except Exception:
            pass

    def _begin_job(self) -> bool:
        with self._busy_lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def _end_job(self) -> None:
        with self._busy_lock:
            self._busy = False

    def _log(self, text: str) -> None:
        line = f"{utc_stamp()}  {str(text).rstrip()}"
        self._run_log.append(line)
        if len(self._run_log) > 500:
            self._run_log = self._run_log[-400:]

    def _run_job(self, name: str, worker: Callable[[], Any], *, on_done: str) -> dict[str, Any]:
        if not self._begin_job():
            return _fail("已有任务正在进行，请等待完成。")
        self._log(f"开始任务: {name}")

        def run() -> None:
            try:
                result = worker()
            except Exception as exc:
                self._log(f"任务失败: {name}  {exc}")
                self._push(on_done, {"ok": False, "error": str(exc)})
            else:
                self._log(f"任务完成: {name}")
                self._push(on_done, _ok(_jsonable(result)))
            finally:
                self._end_job()

        threading.Thread(target=run, name=name, daemon=True).start()
        return _ok({"started": True})

    def _stream_hooks(self, content_event: str, *, chapter_id: str = "") -> tuple[Callable[[str], None], Callable[[str], None], Callable[[], None]]:
        seen = {"reason": False, "content": False}

        def payload(text: str) -> dict[str, Any]:
            data = {"text": text}
            if chapter_id:
                data["chapter_id"] = chapter_id
            return data

        def mark_sent() -> None:
            self._push("think_status", {"phase": "sent"})

        def on_reason(chunk: str) -> None:
            if not seen["reason"]:
                seen["reason"] = True
                self._push("think_status", {"phase": "thinking"})
            self._push("think_chunk", payload(chunk))

        def on_content(chunk: str) -> None:
            if not seen["content"]:
                seen["content"] = True
                self._push("think_status", {"phase": "writing"})
            self._push(content_event, payload(chunk))

        return on_content, on_reason, mark_sent

    def bootstrap(self) -> dict[str, Any]:
        return _ok(
            {
                "title": APP_TITLE,
                "projectsRoot": str(self.projects_root),
                "prefs": self._read_prefs(),
                "workspace": build_workspace_tree(self.app),
            }
        )

    def save_prefs(self, prefs: dict[str, Any] | None = None) -> dict[str, Any]:
        return _ok(self._write_prefs(prefs or {}))

    def refresh_workspace(self) -> dict[str, Any]:
        try:
            self.app = WorkbenchApplicationService.open(self.projects_root)
            return _ok(build_workspace_tree(self.app))
        except Exception as exc:
            return _fail(f"项目列表读取失败: {exc}")

    def project_overview(self, project_id: str) -> dict[str, Any]:
        try:
            state = self.app.project_state(project_id)
        except Exception as exc:
            return _fail(f"作品概览读取失败: {exc}")
        roles = state.get("provider_roles") if isinstance(state.get("provider_roles"), dict) else {}
        configured = sum(1 for role, _label in MODEL_ROLE_OPTIONS if bool((roles.get(role) or {}).get("configured")))
        return _ok(
            {
                "project_id": project_id,
                "chapter_count": state.get("chapter_count", 0),
                "draft_count": state.get("draft_count", 0),
                "committed_chapter_count": state.get("committed_chapter_count", 0),
                "review_count": state.get("review_count", 0),
                "planning_item_count": state.get("planning_item_count", 0),
                "memory_bank_item_count": state.get("memory_bank_item_count", 0),
                "model_status": f"模型 {configured}/{len(MODEL_ROLE_OPTIONS)} 已配置",
                "configured_roles": configured,
            }
        )

    def rename_project(self, project_id: str, title: str) -> dict[str, Any]:
        name = str(title or "").strip()
        if not name:
            return _fail("作品标题不能为空。")
        try:
            result = self.app.rename_project(project_id, title=name)
        except Exception as exc:
            return _fail(f"重命名作品失败: {exc}")
        return _ok({"result": _jsonable(result), "workspace": build_workspace_tree(self.app)})

    def rename_chapter(self, project_id: str, chapter_id: str, title: str) -> dict[str, Any]:
        name = str(title or "").strip()
        if not name:
            return _fail("章节标题不能为空。")
        try:
            result = self.app.rename_chapter(project_id, chapter_id, title=name)
        except Exception as exc:
            return _fail(f"重命名章节失败: {exc}")
        return _ok({"result": _jsonable(result), "workspace": build_workspace_tree(self.app)})

    def create_project(self, title: str, project_id: str = "") -> dict[str, Any]:
        title_text = str(title or "").strip()
        existing = {str(item.get("project_id") or "") for item in self.app.list_projects()}
        ident = str(project_id or "").strip() or _slug_project_id(title_text or "novel", existing)
        try:
            created = self.app.create_project(ident, title=title_text or ident)
        except Exception as exc:
            return _fail(f"新建作品失败: {exc}")
        return _ok({"project": _jsonable(created), "workspace": build_workspace_tree(self.app)})

    def suggest_chapter(self, project_id: str) -> dict[str, Any]:
        try:
            settings = self.app.generation_settings(project_id)
            chapter_id = suggest_next_chapter_id(self.app.list_chapters(project_id))
        except Exception:
            settings = {}
            chapter_id = "chapter_001"
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        return _ok(
            {
                "chapter_id": chapter_id,
                "default_prompt": str(prompting.get("default_user_prompt") or ""),
            }
        )

    def open_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        try:
            draft = self.app.read_draft(project_id, draft_id)
            chapter_id = str(draft.get("chapter_id") or "")
            versions = sorted_draft_versions(
                [item for item in self.app.list_drafts(project_id) if str(item.get("chapter_id") or "") == chapter_id]
            )
        except Exception as exc:
            return _fail(f"打开稿件失败: {exc}")
        draft_ids = [str(item.get("draft_id") or "") for item in versions if item.get("draft_id")]
        if draft_id not in draft_ids:
            draft_ids.append(draft_id)
        index = draft_ids.index(draft_id)
        try:
            review = self.app.find_ai_review_for_draft(project_id, draft_id)
        except Exception:
            review = None
        return _ok(
            {
                "project_id": project_id,
                "draft_id": draft_id,
                "chapter_id": str(draft.get("chapter_id") or ""),
                "title": str(draft.get("title") or draft.get("chapter_id") or "未命名章节"),
                "status": str(draft.get("status") or ""),
                "status_label": draft_status_label(draft.get("status")),
                "version_label": str(draft.get("version_label") or draft_version_text(draft, index)),
                "content": str(draft.get("content") or ""),
                "draft_ids": draft_ids,
                "index": index,
                "has_review": review is not None,
                "review": self._review_payload(project_id, review) if review else None,
            }
        )

    def save_draft(self, project_id: str, draft_id: str, text: str) -> dict[str, Any]:
        try:
            result = self.app.update_draft_content(project_id, draft_id, text=str(text or ""))
        except Exception as exc:
            return _fail(f"保存编辑失败: {exc}")
        return _ok(_jsonable(result))

    def generate_draft(self, project_id: str, chapter_id: str, title: str, prompt: str) -> dict[str, Any]:
        chapter = str(chapter_id or "").strip()
        user_prompt = str(prompt or "").strip()
        if not chapter:
            return _fail("章节 ID 不能为空。")
        if not user_prompt:
            return _fail("本次写作要求不能为空。")
        try:
            settings = self.app.generation_settings(project_id)
        except Exception as exc:
            return _fail(f"读取创作设置失败: {exc}")
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        kwargs = _sampling_kwargs(settings)

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("draft_chunk", chapter_id=chapter)
            mark_sent()
            return self.app.generate_context_draft(
                project_id,
                chapter_id=chapter,
                title=str(title or "").strip(),
                prompt=user_prompt,
                system_prompt=str(prompting.get("system_prompt") or ""),
                stream_callback=on_content,
                reasoning_callback=on_reason,
                metadata={"ui_action": "modern_generate_draft"},
                **kwargs,
            )

        return self._run_job("ModernDraftGenerate", worker, on_done="draft_done")

    def rewrite_draft(self, project_id: str, draft_id: str, instruction: str = "") -> dict[str, Any]:
        try:
            draft = self.app.read_draft(project_id, draft_id)
            settings = self.app.generation_settings(project_id)
        except Exception as exc:
            return _fail(f"读取当前稿件失败: {exc}")
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        chapter_id = str(draft.get("chapter_id") or "")
        prompt = format_draft_regeneration_prompt(
            chapter_id=chapter_id,
            title=str(draft.get("title") or ""),
            instruction=str(instruction or ""),
            default_prompt=str(prompting.get("default_user_prompt") or ""),
        )
        kwargs = _sampling_kwargs(settings)

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("draft_chunk", chapter_id=chapter_id)
            mark_sent()
            return self.app.generate_context_draft(
                project_id,
                chapter_id=chapter_id,
                title=str(draft.get("title") or ""),
                prompt=prompt,
                system_prompt=str(prompting.get("system_prompt") or ""),
                stream_callback=on_content,
                reasoning_callback=on_reason,
                metadata={
                    "ui_action": "modern_regenerate_chapter",
                    "source_draft_id": draft_id,
                    "previous_draft_body_excluded": True,
                },
                **kwargs,
            )

        return self._run_job("ModernDraftRewrite", worker, on_done="draft_done")

    def refine_draft(self, project_id: str, draft_id: str, instruction: str = "") -> dict[str, Any]:
        try:
            review = self.app.find_ai_review_for_draft(project_id, draft_id)
            settings = self.app.generation_settings(project_id)
            draft = self.app.read_draft(project_id, draft_id)
        except Exception as exc:
            return _fail(f"读取精修所需资料失败: {exc}")
        if review is None:
            return _fail("当前草稿还没有 AI 审稿，不能根据审稿精修。")
        kwargs = _sampling_kwargs(settings)
        chapter_id = str(draft.get("chapter_id") or "")

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("draft_chunk", chapter_id=chapter_id)
            mark_sent()
            return self.app.refine_draft_from_ai_review(
                project_id,
                draft_id,
                review_id=str(review.get("review_id") or ""),
                instruction=str(instruction or ""),
                stream_callback=on_content,
                reasoning_callback=on_reason,
                **kwargs,
            )

        return self._run_job("ModernDraftRefine", worker, on_done="draft_done")

    def ai_review(self, project_id: str, draft_id: str) -> dict[str, Any]:
        try:
            existing = self.app.find_ai_review_for_draft(project_id, draft_id)
        except Exception:
            existing = None
        if existing is not None:
            return _ok({"existing": True, "review": self._review_payload(project_id, existing)})
        try:
            settings = self.app.generation_settings(project_id)
        except Exception as exc:
            return _fail(f"读取创作设置失败: {exc}")
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("review_chunk")
            mark_sent()
            sampling = settings.get("sampling") if isinstance(settings.get("sampling"), dict) else {}
            result = self.app.ai_review_draft(
                project_id,
                draft_id,
                max_context_tokens=optional_int(context_settings.get("max_context_tokens")),
                max_tokens=optional_int(sampling.get("max_tokens")),
                stream=True,
                stream_callback=on_content,
                reasoning_callback=on_reason,
            )
            review = self.app.read_review(project_id, str(result.get("review_id") or ""))
            return self._review_payload(project_id, review)

        return self._run_job("ModernAiReview", worker, on_done="review_done")

    def confirm_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        try:
            draft = self.app.read_draft(project_id, draft_id)
            if str(draft.get("status") or "") == "committed":
                return _fail("这个版本已经是确认稿。")
            self.app.accept_draft_manually(project_id, draft_id, reason_code="desktop_confirm")
            result = self.app.commit_draft(project_id, draft_id, replace_existing=True)
        except Exception as exc:
            return _fail(f"确认稿件失败: {exc}")
        return _ok(_jsonable(result))

    def library(self, project_id: str) -> dict[str, Any]:
        try:
            planning = self.app.list_planning_items(project_id, include_text=True)
            memory = self.app.ensure_main_memory_item(project_id)
            preview = self.app.context_package_preview(project_id, include_text=False)
        except Exception as exc:
            return _fail(f"资料库读取失败: {exc}")
        return _ok(
            {
                "planning": _jsonable(planning),
                "memory": _jsonable(memory),
                "context": _jsonable(preview),
            }
        )

    def model_state(self) -> dict[str, Any]:
        try:
            raw = self.app.model_settings_state()
        except Exception as exc:
            return _fail(f"读取模型设置失败: {exc}")
        providers = [_jsonable(item) for item in raw.get("providers") or []]
        models = [_jsonable(item) for item in raw.get("models") or []]
        return _ok(
            {
                "providers": providers,
                "models": models,
                "primary_model_ref": str(raw.get("primary_model_ref") or ""),
                "feature_assignments": raw.get("feature_assignments") or {},
                "features": [{"id": item[0], "label": item[1], "role": item[2]} for item in FEATURE_DEFINITIONS],
                "adapters": [
                    {"id": "openai_compatible", "label": "OpenAI 兼容"},
                    {"id": "siliconflow", "label": "硅基流动"},
                    {"id": "chutes_openai", "label": "Chutes"},
                    {"id": "deepseek", "label": "DeepSeek"},
                    {"id": "openrouter", "label": "OpenRouter"},
                    {"id": "local_openai_compatible", "label": "本地兼容端口"},
                ],
            }
        )

    def save_provider(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        try:
            timeout = float(str(data.get("timeout_seconds") or 300))
            profile = self.app.upsert_provider_profile(
                str(data.get("profile_id") or ""),
                display_name=str(data.get("display_name") or ""),
                adapter=str(data.get("adapter") or "openai_compatible"),
                base_url=str(data.get("base_url") or ""),
                timeout_seconds=timeout,
            )
            profile_id = str(profile.get("profile_id") or "")
            new_key = str(data.get("api_key") or "").strip()
            if new_key:
                self.app.set_provider_profile_secret(profile_id, new_key)
        except Exception as exc:
            return _fail(f"保存接入商失败: {exc}")
        refreshed = self.model_state()
        return _ok({"profile_id": profile_id, **(refreshed.get("data") or {})})

    def clear_provider_key(self, profile_id: str) -> dict[str, Any]:
        try:
            self.app.clear_provider_profile_secret(str(profile_id or ""))
        except Exception as exc:
            return _fail(str(exc))
        return self.model_state()

    def delete_provider(self, profile_id: str) -> dict[str, Any]:
        try:
            self.app.delete_provider_profile(str(profile_id or ""))
        except Exception as exc:
            return _fail(str(exc))
        return self.model_state()

    def refresh_models(self, profile_id: str) -> dict[str, Any]:
        ident = str(profile_id or "").strip()
        if not ident:
            return _fail("请先选择接入商。")

        def worker() -> dict[str, Any]:
            result = self.app.refresh_provider_models(ident)
            state = self.model_state()
            return {"refresh": _jsonable(result), **(state.get("data") or {})}

        return self._run_job("ModernModelRefresh", worker, on_done="models_done")

    def add_model(self, profile_id: str, model_id: str, display_name: str = "") -> dict[str, Any]:
        try:
            self.app.add_manual_model(str(profile_id or ""), str(model_id or ""), display_name=str(display_name or ""))
        except Exception as exc:
            return _fail(str(exc))
        return self.model_state()

    def toggle_model(self, model_ref: str, enabled: bool) -> dict[str, Any]:
        try:
            self.app.set_model_enabled(str(model_ref or ""), bool(enabled))
        except Exception as exc:
            return _fail(str(exc))
        return self.model_state()

    def set_models_enabled(self, model_refs: list[str] | None = None, enabled: bool = True) -> dict[str, Any]:
        refs = [str(item or "").strip() for item in (model_refs or []) if str(item or "").strip()]
        if not refs:
            return _fail("请先选择模型。")
        try:
            for model_ref in refs:
                self.app.set_model_enabled(model_ref, bool(enabled))
        except Exception as exc:
            return _fail(str(exc))
        return self.model_state()

    def save_assignments(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        try:
            self.app.update_model_assignments(
                primary_model_ref=str(data.get("primary_model_ref") or ""),
                feature_assignments=data.get("feature_assignments")
                if isinstance(data.get("feature_assignments"), dict)
                else {},
            )
        except Exception as exc:
            return _fail(f"保存功能分配失败: {exc}")
        return self.model_state()

    def memory_state(self, project_id: str) -> dict[str, Any]:
        try:
            memory = self.app.ensure_main_memory_item(project_id)
            items = self.app.list_memory_items(project_id, include_text=True)
            chapters = self.app.list_confirmed_chapters(project_id)
        except Exception as exc:
            return _fail(f"记忆库读取失败: {exc}")
        text = str(memory.get("text") or "")
        target = normalize_memory_target_tokens(memory.get("target_token_budget"))
        estimated = estimate_memory_text_tokens(text)
        return _ok(
            {
                "memory": _jsonable(memory),
                "items": _jsonable(items),
                "chapters": [
                    {
                        "chapter_id": str(item.get("chapter_id") or ""),
                        "title": str(item.get("title") or ""),
                        "label": readable_chapter_label(str(item.get("chapter_id") or "")),
                        "committed_at": str(item.get("committed_at") or ""),
                    }
                    for item in chapters
                    if item.get("chapter_id")
                ],
                "recommended": recommended_memory_chapter_ids(memory, chapters),
                "progress": memory_progress_label(memory, chapters),
                "token_advice": memory_token_advice(estimated, target),
                "estimated_tokens": estimated,
                "target_tokens": target,
            }
        )

    def save_memory_workspace(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        project_id = str(data.get("project_id") or "")
        memory_id = str(data.get("memory_id") or "main_memory_bank")
        text = str(data.get("text") or "").strip()
        if not text:
            return _fail("记忆银行正文不能为空。可以先写一版简短总结再保存。")
        chapter_ids = [str(item) for item in (data.get("chapter_ids") or []) if str(item)]
        target = normalize_memory_target_tokens(data.get("target_tokens"))
        try:
            self.app.set_memory_text(
                project_id,
                memory_id,
                text,
                source_chapter_ids=chapter_ids,
                target_token_budget=target,
            )
            self.app.set_memory_item_enabled(
                project_id,
                memory_id,
                enabled=bool(data.get("enabled", True)),
                reason_code="modern_toggle",
                target_token_budget=target,
            )
        except Exception as exc:
            return _fail(f"保存记忆库失败: {exc}")
        return self.memory_state(project_id)

    def generate_memory(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        project_id = str(data.get("project_id") or "")
        chapter_ids = [str(item) for item in (data.get("chapter_ids") or []) if str(item)]
        if not chapter_ids:
            return _fail("请先勾选要写入记忆的已确认章节。")

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("memory_chunk")
            mark_sent()
            chapters = [self.app.read_confirmed_chapter(project_id, chapter_id) for chapter_id in chapter_ids]
            return self.app.generate_memory_bank_text(
                project_id,
                current_memory=str(data.get("current_memory") or ""),
                chapters=chapters,
                target_token_budget=normalize_memory_target_tokens(data.get("target_tokens")),
                stream_callback=on_content,
                reasoning_callback=on_reason,
            )

        return self._run_job("ModernMemoryGenerate", worker, on_done="memory_done")

    def preview_memory_generation(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        project_id = str(data.get("project_id") or "")
        chapter_ids = [str(item) for item in (data.get("chapter_ids") or []) if str(item)]
        if not chapter_ids:
            return _fail("请先勾选要写入记忆的已确认章节。")
        try:
            chapters = [self.app.read_confirmed_chapter(project_id, chapter_id) for chapter_id in chapter_ids]
            preview = self.app.preview_memory_generation_request(
                project_id,
                current_memory=str(data.get("current_memory") or ""),
                chapters=chapters,
                target_token_budget=normalize_memory_target_tokens(data.get("target_tokens")),
            )
        except Exception as exc:
            return _fail(f"生成记忆预览失败: {exc}")
        return _ok(
            {
                "preview": _jsonable(preview),
                "prompt_text": format_memory_generation_manual_prompt(preview),
                "request_text": format_memory_generation_request_preview(preview),
            }
        )

    def preview_memory_compression(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        current = str(data.get("current_memory") or "").strip()
        if not current:
            return _fail("当前没有可压缩的记忆正文。")
        try:
            preview = self.app.preview_memory_compression_request(
                str(data.get("project_id") or ""),
                current_memory=current,
                target_token_budget=normalize_memory_target_tokens(data.get("target_tokens")),
            )
        except Exception as exc:
            return _fail(f"生成缩写预览失败: {exc}")
        return _ok(
            {
                "preview": _jsonable(preview),
                "prompt_text": format_memory_generation_manual_prompt(preview),
                "request_text": format_memory_generation_request_preview(preview),
            }
        )

    def recent_model_calls(self, project_id: str) -> dict[str, Any]:
        try:
            log = self.app.provider_call_log(project_id)
        except Exception as exc:
            return _fail(f"读取模型调用记录失败: {exc}")
        raw_calls = log.get("calls") if isinstance(log, dict) and isinstance(log.get("calls"), list) else []
        calls = [item for item in raw_calls if isinstance(item, dict)]
        recent = list(reversed(calls[-20:]))
        lines = ["最近模型调用", "------------"]
        if not recent:
            lines.append("暂无记录。")
        else:
            for item in recent:
                keys = item.get("request_summary") if isinstance(item.get("request_summary"), dict) else {}
                meta = keys.get("metadata_keys") if isinstance(keys.get("metadata_keys"), list) else []
                error = str(item.get("error_type") or "").strip()
                lines.append(
                    f"{item.get('timestamp') or '-'}  {item.get('status') or '-'}  "
                    f"{item.get('provider') or '-'} / {item.get('model') or '-'}  "
                    f"role={item.get('role') or '-'}  "
                    f"{error or 'ok'}  "
                    f"prompt={keys.get('prompt_chars') or 0}  "
                    f"{', '.join(str(key) for key in meta)}"
                )
        return _ok({"details": "\n".join(lines), "calls": _jsonable(recent)})

    def records_state(self, kind: str = "connection", project_id: str = "") -> dict[str, Any]:
        page = next((item for item in RECORD_PAGES if item[0] == kind), RECORD_PAGES[0])
        kind, title, needs_project = page
        if needs_project and not str(project_id or "").strip():
            return _fail("请先选择或新建一个作品。")
        try:
            details = self._records_details(kind, str(project_id or "").strip())
        except Exception as exc:
            self._log(f"读取{title}失败: {exc}")
            return _fail(f"{title}读取失败: {exc}")
        return _ok(
            {
                "kind": kind,
                "title": title,
                "details": details,
                "pages": [{"id": item[0], "label": item[1], "needs_project": item[2]} for item in RECORD_PAGES],
            }
        )

    def _records_details(self, kind: str, project_id: str) -> str:
        if kind == "connection":
            return self._format_connection_check(project_id)
        if kind == "confirmed":
            return self._format_confirmed_chapters(project_id)
        if kind == "chapters":
            return format_record_sections(
                [
                    (
                        "章节",
                        visible_chapter_record_rows(
                            self.app.list_chapters(project_id),
                            self.app.list_drafts(project_id),
                            self.app.list_confirmed_chapters(project_id),
                        ),
                        ("chapter_id", "title", "status", "planned_at", "updated_at"),
                    )
                ]
            )
        if kind == "reviews":
            return format_record_sections(
                [
                    ("草稿", self.app.list_drafts(project_id), ("draft_id", "chapter_id", "status", "provider", "created_at")),
                    (
                        "审稿记录",
                        self.app.list_reviews(project_id),
                        ("review_id", "review_type", "draft_id", "decision", "reason_code", "created_at"),
                    ),
                    (
                        "改写请求",
                        self.app.list_revision_requests(project_id),
                        ("revision_request_id", "review_id", "status", "created_at"),
                    ),
                    (
                        "人工改写任务",
                        self.app.list_manual_rewrite_tasks(project_id),
                        ("task_id", "status", "draft_id", "created_at"),
                    ),
                ]
            )
        if kind == "checklist":
            return format_record_sections(
                [
                    (
                        "功能状态",
                        [
                            {
                                "status": "可查看",
                                "available": "可以查看已确认章节和内部定稿检查记录。",
                                "not_ready": "尚未提供一键正式出版导出。",
                            }
                        ],
                        ("status", "available", "not_ready"),
                    ),
                    (
                        "已确认章节",
                        self.app.list_confirmed_chapters(project_id),
                        ("chapter_id", "title", "draft_id", "committed_at"),
                    ),
                    ("定稿检查", self.app.list_final_assembly_gates(project_id), ("status", "created_at")),
                    ("模型执行说明", self.app.list_final_provider_runbooks(project_id), ("status", "created_at")),
                ]
            )
        if kind == "export":
            return self._format_export_settings(project_id)
        if kind == "calls":
            calls = self.recent_model_calls(project_id)
            call_text = str((calls.get("data") or {}).get("details") or "暂无记录。") if calls.get("ok") else str(calls.get("error") or "")
            extra = format_record_sections(
                [
                    (
                        "连接检查记录",
                        self.app.list_provider_smoke_tests(project_id),
                        ("status", "provider", "model", "created_at"),
                    ),
                    (
                        "真实生成记录",
                        self.app.list_final_provider_real_executions(project_id),
                        ("status", "provider", "model", "created_at"),
                    ),
                ]
            )
            return f"{call_text}\n\n{extra}".strip()
        if kind == "guide":
            return USER_GUIDE_TEXT
        if kind == "run_log":
            return "\n".join(self._run_log) if self._run_log else "暂无运行记录。"
        if kind == "diagnostics":
            result = self.app.prepublish_check(repo_root=self.repo_root)
            summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
            self._log(
                "开发者诊断: "
                f"ok={result.get('ok')} "
                f"blocker={summary.get('blocker_count')} "
                f"warning={summary.get('warning_count')} "
                f"finding={summary.get('finding_count')}"
            )
            return format_diagnostic_details(result)
        raise ValueError(f"Unknown records page: {kind}")

    def _format_connection_check(self, project_id: str) -> str:
        lines = ["连接检查", "--------", "此检查只读取本地配置，不会向模型服务发送请求。", ""]
        for role, label in MODEL_ROLE_OPTIONS:
            try:
                status = self.app.provider_status(project_id, role)
            except Exception as exc:
                status = {"ok": False, "role": role, "message": str(exc)}
            lines.extend(
                [
                    f"{label} ({role})",
                    f"  可用: {'是' if status.get('ok') else '否'}",
                    f"  服务: {status.get('provider') or '-'}",
                    f"  模型: {status.get('model') or '-'}",
                    f"  已配置密钥: {'是' if status.get('has_api_key') else '否'}",
                    f"  说明: {status.get('message') or '-'}",
                    "",
                ]
            )
        try:
            model_state = self.app.model_settings_state()
        except Exception:
            model_state = {}
        assignments = model_state.get("feature_assignments") if isinstance(model_state.get("feature_assignments"), dict) else {}
        primary = str(model_state.get("primary_model_ref") or "").strip() or "（未设置主模型）"
        lines.extend(["功能分配", "--------", f"主模型: {primary}"])
        for feature_id, label, _role in FEATURE_DEFINITIONS:
            item = assignments.get(feature_id) if isinstance(assignments.get(feature_id), dict) else {}
            mode = str(item.get("mode") or "inherit")
            ref = str(item.get("model_ref") or "").strip()
            if mode == "model" and ref:
                lines.append(f"{label}: 单独指定 {ref}")
            else:
                lines.append(f"{label}: 使用主模型")
        return "\n".join(lines).strip()

    def _format_confirmed_chapters(self, project_id: str) -> str:
        chapters = self.app.list_confirmed_chapters(project_id)
        lines = ["已确认章节", "----------"]
        if not chapters:
            lines.append("暂无记录。")
            return "\n".join(lines)
        for index, item in enumerate(chapters, start=1):
            chapter_id = str(item.get("chapter_id") or "")
            try:
                chapter = self.app.read_confirmed_chapter(project_id, chapter_id)
                content = str(chapter.get("content") or "").strip()
            except Exception as exc:
                content = f"（读取正文失败：{exc}）"
            title = str(item.get("title") or chapter_id)
            lines.extend(
                [
                    f"{index}. 章节={chapter_id} | 标题={title} | 来源草稿={item.get('source_draft_id') or '-'} | 确认时间={item.get('committed_at') or '-'}",
                    "正文:",
                    content or "（暂无正文）",
                    "",
                ]
            )
        return "\n".join(lines).rstrip()

    def _format_export_settings(self, project_id: str) -> str:
        settings_path = self.projects_root / project_id / "data" / "export_settings.json"
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            return f"读取导出设置失败:\n{exc}"
        if not isinstance(settings, dict):
            settings = {}
        return "\n".join(
            [
                "导出设置",
                "--------",
                "TXT: 可用。导出范围为当前作品的已确认章节，不包含草稿、审稿记录、API Key 或本地私密设置。",
                "DOCX/ZIP: 开发中。",
                "",
                f"TXT设置: {settings.get('txt_enabled', '默认启用')}",
                f"ZIP: {settings.get('zip_enabled', '-')}",
                f"DOCX: {settings.get('docx_enabled', '-')}",
                f"范围: {settings.get('export_scope', '-')}",
                f"文件: {settings_path}",
            ]
        )

    def compress_memory(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        project_id = str(data.get("project_id") or "")
        current = str(data.get("current_memory") or "").strip()
        if not current:
            return _fail("当前没有可压缩的记忆正文。")

        def worker() -> dict[str, Any]:
            on_content, on_reason, mark_sent = self._stream_hooks("memory_chunk")
            mark_sent()
            return self.app.generate_memory_bank_compression_text(
                project_id,
                current_memory=current,
                target_token_budget=normalize_memory_target_tokens(data.get("target_tokens")),
                stream_callback=on_content,
                reasoning_callback=on_reason,
            )

        return self._run_job("ModernMemoryCompress", worker, on_done="memory_done")

    def planning_state(self, project_id: str, kind: str = "outline") -> dict[str, Any]:
        types = {"outline", "chapter_plan"} if kind == "outline" else {"character_plan", "world_plan", "constraint"}
        labels = {
            "outline": "总纲",
            "chapter_plan": "章节计划",
            "character_plan": "角色设定",
            "world_plan": "世界观设定",
            "constraint": "写作约束",
        }
        try:
            items = [
                item
                for item in self.app.list_planning_items(project_id, include_text=True)
                if str(item.get("item_type") or "") in types
            ]
        except Exception as exc:
            return _fail(f"资料库读取失败: {exc}")
        return _ok(
            {
                "kind": kind,
                "items": _jsonable(items),
                "types": [{"id": key, "label": labels[key]} for key in sorted(types, key=lambda value: list(labels).index(value))],
                "adherence": [
                    {"id": "soft", "label": "参考即可"},
                    {"id": "balanced", "label": "正常遵守"},
                    {"id": "strict", "label": "严格遵守"},
                ],
            }
        )

    def save_planning(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        project_id = str(data.get("project_id") or "")
        planning_id = str(data.get("planning_id") or "").strip() or default_planning_id(str(data.get("item_type") or "outline"))
        creating = bool(data.get("creating"))
        fields = {
            "text": str(data.get("text") or ""),
            "title": str(data.get("title") or ""),
            "item_type": str(data.get("item_type") or "outline"),
            "active": bool(data.get("active", True)),
            "enabled": bool(data.get("active", True)),
            "adherence_level": str(data.get("adherence_level") or "balanced"),
            "chapter_range": str(data.get("chapter_range") or ""),
        }
        try:
            if creating:
                result = self.app.create_planning_item(project_id, planning_id, **fields)
            else:
                result = self.app.update_planning_item(project_id, planning_id, **fields)
        except Exception as exc:
            return _fail(f"保存资料失败: {exc}")
        kind = "outline" if fields["item_type"] in {"outline", "chapter_plan"} else "world"
        state = self.planning_state(project_id, kind)
        return _ok({"saved_id": str(result.get("planning_id") or planning_id), **(state.get("data") or {})})

    def delete_planning(self, project_id: str, planning_id: str, kind: str = "world") -> dict[str, Any]:
        try:
            self.app.delete_planning_item(project_id, planning_id)
        except Exception as exc:
            return _fail(f"删除资料失败: {exc}")
        return self.planning_state(project_id, kind)

    def new_planning_id(self, item_type: str) -> dict[str, Any]:
        return _ok({"planning_id": default_planning_id(item_type)})

    def export_txt(self, project_id: str) -> dict[str, Any]:
        try:
            import webview
        except ImportError:
            return _fail("当前环境还没有安装 pywebview。")
        if _ACTIVE_WINDOW is None:
            return _fail("窗口尚未就绪。")
        title = next(
            (str(item.get("title") or project_id) for item in self.app.list_projects() if item.get("project_id") == project_id),
            project_id,
        )
        safe_name = re.sub(r'[<>:"/\\|?*]+', "_", title).strip() or project_id
        selected = _ACTIVE_WINDOW.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"{safe_name}.txt",
            file_types=("文本文件 (*.txt)",),
        )
        if not selected:
            return _fail("已取消导出。", cancelled=True)
        path = selected[0] if isinstance(selected, (list, tuple)) else selected
        try:
            result = self.app.export_confirmed_chapters_txt(project_id, path)
        except Exception as exc:
            self._log(f"导出TXT失败: project={project_id} error={exc}")
            return _fail(f"导出失败: {exc}")
        self._log(f"导出TXT: project={project_id} chapters={result.get('chapter_count')} path={result.get('path')}")
        return _ok(_jsonable(result))

    def choose_data_root(self) -> dict[str, Any]:
        try:
            import webview
        except ImportError:
            return _fail("当前环境还没有安装 pywebview。")
        if _ACTIVE_WINDOW is None:
            return _fail("窗口尚未就绪。")
        selected = _ACTIVE_WINDOW.create_file_dialog(webview.FOLDER_DIALOG, directory=str(self.projects_root))
        if not selected:
            return _fail("已取消更改项目库。", cancelled=True)
        path = Path(selected[0] if isinstance(selected, (list, tuple)) else selected)
        try:
            path.mkdir(parents=True, exist_ok=True)
            self.projects_root = path
            self.app = WorkbenchApplicationService.open(path)
        except Exception as exc:
            return _fail(f"切换项目库失败: {exc}")
        return _ok({"projectsRoot": str(path), "workspace": build_workspace_tree(self.app)})

    def open_folder(self, kind: str = "project", project_id: str = "") -> dict[str, Any]:
        if kind == "library":
            target = self.projects_root
        else:
            if not project_id:
                return _fail("请先选择作品。")
            target = self.projects_root / project_id
        if not target.exists():
            return _fail("文件夹不存在。")
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except Exception as exc:
            return _fail(f"打开文件夹失败: {exc}")
        return _ok({"path": str(target)})

    def delete_project(self, project_id: str, confirm_text: str = "") -> dict[str, Any]:
        if str(confirm_text or "").strip() != "确认删除":
            return _fail("未输入“确认删除”，已取消。")
        try:
            result = self.app.delete_project(project_id)
        except Exception as exc:
            return _fail(f"删除作品失败: {exc}")
        return _ok({"result": _jsonable(result), "workspace": build_workspace_tree(self.app)})

    def delete_chapter_drafts(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        try:
            result = self.app.delete_chapter_drafts(project_id, chapter_id)
        except Exception as exc:
            return _fail(f"删除章节草稿失败: {exc}")
        return _ok({"result": _jsonable(result), "workspace": build_workspace_tree(self.app)})

    def delete_confirmed_chapter(self, project_id: str, chapter_id: str, confirm_text: str = "") -> dict[str, Any]:
        if str(confirm_text or "").strip() != "确认删除定稿":
            return _fail("未输入“确认删除定稿”，已取消。")
        try:
            result = self.app.delete_confirmed_chapter(project_id, chapter_id)
        except Exception as exc:
            return _fail(f"删除已确认章节失败: {exc}")
        return _ok({"result": _jsonable(result), "workspace": build_workspace_tree(self.app)})

    def local_review(self, project_id: str, draft_id: str) -> dict[str, Any]:
        try:
            existing = self.app.find_review_for_draft(project_id, draft_id)
            if existing is not None:
                return _ok({"existing": True, "review": self._review_payload(project_id, existing)})
            result = self.app.review_draft(project_id, draft_id)
            review = self.app.read_review(project_id, str(result.get("review_id") or ""))
        except Exception as exc:
            if "already has a review" in str(exc):
                existing = self.app.find_review_for_draft(project_id, draft_id)
                if existing is not None:
                    return _ok({"existing": True, "review": self._review_payload(project_id, existing)})
            return _fail(f"本地初审失败: {exc}")
        return _ok({"existing": False, "review": self._review_payload(project_id, review)})

    def generation_settings_state(self, scope: str = "global", project_id: str = "") -> dict[str, Any]:
        try:
            if scope == "project":
                if not project_id:
                    return _fail("请先选择作品。")
                state = self.app.project_generation_settings_state(project_id)
                return _ok(_jsonable({**state, "scope": "project"}))
            return _ok(
                {
                    "scope": "global",
                    "source": "global",
                    "has_project_override": False,
                    "settings": _jsonable(self.app.global_generation_settings()),
                    "global_settings_path": str(self.app._global_settings_path()),
                }
            )
        except Exception as exc:
            return _fail(f"读取创作设置失败: {exc}")

    def save_generation_settings(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        try:
            settings = _normalize_generation_payload(data.get("settings") if isinstance(data.get("settings"), dict) else {})
            if str(data.get("scope") or "") == "project":
                updated = self.app.update_generation_settings(str(data.get("project_id") or ""), settings)
            else:
                updated = self.app.update_global_generation_settings(settings)
        except Exception as exc:
            return _fail(f"保存创作设置失败: {exc}")
        return _ok(_jsonable(updated))

    def reset_generation_settings(self, scope: str = "global", project_id: str = "") -> dict[str, Any]:
        try:
            if scope == "project":
                updated = self.app.clear_project_generation_settings(project_id)
            else:
                updated = self.app.reset_global_generation_settings()
        except Exception as exc:
            return _fail(f"恢复创作设置失败: {exc}")
        return _ok(_jsonable(updated))

    def preview_prompt(self, project_id: str, chapter_id: str, prompt: str) -> dict[str, Any]:
        user_prompt = str(prompt or "").strip()
        if not user_prompt:
            return _fail("提示词不能为空。")
        try:
            settings = self.app.generation_settings(project_id)
            prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
            context = settings.get("context") if isinstance(settings.get("context"), dict) else {}
            render = self.app.prompt_render_dry_run(
                project_id,
                chapter_id=str(chapter_id or "").strip(),
                prompt=user_prompt,
                system_prompt=str(prompting.get("system_prompt") or ""),
                max_context_tokens=optional_int(context.get("max_context_tokens")),
                include_prompt_text=True,
                include_context_text=False,
            )
        except Exception as exc:
            return _fail(f"预览失败: {exc}")
        return _ok({"details": format_prompt_preview(render)})

    def memory_auto_candidate(self, project_id: str) -> dict[str, Any]:
        try:
            candidate = self.app.memory_auto_summary_candidate(project_id)
        except Exception as exc:
            return _fail(f"自动记忆总结检查失败: {exc}")
        chapter_ids = [str(item or "") for item in (candidate.get("source_chapter_ids") or []) if str(item or "")]
        payload = _jsonable(candidate)
        payload["confirm_text"] = format_auto_memory_summary_confirmation(chapter_ids) if candidate.get("ready") else ""
        return _ok(payload)

    def empty_trash(self) -> dict[str, Any]:
        try:
            result = self.app.clear_trash()
        except Exception as exc:
            return _fail(f"清空回收站失败: {exc}")
        return _ok(_jsonable(result))

    def project_health_detail(self, project_id: str) -> dict[str, Any]:
        try:
            health = self.app.project_health(project_id, repo_root=self.repo_root)
        except Exception as exc:
            return _fail(f"作品概览读取失败: {exc}")
        return _ok(
            {
                "summary": format_project_summary(health),
                "providers": format_provider_summary(health),
            }
        )

    def about(self) -> dict[str, Any]:
        return _ok(
            {
                "title": APP_TITLE,
                "text": (
                    "本地优先的小说创作工作台。\n\n"
                    "草稿必须由你显式确认，才会成为正文。\n"
                    "保存设置、打开作品、编辑正文不会自动联网。\n"
                    "只有生成、审稿、精修、刷新模型和记忆生成会在你点击后调用模型。\n\n"
                    "数据保存在本机项目库。删除作品或章节会先进入回收站。"
                ),
            }
        )

    def context_preview(self, project_id: str) -> dict[str, Any]:
        try:
            preview = self.app.context_package_preview(project_id, include_text=True)
        except Exception as exc:
            return _fail(f"生成上下文预览失败: {exc}")
        return _ok({"details": format_context_package_preview(preview), "preview": _jsonable(preview)})

    def _review_payload(self, project_id: str, review: dict[str, Any]) -> dict[str, Any]:
        return {
            "review_id": str(review.get("review_id") or ""),
            "chapter_id": str(review.get("chapter_id") or ""),
            "draft_id": str(review.get("draft_id") or ""),
            "review_type": str(review.get("review_type") or ""),
            "recommendation": str(review.get("recommendation") or ""),
            "comment": str(review.get("comment") or ""),
            "truncated": review_output_truncated(review),
            "truncated_notice": REVIEW_TRUNCATED_NOTICE,
            "details": format_review_details(project_id, review),
        }


def main() -> int:
    try:
        import webview
    except ImportError:
        print("未安装 pywebview，已回退到经典 Tk 界面。")
        print("安装现代界面: .venv\\Scripts\\python.exe -m pip install pywebview")
        from .desktop_app import main as classic_main

        return classic_main()

    ui_dir = modern_ui_dir()
    index = ui_dir / "index.html"
    if not index.exists():
        print(f"找不到现代界面文件: {index}")
        from .desktop_app import main as classic_main

        return classic_main()

    projects_root = default_projects_root()
    projects_root.mkdir(parents=True, exist_ok=True)
    api = WorkbenchBridge(projects_root=projects_root, repo_root=default_repo_root())
    window = webview.create_window(
        APP_TITLE,
        url=str(index.resolve()),
        js_api=api,
        width=1440,
        height=900,
        min_size=(1120, 720),
        maximized=True,
        background_color="#EEF1F8",
        text_select=True,
        confirm_close=False,
    )
    api.bind_window(window)
    webview.start(debug=False, gui="edgechromium")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
