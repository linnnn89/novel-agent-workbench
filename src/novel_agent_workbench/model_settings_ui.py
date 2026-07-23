from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from .model_settings import FEATURE_DEFINITIONS


MASK_PLACEHOLDER = "已保存（留空则保持不变）"
PAGE_PROVIDER = "provider"
PAGE_MODELS = "models"
PAGE_ASSIGNMENTS = "assignments"


def filter_model_labels(labels: list[str], query: str) -> list[str]:
    """Case-insensitive contains search; multiple words must all match."""
    terms = [item.casefold() for item in str(query or "").split() if item.strip()]
    if not terms:
        return list(labels)
    return [label for label in labels if all(term in label.casefold() for term in terms)]


class ModelSettingsDialog:
    def __init__(
        self,
        owner: tk.Misc,
        app: Any,
        *,
        on_saved: Callable[[], None] | None = None,
        write_log: Callable[[str], None] | None = None,
    ) -> None:
        self.owner = owner
        self.app = app
        self.on_saved = on_saved
        self.write_log = write_log or (lambda _text: None)
        self.window = tk.Toplevel(owner)
        self.window.title("模型设置")
        self.window.geometry("1120x760")
        self.window.minsize(900, 640)
        self.window.resizable(True, True)
        self.window.transient(owner)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.page = PAGE_PROVIDER
        self.state: dict[str, Any] = {}
        self.provider_by_id: dict[str, dict[str, Any]] = {}
        self.model_by_ref: dict[str, dict[str, Any]] = {}
        self.model_label_to_ref: dict[str, str] = {}
        self.all_model_labels: list[str] = []
        self.assignment_vars: dict[str, tuple[tk.StringVar, tk.StringVar, ttk.Combobox]] = {}
        self.current_provider_id = ""
        self.busy = False
        self._build_shell()
        self.reload_state()
        self.show_page(PAGE_PROVIDER)
        self.window.grab_set()

    def _build_shell(self) -> None:
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=1)

        sidebar = ttk.Frame(self.window, padding=(14, 18))
        sidebar.grid(row=0, column=0, sticky="ns")
        ttk.Label(sidebar, text="模型设置", font=("Microsoft YaHei UI", 14, "bold")).pack(
            anchor="w", pady=(0, 18)
        )
        self.nav_buttons: dict[str, ttk.Button] = {}
        for page_id, label in (
            (PAGE_PROVIDER, "API 提供商"),
            (PAGE_MODELS, "模型目录"),
            (PAGE_ASSIGNMENTS, "功能分配"),
        ):
            button = ttk.Button(sidebar, text=label, width=18, command=lambda value=page_id: self.show_page(value))
            button.pack(fill="x", pady=3)
            self.nav_buttons[page_id] = button
        ttk.Separator(sidebar).pack(fill="x", pady=18)
        ttk.Label(
            sidebar,
            text="接入商保存后不会自动联网。\n只有“刷新模型”会请求对应 API。",
            justify="left",
            wraplength=180,
        ).pack(anchor="w")

        content = ttk.Frame(self.window, padding=(22, 18, 22, 12))
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)
        self.title_var = tk.StringVar()
        self.subtitle_var = tk.StringVar()
        header = ttk.Frame(content)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(header, textvariable=self.title_var, font=("Microsoft YaHei UI", 17, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.subtitle_var, wraplength=760).pack(anchor="w", pady=(5, 0))

        self.page_host = ttk.Frame(content)
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.rowconfigure(0, weight=1)
        self.page_host.columnconfigure(0, weight=1)
        self.provider_page = self._build_provider_page(self.page_host)
        self.models_page = self._build_models_page(self.page_host)
        self.assignments_page = self._build_assignments_page(self.page_host)
        for frame in (self.provider_page, self.models_page, self.assignments_page):
            frame.grid(row=0, column=0, sticky="nsew")

        footer = ttk.Frame(content)
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="设置保存在本机。")
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="关闭", command=self.close).grid(row=0, column=2, padx=(8, 0))
        self.save_button = ttk.Button(footer, text="保存当前设置", command=self.save_current_page)
        self.save_button.grid(row=0, column=1)

    def _build_provider_page(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        left = ttk.Frame(frame, padding=(0, 0, 18, 0))
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="接入商").pack(anchor="w")
        self.provider_tree = ttk.Treeview(left, show="tree", height=20, selectmode="browse")
        self.provider_tree.column("#0", width=210, stretch=False)
        self.provider_tree.pack(fill="y", expand=True, pady=(6, 8))
        self.provider_tree.bind("<<TreeviewSelect>>", self._on_provider_selected)
        ttk.Button(left, text="+ 添加自定义接入商", command=self.new_custom_provider).pack(fill="x")

        form = ttk.Frame(frame)
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(1, weight=1)
        self.provider_name_var = tk.StringVar()
        self.provider_adapter_var = tk.StringVar(value="openai_compatible")
        self.provider_base_url_var = tk.StringVar()
        self.provider_key_var = tk.StringVar()
        self.provider_timeout_var = tk.StringVar(value="300")
        self.provider_key_status_var = tk.StringVar()
        fields = (
            ("名称", self.provider_name_var),
            ("适配器", self.provider_adapter_var),
            ("API 地址", self.provider_base_url_var),
            ("API Key", self.provider_key_var),
            ("等待上限（秒）", self.provider_timeout_var),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="e", padx=(0, 12), pady=8)
            if label == "适配器":
                widget = ttk.Combobox(
                    form,
                    textvariable=variable,
                    values=("openai_compatible", "siliconflow", "chutes_openai", "openrouter"),
                    state="readonly",
                )
            else:
                widget = ttk.Entry(form, textvariable=variable, show="*" if label == "API Key" else "")
            widget.grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Label(form, textvariable=self.provider_key_status_var).grid(
            row=5, column=1, sticky="w", pady=(0, 8)
        )
        actions = ttk.Frame(form)
        actions.grid(row=6, column=1, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="刷新模型", command=self.refresh_selected_provider_models).pack(side="left")
        ttk.Button(actions, text="清除 Key", command=self.clear_selected_provider_key).pack(
            side="left", padx=(8, 0)
        )
        self.delete_provider_button = ttk.Button(actions, text="删除接入商", command=self.delete_selected_provider)
        self.delete_provider_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            form,
            text="自定义接入商按 OpenAI Chat Completions 兼容协议访问；模型目录默认读取 API 地址下的 /models。",
            wraplength=650,
            justify="left",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(22, 0))
        return frame

    def _build_models_page(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.rowconfigure(2, weight=1)
        frame.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(frame)
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Label(toolbar, text="提供商").pack(side="left")
        self.model_provider_var = tk.StringVar()
        self.model_provider_box = ttk.Combobox(toolbar, textvariable=self.model_provider_var, state="readonly", width=24)
        self.model_provider_box.pack(side="left", padx=(8, 18))
        self.model_provider_box.bind("<<ComboboxSelected>>", lambda _event: self.populate_models())
        ttk.Label(toolbar, text="搜索").pack(side="left")
        self.model_search_var = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.model_search_var, width=28)
        search.pack(side="left", padx=(8, 0))
        self.model_search_var.trace_add("write", lambda *_args: self.populate_models())

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, sticky="w", pady=(12, 8))
        ttk.Button(actions, text="刷新模型", command=self.refresh_selected_provider_models).pack(side="left")
        ttk.Button(actions, text="手工添加模型", command=self.add_manual_model).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="启用 / 停用", command=self.toggle_selected_model).pack(side="left", padx=(8, 0))

        columns = ("provider", "model", "source", "enabled")
        self.model_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        self.model_tree.heading("provider", text="提供商")
        self.model_tree.heading("model", text="模型")
        self.model_tree.heading("source", text="来源")
        self.model_tree.heading("enabled", text="状态")
        self.model_tree.column("provider", width=150, stretch=False)
        self.model_tree.column("model", width=430)
        self.model_tree.column("source", width=90, stretch=False)
        self.model_tree.column("enabled", width=80, stretch=False)
        self.model_tree.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.model_tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.model_tree.configure(yscrollcommand=scrollbar.set)
        return frame

    def _build_assignments_page(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure(2, weight=1)
        ttk.Label(frame, text="主模型").grid(row=0, column=0, sticky="e", padx=(0, 12), pady=(2, 16))
        self.primary_model_var = tk.StringVar()
        self.primary_model_box = ttk.Combobox(frame, textvariable=self.primary_model_var, state="normal")
        self.primary_model_box.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(2, 16))
        self._bind_searchable_model_box(self.primary_model_box)
        ttk.Separator(frame).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        for row, (feature_id, label, _role) in enumerate(FEATURE_DEFINITIONS, start=2):
            mode_var = tk.StringVar(value="使用主模型")
            model_var = tk.StringVar()
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="e", padx=(0, 12), pady=8)
            mode_box = ttk.Combobox(
                frame,
                textvariable=mode_var,
                values=("使用主模型", "单独指定"),
                state="readonly",
                width=14,
            )
            mode_box.grid(row=row, column=1, sticky="w", pady=8)
            model_box = ttk.Combobox(frame, textvariable=model_var, state="normal")
            model_box.grid(row=row, column=2, sticky="ew", padx=(12, 0), pady=8)
            self._bind_searchable_model_box(model_box)
            mode_box.bind(
                "<<ComboboxSelected>>",
                lambda _event, variable=mode_var, box=model_box: self._sync_assignment_box(variable, box),
            )
            self.assignment_vars[feature_id] = (mode_var, model_var, model_box)
        ttk.Label(
            frame,
            text=(
                "“使用主模型”会跟随主模型变化；“单独指定”只覆盖这一项功能。"
                "模型框可连续输入检索，输入完成后按 Enter、方向下键或点击箭头查看结果。"
            ),
            wraplength=700,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(18, 0))
        return frame

    def reload_state(self, *, select_provider_id: str = "") -> None:
        self.state = self.app.model_settings_state()
        self.provider_by_id = {
            str(item.get("profile_id") or ""): item
            for item in self.state.get("providers", [])
            if isinstance(item, dict)
        }
        self.model_by_ref = {
            str(item.get("model_ref") or ""): item
            for item in self.state.get("models", [])
            if isinstance(item, dict)
        }
        self.provider_tree.delete(*self.provider_tree.get_children())
        for profile_id, provider in self.provider_by_id.items():
            marker = " ●" if provider.get("has_api_key") else ""
            self.provider_tree.insert("", "end", iid=profile_id, text=f"{provider.get('display_name')}{marker}")
        provider_labels = [str(item.get("display_name") or "") for item in self.provider_by_id.values()]
        self.model_provider_box["values"] = provider_labels
        if not self.model_provider_var.get() and provider_labels:
            self.model_provider_var.set(provider_labels[0])
        selected = select_provider_id or self.current_provider_id
        if selected in self.provider_by_id:
            self.provider_tree.selection_set(selected)
            self.provider_tree.focus(selected)
            self.load_provider(selected)
        elif self.provider_by_id:
            first = next(iter(self.provider_by_id))
            self.provider_tree.selection_set(first)
            self.load_provider(first)
        self.populate_models()
        self.populate_assignment_options()

    def show_page(self, page: str) -> None:
        self.page = page
        titles = {
            PAGE_PROVIDER: ("API 提供商", "管理服务地址和密钥。内置三家，也可不断添加自定义 OpenAI 兼容接入商。"),
            PAGE_MODELS: ("模型目录", "从接入商刷新模型，也可以手工添加模型 ID；停用后不会出现在功能分配中。"),
            PAGE_ASSIGNMENTS: ("功能分配", "设置主模型，并按正文生成、审稿、精修和记忆任务覆盖模型。"),
        }
        self.title_var.set(titles[page][0])
        self.subtitle_var.set(titles[page][1])
        {
            PAGE_PROVIDER: self.provider_page,
            PAGE_MODELS: self.models_page,
            PAGE_ASSIGNMENTS: self.assignments_page,
        }[page].tkraise()
        self.save_button.configure(text="保存功能分配" if page == PAGE_ASSIGNMENTS else "保存当前设置")

    def _on_provider_selected(self, _event: object | None = None) -> None:
        selected = self.provider_tree.selection()
        if selected:
            self.load_provider(selected[0])

    def load_provider(self, profile_id: str) -> None:
        provider = self.provider_by_id.get(profile_id, {})
        self.current_provider_id = profile_id
        self.provider_name_var.set(str(provider.get("display_name") or ""))
        self.provider_adapter_var.set(str(provider.get("adapter") or "openai_compatible"))
        self.provider_base_url_var.set(str(provider.get("base_url") or ""))
        self.provider_key_var.set("")
        self.provider_timeout_var.set(str(provider.get("timeout_seconds") or 300))
        if provider.get("has_api_key"):
            self.provider_key_status_var.set(f"Key：{provider.get('masked_api_key') or MASK_PLACEHOLDER}")
        else:
            self.provider_key_status_var.set("尚未保存 Key")
        self.delete_provider_button.state(["disabled"] if provider.get("built_in") else ["!disabled"])

    def new_custom_provider(self) -> None:
        self.current_provider_id = ""
        self.provider_tree.selection_remove(self.provider_tree.selection())
        self.provider_name_var.set("")
        self.provider_adapter_var.set("openai_compatible")
        self.provider_base_url_var.set("")
        self.provider_key_var.set("")
        self.provider_timeout_var.set("300")
        self.provider_key_status_var.set("新接入商")
        self.delete_provider_button.state(["disabled"])

    def save_provider(self) -> None:
        try:
            profile = self.app.upsert_provider_profile(
                self.current_provider_id,
                display_name=self.provider_name_var.get(),
                adapter=self.provider_adapter_var.get(),
                base_url=self.provider_base_url_var.get(),
                timeout_seconds=float(self.provider_timeout_var.get()),
            )
            profile_id = str(profile.get("profile_id") or "")
            new_key = self.provider_key_var.get().strip()
            if new_key:
                self.app.set_provider_profile_secret(profile_id, new_key)
        except Exception as exc:
            messagebox.showerror("模型设置", f"保存接入商失败：\n{exc}", parent=self.window)
            return
        self.write_log(f"模型接入商已保存: profile={profile_id}")
        self.status_var.set("接入商已保存；未发起网络请求。")
        self.reload_state(select_provider_id=profile_id)
        self._notify_saved()

    def clear_selected_provider_key(self) -> None:
        if not self.current_provider_id:
            return
        if not messagebox.askyesno("模型设置", "确认清除这个接入商保存在本机的 API Key？", parent=self.window):
            return
        try:
            self.app.clear_provider_profile_secret(self.current_provider_id)
        except Exception as exc:
            messagebox.showerror("模型设置", str(exc), parent=self.window)
            return
        self.status_var.set("API Key 已清除。")
        self.reload_state(select_provider_id=self.current_provider_id)

    def delete_selected_provider(self) -> None:
        if not self.current_provider_id:
            return
        if not messagebox.askyesno(
            "模型设置",
            "删除自定义接入商及其模型目录？已保存的 Key 不会自动删除。",
            parent=self.window,
        ):
            return
        try:
            self.app.delete_provider_profile(self.current_provider_id)
        except Exception as exc:
            messagebox.showerror("模型设置", str(exc), parent=self.window)
            return
        self.current_provider_id = ""
        self.reload_state()

    def _selected_model_provider_id(self) -> str:
        label = self.model_provider_var.get()
        for profile_id, provider in self.provider_by_id.items():
            if str(provider.get("display_name") or "") == label:
                return profile_id
        return self.current_provider_id

    def refresh_selected_provider_models(self) -> None:
        profile_id = self.current_provider_id if self.page == PAGE_PROVIDER else self._selected_model_provider_id()
        if not profile_id or self.busy:
            return
        self.busy = True
        self.status_var.set("正在刷新模型目录…")
        self.save_button.state(["disabled"])

        def worker() -> None:
            try:
                result = self.app.refresh_provider_models(profile_id)
            except Exception as exc:
                self.window.after(0, lambda error=exc: self._finish_refresh(profile_id, error=error))
            else:
                self.window.after(0, lambda value=result: self._finish_refresh(profile_id, result=value))

        threading.Thread(target=worker, name="NovelModelCatalogRefresh", daemon=True).start()

    def _finish_refresh(
        self,
        profile_id: str,
        *,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.busy = False
        self.save_button.state(["!disabled"])
        if error:
            self.status_var.set("刷新失败。")
            messagebox.showerror("模型设置", f"刷新模型目录失败：\n{error}", parent=self.window)
            return
        count = int((result or {}).get("model_count") or 0)
        self.status_var.set(f"模型目录已刷新：{count} 个模型。")
        self.write_log(f"模型目录已刷新: profile={profile_id} models={count}")
        self.reload_state(select_provider_id=profile_id)

    def populate_models(self) -> None:
        self.model_tree.delete(*self.model_tree.get_children())
        profile_id = self._selected_model_provider_id()
        query = self.model_search_var.get().strip().lower()
        for model_ref, model in self.model_by_ref.items():
            if profile_id and str(model.get("provider_profile_id") or "") != profile_id:
                continue
            searchable = f"{model.get('display_name', '')} {model.get('model_id', '')}".lower()
            if query and query not in searchable:
                continue
            provider = self.provider_by_id.get(str(model.get("provider_profile_id") or ""), {})
            self.model_tree.insert(
                "",
                "end",
                iid=model_ref,
                values=(
                    provider.get("display_name") or model.get("provider_profile_id"),
                    model.get("display_name") or model.get("model_id"),
                    "手工" if model.get("source") == "manual" else "目录",
                    "启用" if model.get("enabled", True) else "停用",
                ),
            )

    def add_manual_model(self) -> None:
        profile_id = self._selected_model_provider_id()
        if not profile_id:
            messagebox.showinfo("模型设置", "请先选择接入商。", parent=self.window)
            return
        model_id = simpledialog.askstring("手工添加模型", "模型 ID", parent=self.window)
        if not model_id:
            return
        display_name = simpledialog.askstring(
            "手工添加模型",
            "显示名称（可留空）",
            parent=self.window,
        )
        try:
            self.app.add_manual_model(profile_id, model_id, display_name=display_name or "")
        except Exception as exc:
            messagebox.showerror("模型设置", str(exc), parent=self.window)
            return
        self.reload_state(select_provider_id=profile_id)
        self.status_var.set("手工模型已添加。")

    def toggle_selected_model(self) -> None:
        selected = self.model_tree.selection()
        if not selected:
            return
        model_ref = selected[0]
        model = self.model_by_ref.get(model_ref, {})
        try:
            self.app.set_model_enabled(model_ref, not bool(model.get("enabled", True)))
        except Exception as exc:
            messagebox.showerror("模型设置", str(exc), parent=self.window)
            return
        self.reload_state(select_provider_id=str(model.get("provider_profile_id") or ""))

    def populate_assignment_options(self) -> None:
        enabled = [item for item in self.model_by_ref.values() if item.get("enabled", True)]
        self.model_label_to_ref = {}
        labels: list[str] = []
        for model in enabled:
            profile = self.provider_by_id.get(str(model.get("provider_profile_id") or ""), {})
            label = (
                f"{profile.get('display_name') or model.get('provider_profile_id')} · "
                f"{model.get('display_name') or model.get('model_id')} [{model.get('model_id')}]"
            )
            self.model_label_to_ref[label] = str(model.get("model_ref") or "")
            labels.append(label)
        self.all_model_labels = labels
        ref_to_label = {value: key for key, value in self.model_label_to_ref.items()}
        self.primary_model_box["values"] = labels
        self.primary_model_var.set(ref_to_label.get(str(self.state.get("primary_model_ref") or ""), ""))
        assignments = self.state.get("feature_assignments")
        assignments = assignments if isinstance(assignments, dict) else {}
        for feature_id, (mode_var, model_var, model_box) in self.assignment_vars.items():
            model_box["values"] = labels
            assignment = assignments.get(feature_id) if isinstance(assignments.get(feature_id), dict) else {}
            explicit = str(assignment.get("model_ref") or "")
            if str(assignment.get("mode") or "") == "model" and explicit in ref_to_label:
                mode_var.set("单独指定")
                model_var.set(ref_to_label[explicit])
            else:
                mode_var.set("使用主模型")
                model_var.set("")
            self._sync_assignment_box(mode_var, model_box)

    @staticmethod
    def _sync_assignment_box(mode_var: tk.StringVar, model_box: ttk.Combobox) -> None:
        model_box.configure(state="normal" if mode_var.get() == "单独指定" else "disabled")

    def _bind_searchable_model_box(self, model_box: ttk.Combobox) -> None:
        model_box.bind("<KeyRelease>", self._on_model_search_key, add="+")
        model_box.bind(
            "<<ComboboxSelected>>",
            lambda _event, box=model_box: box.configure(values=self.all_model_labels),
            add="+",
        )
        model_box.bind(
            "<FocusIn>",
            lambda _event, box=model_box: box.after_idle(lambda: box.selection_range(0, tk.END)),
            add="+",
        )

    def _on_model_search_key(self, event: tk.Event[tk.Misc]) -> None:
        box = event.widget
        if not isinstance(box, ttk.Combobox) or str(box.cget("state")) == "disabled":
            return
        if event.keysym in {
            "Up",
            "Down",
            "Left",
            "Right",
            "Home",
            "End",
            "Escape",
            "Tab",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
        }:
            return
        matches = filter_model_labels(self.all_model_labels, box.get())
        box.configure(values=matches)
        self.status_var.set(
            f"匹配到 {len(matches)} 个模型；可继续输入，完成后按 Enter 或点击箭头选择。"
        )
        if matches and event.keysym in {"Return", "KP_Enter"}:
            box.after_idle(lambda current=box: self._post_model_results(current))

    @staticmethod
    def _post_model_results(model_box: ttk.Combobox) -> None:
        if not model_box.winfo_exists() or str(model_box.cget("state")) == "disabled":
            return
        try:
            model_box.tk.call("ttk::combobox::Post", str(model_box))
        except tk.TclError:
            return

    def save_assignments(self) -> None:
        primary_ref = self.model_label_to_ref.get(self.primary_model_var.get(), "")
        assignments: dict[str, dict[str, str]] = {}
        for feature_id, (mode_var, model_var, _box) in self.assignment_vars.items():
            explicit = mode_var.get() == "单独指定"
            assignments[feature_id] = {
                "mode": "model" if explicit else "inherit",
                "model_ref": self.model_label_to_ref.get(model_var.get(), "") if explicit else "",
            }
        try:
            self.app.update_model_assignments(
                primary_model_ref=primary_ref,
                feature_assignments=assignments,
            )
        except Exception as exc:
            messagebox.showerror("模型设置", f"保存功能分配失败：\n{exc}", parent=self.window)
            return
        self.status_var.set("主模型和功能分配已保存。")
        self.write_log("模型功能分配已保存。")
        self.reload_state(select_provider_id=self.current_provider_id)
        self._notify_saved()

    def save_current_page(self) -> None:
        if self.page == PAGE_PROVIDER:
            self.save_provider()
        elif self.page == PAGE_ASSIGNMENTS:
            self.save_assignments()
        else:
            self.status_var.set("模型目录的添加、启用和停用会即时保存。")

    def _notify_saved(self) -> None:
        if self.on_saved:
            self.on_saved()

    def close(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()


def open_model_settings_dialog(
    owner: tk.Misc,
    app: Any,
    *,
    on_saved: Callable[[], None] | None = None,
    write_log: Callable[[str], None] | None = None,
) -> ModelSettingsDialog:
    return ModelSettingsDialog(owner, app, on_saved=on_saved, write_log=write_log)
