"""Classic Memory Bank window and its window-local presentation helpers."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from .memory_bank import DEFAULT_MEMORY_TARGET_TOKENS, normalize_memory_target_tokens
from .memory_bank_ui_state import (
    checked_memory_chapter_ids,
    checked_memory_chapters_label,
    memory_chapter_row_label,
    memory_editor_snapshot,
)
from .ui_presenters import (
    estimate_memory_text_tokens,
    format_context_package_preview,
    format_memory_generation_manual_prompt,
    format_memory_generation_request_preview,
    memory_progress_label,
    memory_token_advice,
    recommended_memory_chapter_ids,
)

if TYPE_CHECKING:
    # Runtime imports must remain one-way: desktop_app imports this module, never the reverse.
    from .desktop_app import WorkbenchDesktopApp


def wrapped_row_positions(
    item_widths: list[int],
    available_width: int,
    *,
    horizontal_gap: int = 8,
) -> list[tuple[int, int]]:
    """Return row/column positions that keep each item inside the available width."""
    positions: list[tuple[int, int]] = []
    row = 0
    column = 0
    used_width = 0
    usable_width = max(1, int(available_width))
    gap = max(0, int(horizontal_gap))

    for requested_width in item_widths:
        item_width = max(1, int(requested_width))
        next_width = item_width if column == 0 else used_width + gap + item_width
        if column > 0 and next_width > usable_width:
            row += 1
            column = 0
            used_width = item_width
        else:
            used_width = next_width
        positions.append((row, column))
        column += 1
    return positions


# Compression wording stays window-owned because it is a user preview,
# not the provider request contract.
def format_memory_compression_prompt(
    *,
    current_memory: str,
    current_tokens: int | None = None,
    target_tokens: int = DEFAULT_MEMORY_TARGET_TOKENS,
) -> str:
    existing_memory = str(current_memory or "").strip()
    safe_target_tokens = normalize_memory_target_tokens(target_tokens)
    estimated_tokens = (
        max(int(current_tokens), 0)
        if isinstance(current_tokens, int) and not isinstance(current_tokens, bool)
        else estimate_memory_text_tokens(existing_memory)
    )
    token_note = memory_token_advice(estimated_tokens, safe_target_tokens)
    lines = [
        "你是长篇小说项目的记忆银行压缩助手。",
        "请只基于“当前记忆银行正文”进行缩写，不新增设定，不调用外部资料，不改变已确认事实。",
        "",
        "长度信息：",
        f"- 当前估算：约 {estimated_tokens} tokens。",
        f"- 目标长度：约 {safe_target_tokens} tokens。",
        f"- 判断：{token_note}",
        "",
        "缩写要求：",
        "1. 输出应能直接替换原“记忆银行正文”，不要写解释、评论、标题外说明或 <think>。",
        "2. 保留近期关键因果、人物当前状态、人物关系/动机变化、世界规则限制、未解决伏笔、后续章节必须遵守的事实。",
        "3. 优先压缩最早、已解决、低影响、重复表达或只剩背景价值的旧记忆。",
        "4. 可以合并同类项、改写为更短句、删除重复提醒，但不要硬删近期关键事实来凑数字。",
        "5. 目标 tokens 是缩写方向，不是硬性截断；如果保留关键连续性需要，可以略超目标。",
        "",
        "【当前记忆银行正文】",
        existing_memory or "（当前记忆银行为空。）",
    ]
    return "\n".join(lines).strip()


# Keep related Tk callbacks together; splitting individual closures would
# obscure their shared window state.
def open_memory_bank_window(
    self: WorkbenchDesktopApp,
    project_id: str,
    *,
    app_title: str,
) -> None:
    """Open the classic editor while the desktop host owns application-wide services."""
    # Keep the established dialog caption without importing desktop_app at runtime.
    APP_TITLE = app_title
    window = self._secondary_window("记忆银行", geometry="1160x740", minsize=(920, 620))
    window.columnconfigure(1, weight=1)
    window.rowconfigure(3, weight=1)

    ttk.Label(
        window,
        text="当前项目专属的长期记忆。勾选本次要合并进记忆银行的已确认章节，系统会把旧记忆和这些章节一起放进更新提示词；右侧正文可直接编辑保存。",
        foreground="#6b7280",
        wraplength=1020,
    ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 8))
    progress_var = tk.StringVar(value="")
    ttk.Label(window, textvariable=progress_var, foreground="#111827").grid(
        row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 4)
    )
    summary_var = tk.StringVar(value="")
    ttk.Label(window, textvariable=summary_var, foreground="#374151").grid(
        row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8)
    )

    list_frame = ttk.Frame(window)
    list_frame.grid(row=3, column=0, sticky="nsew", padx=(14, 8), pady=8)
    list_frame.rowconfigure(2, weight=1)
    list_frame.columnconfigure(0, weight=1)
    ttk.Label(list_frame, text="勾选要发送去更新记忆的章节").grid(row=0, column=0, sticky="w", pady=(0, 6))
    select_buttons = ttk.Frame(list_frame)
    select_buttons.grid(row=1, column=0, sticky="ew", pady=(0, 6))
    chapter_tree_frame = ttk.Frame(list_frame)
    chapter_tree_frame.grid(row=2, column=0, sticky="nsew")
    chapter_tree_frame.rowconfigure(0, weight=1)
    chapter_tree_frame.columnconfigure(0, weight=1)
    chapter_tree = ttk.Treeview(chapter_tree_frame, show="tree", selectmode="none", height=20)
    chapter_tree.grid(row=0, column=0, sticky="nsew")
    chapter_scrollbar = ttk.Scrollbar(chapter_tree_frame, orient="vertical", command=chapter_tree.yview)
    chapter_scrollbar.grid(row=0, column=1, sticky="ns")
    chapter_tree.configure(yscrollcommand=chapter_scrollbar.set)

    editor = ttk.Frame(window)
    editor.grid(row=3, column=1, sticky="nsew", padx=(8, 14), pady=8)
    editor.columnconfigure(1, weight=1)
    editor.rowconfigure(7, weight=1)

    selected_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="")
    token_target_var = tk.StringVar(value=str(DEFAULT_MEMORY_TARGET_TOKENS))
    token_estimate_var = tk.StringVar(value="")
    include_context_var = tk.BooleanVar(value=True)
    api_status_var = tk.StringVar(value="")
    current_memory_item: dict[str, Any] = {}
    confirmed_chapters: list[dict[str, Any]] = []
    checked_chapter_ids: set[str] = set()
    api_generating = {"active": False}

    ttk.Label(editor, text="本次勾选").grid(row=0, column=0, sticky="e", padx=(0, 10), pady=(0, 8))
    ttk.Entry(editor, textvariable=selected_var, state="readonly").grid(row=0, column=1, sticky="ew", pady=(0, 8))
    ttk.Label(editor, text="记忆状态").grid(row=1, column=0, sticky="e", padx=(0, 10), pady=8)
    ttk.Entry(editor, textvariable=status_var, state="readonly").grid(row=1, column=1, sticky="ew", pady=8)
    ttk.Label(editor, text="记忆目标 tokens").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=8)
    token_entry = ttk.Entry(editor, textvariable=token_target_var, width=12)
    token_entry.grid(row=2, column=1, sticky="w", pady=8)
    ttk.Label(editor, text="当前估算 tokens").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=8)
    ttk.Entry(editor, textvariable=token_estimate_var, state="readonly").grid(row=3, column=1, sticky="ew", pady=8)
    ttk.Label(
        editor,
        text="默认 5000，建议 3000-8000；只写进更新提示词，不限制 API 输出或保存正文。",
        foreground="#6b7280",
        wraplength=680,
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Checkbutton(
        editor,
        text="把记忆银行加入生成上下文",
        variable=include_context_var,
        command=lambda: update_status(),
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Label(editor, text="记忆银行正文").grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 4))
    text_frame = ttk.Frame(editor)
    text_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)
    text_box = tk.Text(text_frame, wrap="word", height=22, undo=True)
    self._style_text_widget(text_box)
    text_box.grid(row=0, column=0, sticky="nsew")
    text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_box.yview)
    text_scrollbar.grid(row=0, column=1, sticky="ns")
    text_box.configure(yscrollcommand=text_scrollbar.set)
    ttk.Label(editor, textvariable=api_status_var, foreground="#6b7280", wraplength=680).grid(
        row=8, column=0, columnspan=2, sticky="ew"
    )
    saved_snapshot: dict[str, Any] = {}
    suppress_dirty_tracking = {"active": False}

    def update_window_title() -> None:
        marker = "*" if has_unsaved_changes() else ""
        window.title(f"记忆银行{marker}")

    def chapter_label(chapter: dict[str, Any]) -> str:
        return memory_chapter_row_label(chapter, checked_chapter_ids)

    def checked_ids_in_order() -> list[str]:
        return checked_memory_chapter_ids(confirmed_chapters, checked_chapter_ids)

    def checked_label() -> str:
        return checked_memory_chapters_label(checked_ids_in_order())

    def current_target_tokens(*, normalize_entry: bool = False) -> int:
        target_tokens = normalize_memory_target_tokens(token_target_var.get())
        if normalize_entry:
            token_target_var.set(str(target_tokens))
        return target_tokens

    def editor_snapshot() -> dict[str, Any]:
        return memory_editor_snapshot(
            text=text_box.get("1.0", tk.END),
            include_context=include_context_var.get(),
            target_tokens=current_target_tokens(),
            chapter_ids=checked_ids_in_order(),
        )

    def has_unsaved_changes() -> bool:
        return bool(saved_snapshot) and editor_snapshot() != saved_snapshot

    def remember_saved_snapshot() -> None:
        saved_snapshot.clear()
        saved_snapshot.update(editor_snapshot())
        update_window_title()

    def refresh_dirty_state() -> None:
        if not suppress_dirty_tracking["active"]:
            update_window_title()

    def recommended_chapter_ids() -> list[str]:
        return recommended_memory_chapter_ids(current_memory_item, confirmed_chapters)

    def progress_label() -> str:
        return memory_progress_label(current_memory_item, confirmed_chapters)

    def update_status() -> None:
        text = text_box.get("1.0", tk.END).strip()
        text_state = "已有记忆" if text else "暂无记忆"
        context_state = "会进入生成上下文" if include_context_var.get() else "不会进入生成上下文"
        selected_count = len(checked_chapter_ids)
        target_tokens = current_target_tokens()
        estimated_tokens = estimate_memory_text_tokens(text)
        token_estimate_var.set(memory_token_advice(estimated_tokens, target_tokens))
        progress_var.set(progress_label())
        summary_var.set(
            f"项目记忆：{text_state}，{len(text)} 字，约 {estimated_tokens} tokens；本次勾选 {selected_count} 章；目标约 {target_tokens} tokens；{context_state}。"
        )
        status_var.set(
            f"{text_state}；{len(text)} 字；约 {estimated_tokens} tokens；本次勾选 {selected_count} 章；目标约 {target_tokens} tokens；{context_state}"
        )
        selected_var.set(checked_label())
        refresh_dirty_state()

    def refresh_chapter_rows() -> None:
        for chapter in confirmed_chapters:
            chapter_id = str(chapter.get("chapter_id") or "")
            row_id = f"chapter:{chapter_id}"
            if chapter_id and chapter_tree.exists(row_id):
                chapter_tree.item(row_id, text=chapter_label(chapter))
        update_status()

    def set_checked_chapters(chapter_ids: list[str]) -> None:
        checked_chapter_ids.clear()
        checked_chapter_ids.update(chapter_id for chapter_id in chapter_ids if chapter_id)
        refresh_chapter_rows()

    def check_recommended_chapters() -> None:
        set_checked_chapters(recommended_chapter_ids())

    def check_all_chapters() -> None:
        set_checked_chapters([str(chapter.get("chapter_id") or "") for chapter in confirmed_chapters])

    def clear_checked_chapters() -> None:
        set_checked_chapters([])

    def refresh_chapters(select_id: str = "") -> None:
        previous_checked = set(checked_chapter_ids)
        for child in chapter_tree.get_children(""):
            chapter_tree.delete(child)
        confirmed_chapters[:] = self.app.list_confirmed_chapters(project_id)
        if previous_checked:
            checked_chapter_ids.clear()
            checked_chapter_ids.update(
                chapter_id
                for chapter_id in previous_checked
                if any(str(chapter.get("chapter_id") or "") == chapter_id for chapter in confirmed_chapters)
            )
        else:
            checked_chapter_ids.update(recommended_chapter_ids())
        for chapter in confirmed_chapters:
            chapter_id = str(chapter.get("chapter_id") or "")
            if chapter_id:
                chapter_tree.insert("", "end", iid=f"chapter:{chapter_id}", text=chapter_label(chapter))
        update_status()

    def refresh(select_chapter_id: str = "") -> None:
        suppress_dirty_tracking["active"] = True
        try:
            item = self.app.ensure_main_memory_item(project_id)
        except Exception as exc:
            suppress_dirty_tracking["active"] = False
            messagebox.showerror(APP_TITLE, f"读取记忆银行失败:\n{exc}", parent=window)
            return
        try:
            current_memory_item.clear()
            current_memory_item.update(item)
            include_context_var.set(item.get("enabled") is not False)
            token_target_var.set(str(normalize_memory_target_tokens(item.get("target_token_budget"))))
            text_box.delete("1.0", tk.END)
            text_box.insert("1.0", str(item.get("text") or ""))
            refresh_chapters(select_chapter_id)
            remember_saved_snapshot()
        finally:
            suppress_dirty_tracking["active"] = False
            update_window_title()

    def on_chapter_click(event: tk.Event) -> str | None:
        row_id = chapter_tree.identify_row(event.y)
        if not row_id:
            return None
        chapter_id = str(row_id).removeprefix("chapter:")
        if chapter_id in checked_chapter_ids:
            checked_chapter_ids.remove(chapter_id)
        else:
            checked_chapter_ids.add(chapter_id)
        refresh_chapter_rows()
        return "break"

    def current_memory_id() -> str:
        memory_id = str(current_memory_item.get("memory_id") or "").strip()
        if memory_id:
            return memory_id
        item = self.app.ensure_main_memory_item(project_id)
        current_memory_item.clear()
        current_memory_item.update(item)
        return str(item.get("memory_id") or "").strip()

    def selected_confirmed_chapters() -> list[dict[str, Any]]:
        chapter_ids = checked_ids_in_order()
        if not chapter_ids:
            raise RuntimeError("请先在左侧勾选本次要发送去更新记忆的已确认章节。")
        return [self.app.read_confirmed_chapter(project_id, chapter_id) for chapter_id in chapter_ids]

    def current_memory_generation_preview() -> dict[str, Any]:
        return self.app.preview_memory_generation_request(
            project_id,
            current_memory=text_box.get("1.0", tk.END).strip(),
            chapters=selected_confirmed_chapters(),
            target_token_budget=current_target_tokens(normalize_entry=True),
        )

    def confirm_discard_unsaved(action: str) -> bool:
        if not has_unsaved_changes():
            return True
        return messagebox.askyesno(
            APP_TITLE,
            f"记忆银行有未保存修改，{action}会丢失当前窗口里的改动。\n\n继续？",
            parent=window,
        )

    def save_text() -> None:
        memory_id = current_memory_id()
        text = text_box.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo(APP_TITLE, "记忆银行正文不能为空。可以先写一版简短总结再保存。", parent=window)
            return
        target_tokens = current_target_tokens(normalize_entry=True)
        try:
            result = self.app.set_memory_text(
                project_id,
                memory_id,
                text,
                source_chapter_ids=checked_ids_in_order(),
                target_token_budget=target_tokens,
            )
            self.app.set_memory_item_enabled(
                project_id,
                memory_id,
                enabled=include_context_var.get(),
                reason_code="desktop_toggle",
                target_token_budget=target_tokens,
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"保存记忆正文失败:\n{exc}", parent=window)
            return
        self.write_log(f"记忆银行正文已保存: project={project_id} memory_id={result.get('memory_id')}")
        checked_chapter_ids.clear()
        refresh()
        self.run_project_health(silent=True)

    def save_lifecycle() -> None:
        memory_id = current_memory_id()
        target_tokens = current_target_tokens(normalize_entry=True)
        try:
            result = self.app.set_memory_item_enabled(
                project_id,
                memory_id,
                enabled=include_context_var.get(),
                reason_code="desktop_toggle",
                target_token_budget=target_tokens,
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"保存加入上下文设置失败:\n{exc}", parent=window)
            return
        self.write_log(f"记忆银行引用状态已更新: project={project_id} memory_id={result.get('memory_id')}")
        refresh()
        self.run_project_health(silent=True)

    def show_memory_update_prompt() -> None:
        try:
            preview = current_memory_generation_preview()
        except Exception as exc:
            messagebox.showinfo(APP_TITLE, str(exc), parent=window)
            return
        self.show_text_window(
            "记忆银行更新提示词预览",
            format_memory_generation_manual_prompt(preview),
            parent=window,
            refresh=lambda: format_memory_generation_manual_prompt(current_memory_generation_preview()),
        )

    def set_api_generating(active: bool) -> None:
        api_generating["active"] = active
        state = "disabled" if active else "normal"
        for button in (
            api_generate_button,
            api_preview_button,
            update_prompt_button,
            compression_prompt_button,
            compression_generate_button,
        ):
            button.configure(state=state)
        if active:
            api_status_var.set("正在调用当前 writer 模型服务生成记忆正文；返回前请不要重复点击。")

    def show_memory_api_request_preview() -> None:
        try:
            preview = current_memory_generation_preview()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"生成 API 发送结构失败:\n{exc}", parent=window)
            return
        self.show_text_window(
            "记忆银行 API 发送结构",
            format_memory_generation_request_preview(preview),
            parent=window,
            refresh=lambda: format_memory_generation_request_preview(current_memory_generation_preview()),
        )

    def generate_memory_via_api() -> None:
        if api_generating["active"]:
            return
        try:
            chapters = selected_confirmed_chapters()
            target_tokens = current_target_tokens(normalize_entry=True)
        except Exception as exc:
            messagebox.showinfo(APP_TITLE, str(exc), parent=window)
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "将调用当前 writer 模型服务，把旧记忆和勾选章节发送给 API 生成记忆正文，可能消耗额度。\n\n继续？",
            parent=window,
        ):
            return
        current_memory = text_box.get("1.0", tk.END).strip()
        progress = self._secondary_window(
            "记忆银行生成进度",
            owner=window,
            geometry="860x620",
            minsize=(640, 480),
        )
        progress.columnconfigure(0, weight=1)
        progress.rowconfigure(3, weight=1)
        is_generating = {"active": True}
        ttk.Label(
            progress,
            text=f"正在根据当前记忆银行和本次勾选的 {len(chapters)} 章生成记忆正文。流式返回会显示在下方。",
            wraplength=820,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        progress_status_var = tk.StringVar(value="正在调用当前 writer 模型服务生成记忆正文...")
        ttk.Label(progress, textvariable=progress_status_var, foreground="#6b7280", wraplength=820).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 12),
        )
        progress_bar = ttk.Progressbar(progress, mode="indeterminate")
        progress_bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        progress_bar.start(12)
        live_frame = ttk.Frame(progress)
        live_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        live_frame.rowconfigure(0, weight=1)
        live_frame.columnconfigure(0, weight=1)
        live_text_box = tk.Text(live_frame, wrap="word", undo=True)
        live_text_box.grid(row=0, column=0, sticky="nsew")
        live_text_box.configure(state="disabled")
        live_scrollbar = ttk.Scrollbar(live_frame, orient="vertical", command=live_text_box.yview)
        live_scrollbar.grid(row=0, column=1, sticky="ns")
        live_text_box.configure(yscrollcommand=live_scrollbar.set)
        progress_button_row = ttk.Frame(progress)
        progress_button_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))

        def live_text_content() -> str:
            return live_text_box.get("1.0", tk.END).strip()

        def append_stream_chunk(chunk: str) -> None:
            if not chunk:
                return
            live_text_box.configure(state="normal")
            live_text_box.insert(tk.END, chunk)
            live_text_box.see(tk.END)
            live_text_box.configure(state="disabled")

        def set_live_text(text: str, *, editable: bool) -> None:
            live_text_box.configure(state="normal")
            live_text_box.delete("1.0", tk.END)
            live_text_box.insert("1.0", text)
            live_text_box.see(tk.END)
            live_text_box.configure(state="normal" if editable else "disabled")

        def close_progress_window() -> None:
            if is_generating["active"]:
                messagebox.showinfo(APP_TITLE, "记忆正文正在生成，请等待完成。", parent=progress)
                return
            progress.destroy()

        close_progress_button = ttk.Button(
            progress_button_row,
            text="关闭",
            command=close_progress_window,
            state="disabled",
        )
        close_progress_button.pack(side="right")
        progress.protocol("WM_DELETE_WINDOW", close_progress_window)

        def stream_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: append_stream_chunk(chunk))

        set_api_generating(True)
        self.write_log(f"记忆银行 API 生成请求已发送: project={project_id} chapters={len(chapters)}")

        def worker() -> None:
            try:
                result = self.app.generate_memory_bank_text(
                    project_id,
                    current_memory=current_memory,
                    chapters=chapters,
                    target_token_budget=target_tokens,
                    stream_callback=stream_callback,
                )
            except Exception as exc:
                self.after(0, lambda exc=exc: finish(error=exc))
                return
            self.after(0, lambda result=result: finish(result=result))

        def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
            is_generating["active"] = False
            try:
                progress_bar.stop()
            except tk.TclError:
                pass
            set_api_generating(False)
            if error is not None:
                api_status_var.set("AI 生成记忆失败。")
                progress_status_var.set("AI 生成记忆失败。")
                progress.title("记忆银行生成失败")
                close_progress_button.configure(state="normal")
                messagebox.showerror(APP_TITLE, f"AI 生成记忆失败:\n{error}", parent=window)
                self.write_log(f"记忆银行 API 生成失败: {error}")
                return
            result = result or {}
            generated_text = str(result.get("text") or "").strip()
            if generated_text and live_text_content() != generated_text:
                set_live_text(generated_text, editable=True)
            else:
                live_text_box.configure(state="normal")
            text_box.delete("1.0", tk.END)
            text_box.insert("1.0", generated_text)
            summary = result.get("request_summary") if isinstance(result.get("request_summary"), dict) else {}
            api_status_var.set(
                "AI 已生成记忆正文，已填入右侧文本框；请检查后点击“保存记忆正文”。"
                f" provider={result.get('provider') or '-'} model={result.get('model') or '-'}"
                f" chars={len(generated_text)} prompt_chars={summary.get('prompt_chars') or '-'}"
            )
            progress_status_var.set(
                "AI 已生成记忆正文，已同步填入记忆银行窗口；请检查后点击“保存记忆正文”。"
                f" provider={result.get('provider') or '-'} model={result.get('model') or '-'}"
                f" chars={len(generated_text)} prompt_chars={summary.get('prompt_chars') or '-'}"
            )
            progress.title("记忆银行生成结果")
            close_progress_button.configure(state="normal")
            self.write_log(
                f"记忆银行 API 生成成功: project={project_id} provider={result.get('provider')} "
                f"model={result.get('model')} chars={len(generated_text)}"
            )
            update_status()

        threading.Thread(target=worker, name="NovelMemoryBankGeneration", daemon=True).start()

    def show_memory_compression_prompt() -> None:
        current_memory = text_box.get("1.0", tk.END).strip()
        if not current_memory:
            messagebox.showinfo(APP_TITLE, "当前记忆银行正文为空，暂时不需要缩写。", parent=window)
            return
        target_tokens = current_target_tokens(normalize_entry=True)
        prompt = format_memory_compression_prompt(
            current_memory=current_memory,
            current_tokens=estimate_memory_text_tokens(current_memory),
            target_tokens=target_tokens,
        )
        self.show_text_window(
            "记忆银行缩写提示词预览",
            prompt,
            parent=window,
            refresh=lambda: format_memory_compression_prompt(
                current_memory=text_box.get("1.0", tk.END).strip(),
                current_tokens=estimate_memory_text_tokens(text_box.get("1.0", tk.END).strip()),
                target_tokens=current_target_tokens(normalize_entry=True),
            ),
        )

    def generate_compression_via_api() -> None:
        if api_generating["active"]:
            return
        current_memory = text_box.get("1.0", tk.END).strip()
        if not current_memory:
            messagebox.showinfo(APP_TITLE, "当前记忆银行正文为空，暂时不需要缩写。", parent=window)
            return
        target_tokens = current_target_tokens(normalize_entry=True)
        if not messagebox.askyesno(
            APP_TITLE,
            "将调用当前 writer 模型服务，只发送当前记忆银行正文，用于生成缩写后的记忆正文，可能消耗额度。\n\n"
            "生成结果会先回填到右侧文本框，不会自动保存。\n\n继续？",
            parent=window,
        ):
            return
        progress = self._secondary_window(
            "记忆银行缩写进度",
            owner=window,
            geometry="860x620",
            minsize=(640, 480),
        )
        progress.columnconfigure(0, weight=1)
        progress.rowconfigure(3, weight=1)
        is_generating = {"active": True}
        ttk.Label(
            progress,
            text=f"正在把当前记忆银行缩写到约 {target_tokens} tokens。流式返回会显示在下方。",
            wraplength=820,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        progress_status_var = tk.StringVar(value="正在调用当前 writer 模型服务缩写记忆正文...")
        ttk.Label(progress, textvariable=progress_status_var, foreground="#6b7280", wraplength=820).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 12),
        )
        progress_bar = ttk.Progressbar(progress, mode="indeterminate")
        progress_bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        progress_bar.start(12)
        live_frame = ttk.Frame(progress)
        live_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        live_frame.rowconfigure(0, weight=1)
        live_frame.columnconfigure(0, weight=1)
        live_text_box = tk.Text(live_frame, wrap="word", undo=True)
        live_text_box.grid(row=0, column=0, sticky="nsew")
        live_text_box.configure(state="disabled")
        live_scrollbar = ttk.Scrollbar(live_frame, orient="vertical", command=live_text_box.yview)
        live_scrollbar.grid(row=0, column=1, sticky="ns")
        live_text_box.configure(yscrollcommand=live_scrollbar.set)
        progress_button_row = ttk.Frame(progress)
        progress_button_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))

        def live_text_content() -> str:
            return live_text_box.get("1.0", tk.END).strip()

        def append_stream_chunk(chunk: str) -> None:
            if not chunk:
                return
            live_text_box.configure(state="normal")
            live_text_box.insert(tk.END, chunk)
            live_text_box.see(tk.END)
            live_text_box.configure(state="disabled")

        def set_live_text(text: str, *, editable: bool) -> None:
            live_text_box.configure(state="normal")
            live_text_box.delete("1.0", tk.END)
            live_text_box.insert("1.0", text)
            live_text_box.see(tk.END)
            live_text_box.configure(state="normal" if editable else "disabled")

        def close_progress_window() -> None:
            if is_generating["active"]:
                messagebox.showinfo(APP_TITLE, "记忆正文正在缩写，请等待完成。", parent=progress)
                return
            progress.destroy()

        close_progress_button = ttk.Button(
            progress_button_row,
            text="关闭",
            command=close_progress_window,
            state="disabled",
        )
        close_progress_button.pack(side="right")
        progress.protocol("WM_DELETE_WINDOW", close_progress_window)

        def stream_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: append_stream_chunk(chunk))

        set_api_generating(True)
        self.write_log(f"记忆银行缩写 API 请求已发送: project={project_id}")

        def worker() -> None:
            try:
                result = self.app.generate_memory_bank_compression_text(
                    project_id,
                    current_memory=current_memory,
                    target_token_budget=target_tokens,
                    stream_callback=stream_callback,
                )
            except Exception as exc:
                self.after(0, lambda exc=exc: finish(error=exc))
                return
            self.after(0, lambda result=result: finish(result=result))

        def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
            is_generating["active"] = False
            try:
                progress_bar.stop()
            except tk.TclError:
                pass
            set_api_generating(False)
            if error is not None:
                api_status_var.set("AI 缩写记忆失败。")
                progress_status_var.set("AI 缩写记忆失败。")
                progress.title("记忆银行缩写失败")
                close_progress_button.configure(state="normal")
                messagebox.showerror(APP_TITLE, f"AI 缩写记忆失败:\n{error}", parent=window)
                self.write_log(f"记忆银行缩写 API 失败: {error}")
                return
            result = result or {}
            generated_text = str(result.get("text") or "").strip()
            if generated_text and live_text_content() != generated_text:
                set_live_text(generated_text, editable=True)
            else:
                live_text_box.configure(state="normal")
            text_box.delete("1.0", tk.END)
            text_box.insert("1.0", generated_text)
            summary = result.get("request_summary") if isinstance(result.get("request_summary"), dict) else {}
            api_status_var.set(
                "AI 已缩写记忆正文，已填入右侧文本框；请检查后点击“保存记忆正文”。"
                f" provider={result.get('provider') or '-'} model={result.get('model') or '-'}"
                f" chars={len(generated_text)} prompt_chars={summary.get('prompt_chars') or '-'}"
            )
            progress_status_var.set(
                "AI 已缩写记忆正文，已同步填入记忆银行窗口；请检查后点击“保存记忆正文”。"
                f" provider={result.get('provider') or '-'} model={result.get('model') or '-'}"
                f" chars={len(generated_text)} prompt_chars={summary.get('prompt_chars') or '-'}"
            )
            progress.title("记忆银行缩写结果")
            close_progress_button.configure(state="normal")
            self.write_log(
                f"记忆银行缩写 API 成功: project={project_id} provider={result.get('provider')} "
                f"model={result.get('model')} chars={len(generated_text)}"
            )
            update_status()

        threading.Thread(target=worker, name="NovelMemoryBankCompression", daemon=True).start()

    def show_context_preview() -> None:
        try:
            preview = self.app.context_package_preview(project_id, include_text=True)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"生成上下文预览失败:\n{exc}", parent=window)
            return
        self.show_text_window(
            "生成时会携带的上下文",
            format_context_package_preview(preview),
            parent=window,
            refresh=lambda: format_context_package_preview(
                self.app.context_package_preview(project_id, include_text=True)
            ),
        )

    chapter_tree.bind("<Button-1>", on_chapter_click)
    text_box.bind("<KeyRelease>", lambda _event: update_status())
    token_entry.bind("<KeyRelease>", lambda _event: update_status())
    window.bind("<Control-s>", lambda _event: (save_text(), "break")[1])
    window.bind("<Control-S>", lambda _event: (save_text(), "break")[1])

    ttk.Button(select_buttons, text="勾选建议章节", command=check_recommended_chapters).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(select_buttons, text="全选", command=check_all_chapters).pack(side="left", padx=(0, 6))
    ttk.Button(select_buttons, text="清空", command=clear_checked_chapters).pack(side="left")

    button_row = ttk.Frame(window, style="DialogFooter.TFrame")
    button_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))
    update_prompt_button = ttk.Button(button_row, text="生成更新记忆提示词", command=show_memory_update_prompt)
    api_preview_button = ttk.Button(button_row, text="查看API发送结构", command=show_memory_api_request_preview)
    api_generate_button = ttk.Button(
        button_row,
        text="发送给AI生成记忆",
        command=generate_memory_via_api,
        style="Primary.TButton",
    )
    compression_prompt_button = ttk.Button(button_row, text="生成缩写提示词", command=show_memory_compression_prompt)
    compression_generate_button = ttk.Button(button_row, text="发送给AI缩写记忆", command=generate_compression_via_api)
    context_preview_button = ttk.Button(button_row, text="查看生成时会带的上下文", command=show_context_preview)
    refresh_button = ttk.Button(
        button_row,
        text="刷新窗口",
        command=lambda: refresh() if confirm_discard_unsaved("刷新窗口") else None,
    )
    lifecycle_button = ttk.Button(button_row, text="保存加入上下文设置", command=save_lifecycle)
    close_button = ttk.Button(
        button_row,
        text="关闭",
        command=lambda: window.destroy() if confirm_discard_unsaved("关闭窗口") else None,
    )
    save_text_button = ttk.Button(button_row, text="保存记忆正文", command=save_text, style="Confirm.TButton")
    action_buttons = [
        update_prompt_button,
        api_preview_button,
        api_generate_button,
        compression_prompt_button,
        compression_generate_button,
        context_preview_button,
        refresh_button,
        lifecycle_button,
        close_button,
        save_text_button,
    ]
    button_layout_state: dict[str, object] = {"scheduled": False, "positions": None}

    def apply_button_layout() -> None:
        button_layout_state["scheduled"] = False
        try:
            available_width = button_row.winfo_width()
            if available_width <= 1:
                available_width = max(1, window.winfo_width() - 28)
            positions = wrapped_row_positions(
                [button.winfo_reqwidth() for button in action_buttons],
                available_width,
            )
        except tk.TclError:
            return
        if positions == button_layout_state["positions"]:
            return
        button_layout_state["positions"] = positions
        last_column_by_row: dict[int, int] = {}
        last_row = 0
        for row, column in positions:
            last_column_by_row[row] = column
            last_row = max(last_row, row)
        for button, (row, column) in zip(action_buttons, positions, strict=True):
            button.grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 8 if column < last_column_by_row[row] else 0),
                pady=(0, 8 if row < last_row else 0),
            )

    def schedule_button_layout(_event: tk.Event | None = None) -> None:
        if button_layout_state["scheduled"]:
            return
        button_layout_state["scheduled"] = True
        button_row.after_idle(apply_button_layout)

    button_row.bind("<Configure>", schedule_button_layout, add="+")
    schedule_button_layout()
    window.protocol("WM_DELETE_WINDOW", lambda: window.destroy() if confirm_discard_unsaved("关闭窗口") else None)

    refresh()
