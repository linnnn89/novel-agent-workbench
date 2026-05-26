from __future__ import annotations

import json
import os
import re
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable
from urllib.parse import urlparse

from .application_service import WorkbenchApplicationService
from .config import default_generation_settings
from .context_assembler import DEFAULT_CHARS_PER_TOKEN
from .memory_bank import DEFAULT_MEMORY_TARGET_TOKENS, normalize_memory_target_tokens
from .providers import DEFAULT_PROVIDER_TIMEOUT_SECONDS
from .storage import DEFAULT_PROJECTS_DIRNAME


APP_TITLE = "小说创作工作台"
APP_SUBTITLE = "本地小说创作工作台"
WINDOW_MIN_SIZE = (1120, 720)
TOP_NAV_SECTIONS = (
    {
        "label": "工作台",
        "items": (
            ("project_health", "当前项目概览"),
            ("open_project_folder", "打开作品文件夹"),
            ("open_data_root", "打开项目库"),
        ),
    },
    {
        "label": "创作",
        "items": (
            ("chapter_list", "章节列表"),
            ("generate_draft", "生成草稿"),
            ("review_rewrite", "审稿与改写"),
            ("confirmed_chapters", "已确认章节"),
        ),
    },
    {
        "label": "资料库",
        "items": (
            ("planning_library", "大纲与章节"),
            ("world_materials", "世界观与人物"),
            ("memory_bank", "记忆库"),
            ("corpus_style", "参考作品与风格（开发中）"),
        ),
    },
    {
        "label": "模型",
        "items": (
            ("model_connection", "模型服务"),
            ("model_self_check", "连接检查"),
        ),
    },
    {
        "label": "创作设置",
        "items": (
            ("generation_params", "全局提示词与上下文"),
            ("generation_params", "全局采样参数"),
            ("choose_data_root", "项目库位置"),
            ("refresh_all", "刷新"),
            ("clear_trash", "清空回收站"),
        ),
    },
    {
        "label": "定稿",
        "items": (
            ("confirmed_chapters", "已确认章节"),
            ("export_txt", "导出TXT文稿"),
            ("final_checklist", "出稿清单（开发中）"),
            ("export_settings", "导出设置"),
        ),
    },
    {
        "label": "帮助",
        "items": (
            ("user_guide", "使用说明"),
            ("project_self_check", "开发者诊断"),
            ("model_call_records", "模型调用记录（排障）"),
            ("run_log", "运行记录"),
            ("about", "关于软件"),
        ),
    },
)
TOP_NAV_LABELS = tuple(str(section["label"]) for section in TOP_NAV_SECTIONS)
SYSTEM_SETTING_ACTIONS = ("更改项目库", "打开项目库", "刷新")
PROJECT_ACTIONS = (
    "新建作品",
    "生成草稿",
    "AI审稿",
    "确认稿件",
    "要求重写（重新随机）",
    "根据审稿精修",
    "项目专属设置",
    "打开作品文件夹",
)
MODEL_ROLE_OPTIONS = (
    ("writer", "正文生成"),
    ("scorer", "AI审稿"),
    ("reviser", "AI精修/改写"),
)
MODEL_PROVIDER_PRESETS = (
    {
        "label": "离线测试（不联网）",
        "provider": "mock",
        "default_model": "mock-writer",
        "default_base_url": "",
        "secret_required": False,
    },
    {
        "label": "OpenAI 兼容云端 API",
        "provider": "openai_compatible",
        "default_model": "",
        "default_base_url": "",
        "secret_required": True,
    },
    {
        "label": "Chutes API",
        "provider": "chutes_openai",
        "default_model": "Qwen/Qwen3-32B-TEE",
        "default_base_url": "https://llm.chutes.ai/v1",
        "secret_required": True,
    },
    {
        "label": "DeepSeek API",
        "provider": "deepseek",
        "default_model": "deepseek-v4-flash",
        "default_base_url": "https://api.deepseek.com/v1",
        "secret_required": True,
    },
    {
        "label": "OpenRouter API",
        "provider": "openrouter",
        "default_model": "",
        "default_base_url": "https://openrouter.ai/api/v1",
        "secret_required": True,
    },
    {
        "label": "本地 OpenAI 兼容端口（LM Studio / Ollama）",
        "provider": "local_openai_compatible",
        "default_model": "",
        "default_base_url": "http://127.0.0.1:1234/v1",
        "secret_required": False,
    },
)
SAVED_SECRET_MASK = "********"
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
PLANNING_TYPE_OPTIONS = (
    ("outline", "总纲"),
    ("beat_sheet", "节拍表"),
    ("chapter_plan", "章节计划"),
    ("character_plan", "角色设定"),
    ("world_plan", "世界观设定"),
    ("constraint", "写作约束"),
    ("other", "其他资料"),
)
PLANNING_ADHERENCE_OPTIONS = (
    ("soft", "参考即可"),
    ("balanced", "正常遵守"),
    ("strict", "严格遵守"),
)
SINGLETON_PLANNING_TYPES = {"outline", "world_plan"}


def default_projects_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "用户数据" / DEFAULT_PROJECTS_DIRNAME
    return Path(__file__).resolve().parents[2] / DEFAULT_PROJECTS_DIRNAME


def default_repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "novel_agent_workbench" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def icon_path() -> Path:
    return asset_path("novel_agent_workbench.ico")


class WorkbenchDesktopApp(tk.Tk):
    def __init__(self, *, projects_root: Path | None = None, repo_root: Path | None = None) -> None:
        super().__init__()
        self.projects_root = projects_root or default_projects_root()
        self.repo_root = repo_root or default_repo_root()
        self.app = WorkbenchApplicationService.open(self.projects_root)
        self.projects: list[dict[str, Any]] = []
        self.selected_project_id = ""
        self.current_draft_project_id = ""
        self.current_draft_ids: list[str] = []
        self.current_draft_index = -1
        self.current_draft_loading = False
        self.current_draft_autosave_job: str | None = None
        self.live_generation_key: tuple[str, str] | None = None
        self.main_canvas: tk.Canvas | None = None
        self.main_scrollbar: ttk.Scrollbar | None = None
        self.thinking_window: tk.Toplevel | None = None
        self.thinking_body: tk.Text | None = None
        self.thinking_closed_generation_key: tuple[str, str] | None = None
        self.hidden_stale_draft_ids: set[tuple[str, str]] = set()
        self.prompted_stale_draft_ids: set[tuple[str, str]] = set()

        self.title(APP_TITLE)
        self.minsize(*WINDOW_MIN_SIZE)
        self.geometry("1180x760")
        self._set_window_icon()
        self._configure_style()
        self._build_layout()
        self.refresh_projects()

    def _set_window_icon(self) -> None:
        path = icon_path()
        if path.exists():
            try:
                self.iconbitmap(str(path))
            except tk.TclError:
                pass

    def _configure_style(self) -> None:
        self.configure(bg="#f6f7fb")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TopNav.TFrame", background="#f5edf5")
        style.configure("TopNav.TLabel", font=("Microsoft YaHei UI", 11), background="#f5edf5", foreground="#5d5560")
        style.configure("TopNav.TMenubutton", font=("Microsoft YaHei UI", 11), background="#f5edf5", foreground="#4b4550")
        style.configure("Settings.TFrame", background="#ffffff")
        style.configure("Sidebar.TFrame", background="#fbf5fb")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), background="#ffffff", foreground="#19202d")
        style.configure("Subtle.TLabel", background="#f6f7fb", foreground="#5a6475")
        style.configure("SettingsLabel.TLabel", background="#ffffff", foreground="#5a6475")
        style.configure("SidebarLabel.TLabel", background="#fbf5fb", foreground="#8a8190")
        style.configure("Panel.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        style.configure("PanelTitle.TLabel", font=("Microsoft YaHei UI", 11, "bold"), background="#ffffff", foreground="#19202d")
        style.configure("PanelText.TLabel", background="#ffffff", foreground="#394150")
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), foreground="#ffffff", background="#2563eb")
        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("pressed", "#1e40af"), ("disabled", "#93a4c7")],
            foreground=[("disabled", "#f5f7fb")],
        )
        style.configure("Secondary.TButton", font=("Microsoft YaHei UI", 10), foreground="#374151", background="#eef2f7")
        style.map("Secondary.TButton", background=[("active", "#e2e8f0"), ("pressed", "#cbd5e1")])
        style.configure("Quiet.TButton", font=("Microsoft YaHei UI", 9), foreground="#4b5563", background="#f8fafc")
        style.map("Quiet.TButton", background=[("active", "#eef2f7"), ("pressed", "#e2e8f0")])
        style.configure("StatusOk.TLabel", background="#ffffff", foreground="#176b3a", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("StatusWarn.TLabel", background="#ffffff", foreground="#9a5b00", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("StatusBlock.TLabel", background="#ffffff", foreground="#9d1c1c", font=("Microsoft YaHei UI", 11, "bold"))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        nav = ttk.Frame(self, padding=(20, 10, 20, 8), style="TopNav.TFrame")
        nav.grid(row=0, column=0, columnspan=2, sticky="ew")
        for section in TOP_NAV_SECTIONS:
            button = ttk.Menubutton(nav, text=str(section["label"]), style="TopNav.TMenubutton")
            menu = tk.Menu(button, tearoff=False)
            for action, item_label in section["items"]:
                command = self.top_nav_command(str(action))
                menu.add_command(label=str(item_label), command=command or self.show_unavailable)
            button["menu"] = menu
            button.pack(side="left", padx=(0, 18))

        header = ttk.Frame(self, padding=(24, 14, 24, 12), style="Settings.TFrame")
        header.grid(row=1, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 22))
        ttk.Label(header, text="项目库位置", style="SettingsLabel.TLabel").grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.root_var = tk.StringVar(value=str(self.projects_root))
        ttk.Entry(header, textvariable=self.root_var, width=44).grid(row=0, column=2, sticky="ew", padx=(0, 10))
        for offset, (label, command) in enumerate(
            [
                ("更改项目库", self.choose_data_root),
                ("打开项目库", self.open_data_root),
                ("刷新", self.refresh_all),
            ],
            start=3,
        ):
            ttk.Button(header, text=label, command=command).grid(row=0, column=offset, sticky="e", padx=(0, 8))

        sidebar = ttk.Frame(self, padding=(18, 18, 12, 18), style="Sidebar.TFrame")
        sidebar.grid(row=2, column=0, sticky="ns")
        sidebar.rowconfigure(1, weight=1)
        sidebar.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="项目", style="SidebarLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.project_tree = ttk.Treeview(sidebar, show="tree", selectmode="browse", height=23)
        self.project_tree.grid(row=1, column=0, sticky="nsew")
        self.project_tree.bind("<<TreeviewSelect>>", self.on_project_selected)
        self.project_tree.bind("<<TreeviewOpen>>", self.on_project_tree_open)
        self.project_tree.bind("<Double-1>", self.on_project_tree_double_click)
        self.project_tree.bind("<Button-3>", self.show_project_context_menu)
        self.project_tree.bind("<Button-2>", self.show_project_context_menu)
        project_actions = ttk.Frame(sidebar, padding=(0, 12, 0, 0), style="Sidebar.TFrame")
        project_actions.grid(row=2, column=0, sticky="ew")
        project_actions.columnconfigure(0, weight=1)
        quick_actions: list[tuple[str, Callable[[], None], str]] = [
            ("生成草稿", self.show_generate_draft_dialog, "Primary.TButton"),
            ("AI审稿", self.ai_review_current_draft, "Secondary.TButton"),
            ("确认稿件", self.confirm_current_draft, "Secondary.TButton"),
            ("要求重写（重新随机）", self.rewrite_current_draft, "Secondary.TButton"),
            ("根据审稿精修", self.refine_current_draft_from_ai_review, "Secondary.TButton"),
        ]
        project_actions_list: list[tuple[str, Callable[[], None], str]] = [
            ("新建作品", self.create_project_dialog, "Quiet.TButton"),
            ("项目专属设置", self.show_project_generation_settings_dialog, "Quiet.TButton"),
            ("打开作品文件夹", self.open_selected_project_folder, "Quiet.TButton"),
        ]
        row = 0
        ttk.Label(project_actions, text="快捷操作", style="SidebarLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 8))
        row += 1
        for label, command, style_name in quick_actions:
            ttk.Button(project_actions, text=label, command=command, style=style_name).grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(0, 8),
            )
            row += 1
        ttk.Label(project_actions, text="项目", style="SidebarLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(6, 8))
        row += 1
        for label, command, style_name in project_actions_list:
            ttk.Button(project_actions, text=label, command=command, style=style_name).grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(0, 8),
            )
            row += 1

        main_host = ttk.Frame(self, style="TFrame")
        main_host.grid(row=2, column=1, sticky="nsew")
        main_host.rowconfigure(0, weight=1)
        main_host.columnconfigure(0, weight=1)
        self.main_canvas = tk.Canvas(main_host, borderwidth=0, highlightthickness=0, background="#f6f7fb")
        self.main_scrollbar = ttk.Scrollbar(main_host, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.on_main_canvas_scroll)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        main = ttk.Frame(self.main_canvas, padding=(12, 18, 24, 18), style="TFrame")
        main_window = self.main_canvas.create_window((0, 0), window=main, anchor="nw")
        main.bind("<Configure>", lambda event: self.update_main_scroll_region())
        self.main_canvas.bind(
            "<Configure>",
            lambda event: (
                self.main_canvas.itemconfigure(main_window, width=event.width),
                self.update_main_scroll_region(),
            )
            if self.main_canvas
            else None,
        )
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=0, minsize=150)
        main.rowconfigure(1, weight=24, minsize=380)
        main.rowconfigure(2, weight=0, minsize=86)

        self.summary_frame = self._panel(main, row=0, column=0, title="项目状态")
        self.summary_text = tk.StringVar(value="请选择一个项目。")
        self.summary_label = ttk.Label(
            self.summary_frame,
            textvariable=self.summary_text,
            style="PanelText.TLabel",
            justify="left",
            wraplength=470,
        )
        self.summary_label.grid(row=1, column=0, sticky="nw", padx=18, pady=(4, 18))

        self.provider_frame = self._panel(main, row=0, column=1, title="模型服务")
        self.provider_frame.rowconfigure(1, weight=1)
        self.provider_body = tk.Text(
            self.provider_frame,
            height=9,
            wrap="word",
            borderwidth=0,
            font=("Microsoft YaHei UI", 10),
            foreground="#273043",
            background="#fbfcff",
            padx=8,
            pady=6,
        )
        provider_scroll = ttk.Scrollbar(self.provider_frame, orient="vertical", command=self.provider_body.yview)
        self.provider_body.configure(yscrollcommand=provider_scroll.set)
        self.provider_body.grid(row=1, column=0, sticky="nsew", padx=(18, 0), pady=(4, 18))
        provider_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 18), pady=(4, 18))
        self.set_provider_summary("模型服务默认不会自动联网。")

        draft_panel = self._panel(main, row=1, column=0, columnspan=2, title="稿件浏览与确认")
        draft_panel.rowconfigure(3, weight=1, minsize=260)
        draft_panel.columnconfigure(0, weight=1)
        self.draft_meta_var = tk.StringVar(value="生成草稿后会在这里显示；也可以展开左侧项目下的确认章节查看。")
        ttk.Label(draft_panel, textvariable=self.draft_meta_var, style="PanelText.TLabel").grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 2),
        )
        self.draft_hint_var = tk.StringVar(value="编辑会自动保存到当前项目文件夹。")
        ttk.Label(draft_panel, textvariable=self.draft_hint_var, style="Subtle.TLabel").grid(
            row=2,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 8),
        )
        self.draft_body = tk.Text(
            draft_panel,
            height=16,
            wrap="word",
            borderwidth=0,
            undo=True,
            maxundo=200,
            autoseparators=True,
            font=("Microsoft YaHei UI", 12),
            foreground="#1f2937",
            background="#fbfcff",
            insertwidth=2,
            padx=12,
            pady=10,
        )
        draft_scroll = ttk.Scrollbar(draft_panel, orient="vertical", command=self.draft_body.yview)
        self.draft_body.configure(yscrollcommand=draft_scroll.set)
        self.draft_body.grid(row=3, column=0, sticky="nsew", padx=(18, 0), pady=(0, 8))
        draft_scroll.grid(row=3, column=1, sticky="ns", padx=(0, 18), pady=(0, 8))
        self.draft_body.insert("1.0", "暂无稿件。")
        self.draft_body.configure(state="disabled")
        self.draft_body.bind("<<Modified>>", self.on_draft_text_modified)
        draft_buttons = ttk.Frame(draft_panel)
        draft_buttons.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 14))
        ttk.Button(draft_buttons, text="前一版", command=self.show_previous_draft_version).pack(side="left", padx=(0, 8))
        ttk.Button(draft_buttons, text="下一版", command=self.show_next_draft_version).pack(side="left", padx=(0, 16))
        ttk.Button(draft_buttons, text="保存编辑", command=self.save_current_draft_edit, style="Secondary.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(draft_buttons, text="AI审稿", command=self.ai_review_current_draft, style="Secondary.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(draft_buttons, text="确认稿件", command=self.confirm_current_draft, style="Primary.TButton").pack(side="right", padx=(8, 0))
        ttk.Button(draft_buttons, text="根据审稿精修", command=self.refine_current_draft_from_ai_review, style="Secondary.TButton").pack(
            side="right",
            padx=(8, 0),
        )
        ttk.Button(draft_buttons, text="要求重写（重新随机）", command=self.rewrite_current_draft, style="Quiet.TButton").pack(side="right")

        log_panel = self._panel(main, row=2, column=0, columnspan=2, title="运行记录")
        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_panel,
            height=3,
            wrap="word",
            borderwidth=0,
            font=("Consolas", 10),
            foreground="#273043",
            background="#fbfcff",
        )
        self.log.grid(row=1, column=0, sticky="nsew", padx=18, pady=(4, 18))
        self.write_log("启动完成。保存模型配置不会联网；点击测试连接或生成草稿时才会联网。")

    def top_nav_command(self, action: str) -> Any:
        commands = {
            "project_health": self.run_project_health,
            "open_project_folder": self.open_selected_project_folder,
            "open_data_root": self.open_data_root,
            "chapter_list": self.show_chapter_list,
            "generate_draft": self.show_generate_draft_dialog,
            "review_rewrite": self.show_review_rewrite,
            "confirmed_chapters": self.show_confirmed_chapters,
            "planning_library": self.show_planning_library,
            "world_materials": self.show_world_materials,
            "memory_bank": self.show_memory_bank,
            "corpus_style": self.show_corpus_style,
            "model_connection": self.configure_model_connection,
            "model_self_check": self.show_model_self_check,
            "generation_params": self.show_generation_params,
            "model_call_records": self.show_model_call_records,
            "final_checklist": self.show_final_checklist,
            "export_txt": self.export_txt_dialog,
            "export_settings": self.show_export_settings,
            "project_self_check": self.run_prepublish_check,
            "choose_data_root": self.choose_data_root,
            "refresh_all": self.refresh_all,
            "clear_trash": self.clear_trash_dialog,
            "user_guide": self.show_user_guide,
            "run_log": self.show_run_log_window,
            "about": self.show_about,
        }
        return commands.get(action)

    def show_unavailable(self) -> None:
        messagebox.showinfo(APP_TITLE, "这个入口还没有可用动作。")

    def update_main_scroll_region(self) -> None:
        if self.main_canvas is None:
            return
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        first, last = self.main_canvas.yview()
        self.on_main_canvas_scroll(str(first), str(last))

    def on_main_canvas_scroll(self, first: str, last: str) -> None:
        if self.main_canvas is None or self.main_scrollbar is None:
            return
        self.main_scrollbar.set(first, last)
        needs_scrollbar = float(first) > 0.0 or float(last) < 1.0
        if needs_scrollbar:
            if not self.main_scrollbar.winfo_ismapped():
                self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        elif self.main_scrollbar.winfo_ismapped():
            self.main_scrollbar.grid_remove()

    def _panel(self, parent: ttk.Frame, *, row: int, column: int, title: str, columnspan: int = 1) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=(0, 0, 0, 0), style="Panel.TFrame")
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=6, pady=6)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=title, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))
        return frame

    def refresh_all(self) -> None:
        self.refresh_projects()
        if self.selected_project_id:
            self.run_project_health(silent=True)

    def refresh_projects(self) -> None:
        previous_project_id = self.selected_project_id
        try:
            self.app = WorkbenchApplicationService.open(self.projects_root)
            self.projects = self.app.list_projects()
        except Exception as exc:
            self.projects = []
            self.write_log(f"项目列表读取失败: {exc}")
            messagebox.showerror(APP_TITLE, f"项目列表读取失败:\n{exc}")
        for item_id in self.project_tree.get_children(""):
            self.project_tree.delete(item_id)
        for item in self.projects:
            project_id = str(item.get("project_id") or "")
            title = str(item.get("title") or project_id)
            node_id = project_node_id(project_id)
            self.project_tree.insert("", "end", iid=node_id, text=f"{title}  ({project_id})", open=False)
            self.load_project_work_nodes(project_id)
        if self.projects:
            project_ids = {str(item.get("project_id") or "") for item in self.projects}
            target_project_id = previous_project_id if previous_project_id in project_ids else str(self.projects[0].get("project_id") or "")
            target_id = project_node_id(target_project_id)
            self.project_tree.selection_set(target_id)
            self.project_tree.focus(target_id)
            self.on_project_selected()
        else:
            self.selected_project_id = ""
            self.summary_text.set("当前项目库还没有作品。可以点击“新建作品”。")
            self.set_provider_summary("模型服务默认不会自动联网。")

    def on_project_selected(self, event: object | None = None) -> None:
        selection = self.project_tree.selection()
        if not selection:
            return
        kind, project_id, item_id = parse_tree_node_id(str(selection[0]))
        if kind not in {"project", "chapter", "draft"} or not project_id:
            return
        self.selected_project_id = project_id
        self.run_project_health(silent=True)
        if kind == "chapter" and item_id:
            self.show_chapter_browser(project_id, item_id)
        elif kind == "draft" and item_id:
            self.show_draft_workspace(project_id, item_id)

    def on_project_tree_open(self, event: object | None = None) -> None:
        node_id = str(self.project_tree.focus() or "")
        kind, project_id, _ = parse_tree_node_id(node_id)
        if kind == "project" and project_id:
            self.load_project_work_nodes(project_id)

    def on_project_tree_double_click(self, event: tk.Event) -> None:
        node_id = self.project_tree.identify_row(event.y)
        kind, project_id, item_id = parse_tree_node_id(str(node_id))
        if kind == "chapter" and project_id and item_id:
            self.show_chapter_browser(project_id, item_id)
        elif kind == "draft" and project_id and item_id:
            self.show_draft_workspace(project_id, item_id)

    def load_confirmed_chapter_nodes(self, project_id: str) -> None:
        self.load_project_work_nodes(project_id)

    def load_project_work_nodes(self, project_id: str) -> None:
        node_id = project_node_id(project_id)
        if not self.project_tree.exists(node_id):
            return
        for child in self.project_tree.get_children(node_id):
            self.project_tree.delete(child)
        try:
            chapters = self.app.list_confirmed_chapters(project_id)
        except Exception:
            chapters = []
        drafts = self.readable_draft_summaries(project_id)
        for child in self.project_tree.get_children(node_id):
            self.project_tree.delete(child)
        inserted_nodes: set[str] = set()
        confirmed_by_chapter = {str(item.get("chapter_id") or ""): item for item in chapters if item.get("chapter_id")}
        active_confirmed_draft_ids = {
            str(item.get("source_draft_id") or "") for item in chapters if item.get("source_draft_id")
        }
        drafts_by_chapter: dict[str, list[dict[str, Any]]] = {}
        root_drafts: list[dict[str, Any]] = []
        for draft in drafts:
            chapter_id = str(draft.get("chapter_id") or "")
            if chapter_id:
                drafts_by_chapter.setdefault(chapter_id, []).append(draft)
            else:
                root_drafts.append(draft)
        chapter_ids = sorted(
            set(confirmed_by_chapter) | set(drafts_by_chapter),
            key=lambda value: (chapter_sort_number(value), value),
        )
        for chapter_id in chapter_ids:
            chapter = confirmed_by_chapter.get(chapter_id, {})
            item_id = chapter_node_id(project_id, chapter_id)
            if item_id in inserted_nodes or self.project_tree.exists(item_id):
                self.write_log(f"已跳过重复确认章节索引: project={project_id} chapter={chapter_id}")
                continue
            inserted_nodes.add(item_id)
            chapter_drafts = sorted_draft_versions(drafts_by_chapter.get(chapter_id, []))
            title = str(chapter.get("title") or latest_draft_title(chapter_drafts) or chapter_id)
            status_text = "已确认" if chapter_id in confirmed_by_chapter else "有草稿"
            self.project_tree.insert(
                node_id,
                "end",
                iid=item_id,
                text=f"{chapter_id}  {title}（{status_text}）",
            )
            for index, draft in enumerate(chapter_drafts):
                draft_id = str(draft.get("draft_id") or "")
                if not draft_id:
                    continue
                draft_item_id = draft_node_id(project_id, draft_id)
                if draft_item_id in inserted_nodes or self.project_tree.exists(draft_item_id):
                    self.write_log(f"已跳过重复草稿索引: project={project_id} draft_id={draft_id}")
                    continue
                inserted_nodes.add(draft_item_id)
                version_label = draft_version_text(draft, index)
                draft_status = "已确认" if draft_id in active_confirmed_draft_ids else "未确认"
                title_suffix = str(draft.get("title") or "")
                title_suffix = f"  {title_suffix}" if title_suffix and title_suffix != chapter_id else ""
                self.project_tree.insert(
                    item_id,
                    "end",
                    iid=draft_item_id,
                    text=f"{version_label}{title_suffix}（{draft_status}）",
                )
        for index, draft in enumerate(sorted_draft_versions(root_drafts)):
            draft_id = str(draft.get("draft_id") or "")
            if not draft_id:
                continue
            item_id = draft_node_id(project_id, draft_id)
            if item_id in inserted_nodes or self.project_tree.exists(item_id):
                self.write_log(f"已跳过重复草稿索引: project={project_id} draft_id={draft_id}")
                continue
            inserted_nodes.add(item_id)
            chapter_id = str(draft.get("chapter_id") or "")
            title = str(draft.get("title") or chapter_id or draft_id)
            version_label = draft_version_text(draft, index)
            prefix = f"{chapter_id}  " if chapter_id else ""
            self.project_tree.insert(
                node_id,
                "end",
                iid=item_id,
                text=f"{prefix}{title}  {version_label}（未确认）",
            )

    def show_project_context_menu(self, event: tk.Event) -> None:
        node_id = self.project_tree.identify_row(event.y)
        kind, project_id, item_id = parse_tree_node_id(str(node_id))
        if kind not in {"project", "chapter", "draft"} or not project_id:
            return
        self.project_tree.selection_set(node_id)
        self.project_tree.focus(node_id)
        self.on_project_selected()
        menu = tk.Menu(self, tearoff=False)
        if kind == "chapter" and item_id:
            menu.add_command(label="打开章节", command=lambda: self.show_chapter_browser(project_id, item_id))
            menu.add_command(label="AI审稿当前稿", command=self.ai_review_current_draft)
            menu.add_command(label="本地初审当前稿", command=self.review_current_draft)
            menu.add_command(label="要求重写（重新随机）当前稿", command=self.rewrite_current_draft)
            menu.add_command(label="根据审稿精修当前稿", command=self.refine_current_draft_from_ai_review)
            menu.add_separator()
            menu.add_command(label="删除本章草稿", command=lambda: self.delete_chapter_drafts_dialog(project_id, item_id))
            menu.add_separator()
            menu.add_command(label="记忆库", command=self.show_memory_bank)
            menu.add_command(label="大纲与章节", command=self.show_planning_library)
            menu.add_command(label="查看生成时会带的上下文", command=self.summarize_project_context)
        elif kind == "draft" and item_id:
            menu.add_command(label="打开草稿", command=lambda: self.show_draft_workspace(project_id, item_id))
            menu.add_command(label="AI审稿", command=lambda: self.ai_review_draft_by_id(project_id, item_id))
            menu.add_command(label="本地初审", command=lambda: self.review_draft_by_id(project_id, item_id))
            menu.add_command(label="确认稿件", command=lambda: self.confirm_draft_by_id(project_id, item_id))
            menu.add_command(label="要求重写（重新随机）", command=lambda: self.rewrite_draft_by_id(project_id, item_id))
            menu.add_command(label="根据审稿精修", command=lambda: self.refine_draft_by_id(project_id, item_id))
            menu.add_separator()
            menu.add_command(label="记忆库", command=self.show_memory_bank)
            menu.add_command(label="大纲与章节", command=self.show_planning_library)
            menu.add_command(label="查看生成时会带的上下文", command=self.summarize_project_context)
        else:
            for label, command in (
                ("生成草稿", self.show_generate_draft_dialog),
                ("AI审稿当前稿", self.ai_review_current_draft),
                ("本地初审当前稿", self.review_current_draft),
                ("确认当前稿", self.confirm_current_draft),
                ("要求重写（重新随机）当前稿", self.rewrite_current_draft),
                ("根据审稿精修当前稿", self.refine_current_draft_from_ai_review),
                ("查看生成时会带的上下文", self.summarize_project_context),
                ("记忆库", self.show_memory_bank),
                ("项目专属设置", self.show_project_generation_settings_dialog),
                ("大纲与章节", self.show_planning_library),
                ("模型服务", self.configure_model_connection),
                ("打开作品文件夹", self.open_selected_project_folder),
            ):
                menu.add_command(label=label, command=command)
            menu.add_separator()
            menu.add_command(label="删除作品", command=lambda: self.delete_project_dialog(project_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def choose_data_root(self) -> None:
        selected = filedialog.askdirectory(title="选择项目库位置", initialdir=str(self.projects_root))
        if not selected:
            return
        self.projects_root = Path(selected).resolve()
        self.root_var.set(str(self.projects_root))
        self.write_log(f"项目库位置: {self.projects_root}")
        self.refresh_projects()

    def create_project_dialog(self) -> None:
        project_id = simpledialog.askstring(APP_TITLE, "作品 ID（英文、数字、下划线）:")
        if not project_id:
            return
        title = simpledialog.askstring(APP_TITLE, "作品标题（可留空）:") or project_id
        try:
            self.app.create_project(project_id.strip(), title=title.strip())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"新建作品失败:\n{exc}")
            self.write_log(f"新建作品失败: {exc}")
            return
        self.write_log(f"新建作品: {project_id.strip()}")
        self.refresh_projects()

    def delete_project_dialog(self, project_id: str) -> None:
        project = next((item for item in self.projects if item.get("project_id") == project_id), {})
        title = str(project.get("title") or project_id)
        warning = (
            f"将删除整个作品：{title}\n\n"
            f"作品 ID：{project_id}\n\n"
            "这会把作品目录移入本项目库的 .trash 回收文件夹名，并从项目列表移除。\n"
            "作品内草稿、定稿、设置、API Key、本地资料都会一起移走。\n\n"
            "继续前请确认你不再需要从软件里直接打开它。"
        )
        if not messagebox.askyesno(APP_TITLE, warning):
            return
        typed = simpledialog.askstring(APP_TITLE, "如需删除整个作品，请输入：确认删除")
        if typed != "确认删除":
            self.write_log(f"取消删除作品: project={project_id}")
            messagebox.showinfo(APP_TITLE, "未输入“确认删除”，已取消。")
            return
        try:
            result = self.app.delete_project(project_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"删除作品失败:\n{exc}")
            self.write_log(f"删除作品失败: project={project_id} error={exc}")
            return
        self.selected_project_id = ""
        self.current_draft_project_id = ""
        self.current_draft_ids = []
        self.current_draft_index = -1
        self.draft_meta_var.set("稿件浏览与确认")
        self.draft_body.delete("1.0", tk.END)
        self.refresh_projects()
        self.write_log(
            f"删除作品: project={project_id} trashed_path={result.get('trashed_path')}"
        )
        messagebox.showinfo(APP_TITLE, "作品已移入回收站。可在“创作设置 > 清空回收站”彻底删除 .trash。")

    def delete_chapter_drafts_dialog(self, project_id: str, chapter_id: str) -> None:
        message = (
            f"将删除章节 {chapter_id} 的草稿、AI审稿记录和精修请求。\n\n"
            "已确认章节会保留；为了保持定稿一致性，已确认章节对应的提交源稿也会保留。\n"
            "删除前会自动创建 checkpoint，删除的文件会先移入 .trash。"
        )
        if not messagebox.askyesno(APP_TITLE, message):
            return
        try:
            result = self.app.delete_chapter_drafts(project_id, chapter_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"删除章节草稿失败:\n{exc}")
            self.write_log(f"删除章节草稿失败: project={project_id} chapter={chapter_id} error={exc}")
            return
        deleted_count = len(result.get("deleted_draft_ids") or [])
        review_count = len(result.get("removed_reviews") or [])
        revision_count = len(result.get("removed_revision_requests") or [])
        self.write_log(
            f"删除章节草稿: project={project_id} chapter={chapter_id} "
            f"drafts={deleted_count} reviews={review_count} revisions={revision_count}"
        )
        self.load_project_work_nodes(project_id)
        self.run_project_health(silent=True)
        if self.current_draft_project_id == project_id:
            self.current_draft_project_id = ""
            self.current_draft_ids = []
            self.current_draft_index = -1
            self.draft_meta_var.set("稿件浏览与确认")
            self.draft_body.delete("1.0", tk.END)
        messagebox.showinfo(
            APP_TITLE,
            f"已删除本章草稿 {deleted_count} 个，审稿记录 {review_count} 个，精修请求 {revision_count} 个。\n"
            f"已确认章节保留：{'是' if result.get('confirmed_chapter_retained') else '否'}",
        )

    def clear_trash_dialog(self) -> None:
        message = (
            "将彻底删除当前项目库下所有 .trash 回收文件和目录。\n\n"
            "这包括被删除的作品、草稿、审稿记录、旧备份退役文件等。\n"
            "清空后不能从软件内恢复。确定继续？"
        )
        if not messagebox.askyesno(APP_TITLE, message):
            return
        try:
            result = self.app.clear_trash()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"清空回收站失败:\n{exc}")
            self.write_log(f"清空回收站失败: {exc}")
            return
        removed_count = int(result.get("removed_count") or 0)
        removed_bytes = int(result.get("removed_bytes") or 0)
        self.write_log(f"清空回收站: removed={removed_count} bytes={removed_bytes}")
        self.refresh_projects()
        messagebox.showinfo(APP_TITLE, f"回收站已清空：删除 {removed_count} 项，约 {format_bytes(removed_bytes)}。")

    def run_project_health(self, *, silent: bool = False) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        try:
            health = self.app.project_health(project_id, repo_root=self.repo_root)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"当前项目概览读取失败:\n{exc}")
            self.write_log(f"当前项目概览读取失败: {exc}")
            return
        self.summary_text.set(format_project_summary(health))
        self.set_provider_summary(format_provider_summary(health))
        if not silent:
            self.write_log(format_health_log(health))

    def set_provider_summary(self, text: str) -> None:
        if not hasattr(self, "provider_body"):
            return
        try:
            self.provider_body.configure(state="normal")
            self.provider_body.delete("1.0", tk.END)
            self.provider_body.insert("1.0", text.rstrip() + "\n")
            self.provider_body.configure(state="disabled")
        except tk.TclError:
            return

    def summarize_project_context(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        try:
            preview = self.app.context_package_preview(project_id, include_text=True)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"生成上下文预览失败:\n{exc}")
            self.write_log(f"生成上下文预览失败: {exc}")
            return
        self.write_log(f"查看生成时会带的上下文: project={project_id}")
        self.show_text_window(
            "生成时会携带的上下文",
            format_context_package_preview(preview),
            actions=(("打开记忆库", self.show_memory_bank), ("打开大纲与章节", self.show_planning_library)),
            refresh=lambda: format_context_package_preview(
                self.app.context_package_preview(project_id, include_text=True)
            ),
        )

    def run_prepublish_check(self) -> None:
        try:
            result = self.app.prepublish_check(repo_root=self.repo_root)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"开发者诊断失败:\n{exc}")
            self.write_log(f"开发者诊断失败: {exc}")
            return
        summary = result.get("summary", {})
        self.write_log(
            "开发者诊断: "
            f"ok={result.get('ok')} "
            f"blocker={summary.get('blocker_count')} "
            f"warning={summary.get('warning_count')} "
            f"finding={summary.get('finding_count')}"
        )
        self.show_text_window(
            "开发者诊断",
            format_diagnostic_details(result),
            refresh=self.format_prepublish_diagnostics,
        )
        if result.get("ok") and int(summary.get("warning_count") or 0) == 0:
            messagebox.showinfo(APP_TITLE, "开发者诊断通过：0 blocker / 0 warning。")
        else:
            messagebox.showwarning(APP_TITLE, "开发者诊断存在发现项，详情已打开。")

    def format_prepublish_diagnostics(self) -> str:
        try:
            return format_diagnostic_details(self.app.prepublish_check(repo_root=self.repo_root))
        except Exception as exc:
            return f"开发者诊断失败:\n{exc}"

    def show_chapter_list(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records(
            "章节列表",
            lambda: [
                (
                    "章节",
                    visible_chapter_record_rows(
                        self.app.list_chapters(project_id),
                        self.app.list_drafts(project_id),
                        self.app.list_confirmed_chapters(project_id),
                    ),
                    ("chapter_id", "title", "status", "planned_at", "updated_at"),
                )
            ],
        )

    def show_generate_draft_dialog(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        settings = self.app.generation_settings(project_id)
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        sampling = settings.get("sampling") if isinstance(settings.get("sampling"), dict) else {}
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
        dialog = tk.Toplevel(self)
        dialog.title("生成草稿")
        dialog.transient(self)
        dialog.geometry("620x460")
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(3, weight=1)

        try:
            chapter_var = tk.StringVar(value=suggest_next_chapter_id(self.app.list_chapters(project_id)))
        except Exception:
            chapter_var = tk.StringVar(value="chapter_001")
        title_var = tk.StringVar(value="")
        ttk.Label(dialog, text="章节 ID").grid(row=0, column=0, sticky="e", padx=(18, 10), pady=(18, 8))
        ttk.Entry(dialog, textvariable=chapter_var, width=44).grid(row=0, column=1, sticky="ew", padx=(0, 18), pady=(18, 8))
        ttk.Label(dialog, text="章节标题").grid(row=1, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=title_var, width=44).grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=8)
        ttk.Label(dialog, text="本次要求").grid(row=2, column=0, sticky="ne", padx=(18, 10), pady=8)
        prompt_box = tk.Text(dialog, height=12, wrap="word")
        prompt_box.grid(row=2, column=1, rowspan=2, sticky="nsew", padx=(0, 18), pady=8)
        prompt_box.insert("1.0", str(prompting.get("default_user_prompt") or ""))
        status_var = tk.StringVar(
            value="生成前会按当前创作设置拼装提示词和资料；保存设置不会联网，点击生成草稿会调用当前模型服务。"
        )
        note = ttk.Label(
            dialog,
            textvariable=status_var,
            wraplength=560,
            justify="left",
        )
        note.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 12))
        button_row = ttk.Frame(dialog)
        button_row.grid(row=5, column=0, columnspan=2, sticky="e", padx=18, pady=(0, 18))
        generating = {"active": False}

        def set_generating(active: bool) -> None:
            generating["active"] = active
            state = "disabled" if active else "normal"
            generate_button.configure(state=state)
            preview_button.configure(state=state)
            cancel_button.configure(state=state)
            dialog.title("生成草稿（请求中）" if active else "生成草稿")
            if active:
                status_var.set("正在发送请求并等待模型返回；窗口不会卡死，请不要重复点击。")
            else:
                status_var.set("生成前会按当前创作设置拼装提示词和资料；保存设置不会联网，点击生成草稿会调用当前模型服务。")

        def close_dialog() -> None:
            if generating["active"]:
                messagebox.showinfo(APP_TITLE, "正在生成草稿，请等待模型返回后再关闭。", parent=dialog)
                return
            dialog.destroy()

        def generate() -> None:
            chapter_id = chapter_var.get().strip()
            prompt = prompt_box.get("1.0", tk.END).strip()
            if not chapter_id:
                messagebox.showerror(APP_TITLE, "章节 ID 不能为空。", parent=dialog)
                return
            if not prompt:
                messagebox.showerror(APP_TITLE, "提示词不能为空。", parent=dialog)
                return
            request = {
                "chapter_id": chapter_id,
                "title": title_var.get().strip(),
                "prompt": prompt,
                "system_prompt": str(prompting.get("system_prompt") or ""),
                "temperature": optional_float(sampling.get("temperature")),
                "top_p": optional_float(sampling.get("top_p")),
                "top_k": optional_int(sampling.get("top_k")),
                "min_p": optional_float(sampling.get("min_p")),
                "max_tokens": optional_int(sampling.get("max_tokens")),
                "presence_penalty": optional_float(sampling.get("presence_penalty")),
                "frequency_penalty": optional_float(sampling.get("frequency_penalty")),
                "repetition_penalty": optional_float(sampling.get("repetition_penalty")),
                "stream": optional_bool(sampling.get("stream")),
                "max_context_tokens": optional_int(context_settings.get("max_context_tokens")),
                "metadata": {"ui_action": "desktop_generate_draft"},
            }
            set_generating(True)
            self.start_live_draft_generation(project_id, chapter_id, request["title"] or chapter_id)
            self.write_log(f"生成草稿请求已发送: project={project_id} chapter={chapter_id}")
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

            def stream_callback(chunk: str) -> None:
                self.after(0, lambda chunk=chunk: self.append_live_draft_chunk(project_id, chapter_id, chunk))

            def reasoning_callback(chunk: str) -> None:
                self.after(0, lambda chunk=chunk: self.append_live_reasoning_chunk(project_id, chapter_id, chunk))

            def worker() -> None:
                try:
                    result = self.app.generate_context_draft(
                        project_id,
                        **request,
                        stream_callback=stream_callback,
                        reasoning_callback=reasoning_callback,
                    )
                except Exception as exc:
                    self.after(0, lambda exc=exc: finish(error=exc))
                    return
                self.after(0, lambda result=result: finish(result=result))

            def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
                if error is not None:
                    self.finish_live_draft_generation(project_id, chapter_id, error=error)
                    messagebox.showerror(APP_TITLE, f"生成草稿失败:\n{error}")
                    self.write_log(f"生成草稿失败: {error}")
                    return
                result = result or {}
                self.write_log(f"生成草稿成功: draft_id={result.get('draft_id')} chapter={chapter_id}")
                self.finish_live_draft_generation(project_id, chapter_id)
                self.run_project_health(silent=True)
                self.show_draft_workspace(project_id, str(result.get("draft_id") or ""))

            threading.Thread(target=worker, name="NovelDraftGeneration", daemon=True).start()

        def preview() -> None:
            prompt = prompt_box.get("1.0", tk.END).strip()
            if not prompt:
                messagebox.showerror(APP_TITLE, "提示词不能为空。", parent=dialog)
                return
            try:
                render = self.app.prompt_render_dry_run(
                    project_id,
                    chapter_id=chapter_var.get().strip(),
                    prompt=prompt,
                    system_prompt=str(prompting.get("system_prompt") or ""),
                    max_context_tokens=optional_int(context_settings.get("max_context_tokens")),
                    include_prompt_text=True,
                    include_context_text=False,
                )
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"预览失败:\n{exc}", parent=dialog)
                return
            self.show_text_window("将发送给模型的结构预览", format_prompt_preview(render), parent=dialog)

        cancel_button = ttk.Button(button_row, text="取消", command=close_dialog)
        cancel_button.pack(side="right", padx=(8, 0))
        generate_button = ttk.Button(button_row, text="生成草稿", command=generate)
        generate_button.pack(side="right")
        preview_button = ttk.Button(button_row, text="预览格式", command=preview)
        preview_button.pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.grab_set()
        dialog.wait_window()

    def start_live_draft_generation(self, project_id: str, chapter_id: str, title: str) -> None:
        self.reset_thinking_stream_window()
        self.live_generation_key = (project_id, chapter_id)
        self.thinking_closed_generation_key = None
        self.current_draft_project_id = ""
        self.current_draft_ids = []
        self.current_draft_index = -1
        self.current_draft_loading = True
        self.draft_meta_var.set(f"{project_id} / {chapter_id}    正在生成草稿...")
        self.draft_hint_var.set(f"标题: {title or '-'}    模型返回会实时写入下方编辑区，完成保存后可直接修改。")
        self.draft_body.configure(state="normal")
        self.draft_body.delete("1.0", tk.END)
        self.draft_body.insert("1.0", "")
        self.draft_body.edit_modified(False)
        self.draft_body.configure(state="disabled")
        self.current_draft_loading = False

    def reset_thinking_stream_window(self) -> None:
        if self.thinking_window is not None:
            try:
                if self.thinking_window.winfo_exists():
                    self.thinking_window.destroy()
            except tk.TclError:
                pass
        self.thinking_window = None
        self.thinking_body = None

    def thinking_stream_window_exists(self) -> bool:
        if self.thinking_window is None:
            return False
        try:
            return bool(self.thinking_window.winfo_exists())
        except tk.TclError:
            return False

    def show_thinking_stream_window(self, project_id: str, chapter_id: str) -> None:
        if self.thinking_stream_window_exists():
            return
        window = tk.Toplevel(self)
        window.title("模型 <think> 流式输出")
        window.geometry("560x340")
        window.minsize(420, 240)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(
            window,
            text=f"{project_id} / {chapter_id}    该内容不会写入正文草稿。",
            foreground="#6b7280",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))
        body = tk.Text(
            window,
            wrap="word",
            font=("Consolas", 10),
            foreground="#374151",
            background="#fffdf7",
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scrollbar.set)
        body.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 12))
        body.configure(state="disabled")

        def close() -> None:
            self.thinking_closed_generation_key = self.live_generation_key
            try:
                window.destroy()
            finally:
                self.thinking_window = None
                self.thinking_body = None

        window.protocol("WM_DELETE_WINDOW", close)
        self.thinking_window = window
        self.thinking_body = body

    def append_live_reasoning_chunk(self, project_id: str, chapter_id: str, chunk: str) -> None:
        generation_key = (project_id, chapter_id)
        if self.live_generation_key != generation_key or not chunk:
            return
        if self.thinking_closed_generation_key == generation_key:
            return
        self.show_thinking_stream_window(project_id, chapter_id)
        if self.thinking_body is None:
            return
        try:
            self.thinking_body.configure(state="normal")
            self.thinking_body.insert(tk.END, chunk)
            self.thinking_body.see(tk.END)
            self.thinking_body.configure(state="disabled")
        except tk.TclError:
            self.thinking_body = None

    def append_live_draft_chunk(self, project_id: str, chapter_id: str, chunk: str) -> None:
        if self.live_generation_key != (project_id, chapter_id) or not chunk:
            return
        self.current_draft_loading = True
        self.draft_body.configure(state="normal")
        self.draft_body.insert(tk.END, chunk)
        self.draft_body.see(tk.END)
        self.draft_body.edit_modified(False)
        self.draft_body.configure(state="disabled")
        self.current_draft_loading = False

    def finish_live_draft_generation(
        self,
        project_id: str,
        chapter_id: str,
        *,
        error: BaseException | None = None,
    ) -> None:
        if self.live_generation_key != (project_id, chapter_id):
            return
        self.live_generation_key = None
        if error is not None:
            self.draft_meta_var.set(f"{project_id} / {chapter_id}    生成失败，尚未保存为正式草稿。")
            self.draft_hint_var.set("当前窗口里如果已有部分返回内容，可手动复制保留。")
            self.draft_body.configure(state="normal")

    def show_chapter_browser(self, project_id: str, chapter_id: str) -> None:
        drafts = sorted_draft_versions(self.readable_draft_summaries(project_id, chapter_id=chapter_id))
        latest_draft_id = latest_chapter_draft_id(drafts)
        if latest_draft_id:
            self.show_draft_workspace(project_id, latest_draft_id)
            return
        try:
            chapter = self.app.read_confirmed_chapter(project_id, chapter_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"打开章节失败:\n{exc}")
            return
        source_draft_id = str(chapter.get("source_draft_id") or "")
        if source_draft_id:
            self.show_draft_workspace(project_id, source_draft_id)
            return
        self.draft_meta_var.set(f"{project_id} / {chapter_id}")
        self.draft_hint_var.set("确认章节没有可追溯草稿，当前显示确认章节正文。")
        self.live_generation_key = None
        self.current_draft_project_id = project_id
        self.current_draft_ids = []
        self.current_draft_index = -1
        self.current_draft_loading = True
        self.draft_body.configure(state="normal")
        self.draft_body.delete("1.0", tk.END)
        self.draft_body.insert("1.0", str(chapter.get("content") or ""))
        self.draft_body.edit_modified(False)
        self.draft_body.configure(state="disabled")
        self.current_draft_loading = False

    def show_draft_workspace(self, project_id: str, draft_id: str) -> None:
        if not draft_id:
            return
        self.live_generation_key = None
        try:
            draft = self.app.read_draft(project_id, draft_id)
            chapter_id = str(draft.get("chapter_id") or "")
            versions = sorted_draft_versions(self.readable_draft_summaries(project_id, chapter_id=chapter_id))
        except Exception as exc:
            self.load_project_work_nodes(project_id)
            messagebox.showerror(APP_TITLE, f"打开稿件失败:\n{exc}")
            return
        draft_ids = [str(item.get("draft_id") or "") for item in versions if item.get("draft_id")]
        if draft_id not in draft_ids:
            draft_ids.append(draft_id)
        self.current_draft_project_id = project_id
        self.current_draft_ids = draft_ids
        self.current_draft_index = draft_ids.index(draft_id)
        version_label = str(draft.get("version_label") or draft_version_text(draft, self.current_draft_index))
        status = str(draft.get("status") or "")
        title = str(draft.get("title") or chapter_id)
        self.draft_meta_var.set(f"{project_id} / {chapter_id} / {version_label}")
        self.draft_hint_var.set(f"状态: {draft_status_label(status)}    标题: {title or '-'}    编辑会自动保存到当前项目文件夹。")
        self.current_draft_loading = True
        self.draft_body.configure(state="normal")
        self.draft_body.delete("1.0", tk.END)
        self.draft_body.insert("1.0", str(draft.get("content") or ""))
        self.draft_body.edit_modified(False)
        self.current_draft_loading = False
        self.write_log(f"打开稿件: project={project_id} draft_id={draft_id} {version_label}")

    def readable_draft_summaries(self, project_id: str, *, chapter_id: str = "") -> list[dict[str, Any]]:
        try:
            drafts = self.app.list_drafts(project_id)
        except Exception:
            return []
        readable: list[dict[str, Any]] = []
        missing_entries: list[dict[str, Any]] = []
        for item in drafts:
            item_chapter_id = str(item.get("chapter_id") or "")
            if chapter_id and item_chapter_id != chapter_id:
                continue
            draft_id = str(item.get("draft_id") or "")
            if not draft_id:
                continue
            try:
                draft = self.app.read_draft(project_id, draft_id)
            except Exception as exc:
                try:
                    check = self.app.verify_draft_index_entry(project_id, draft_id)
                except Exception:
                    check = {"draft_id": draft_id, "status": "unknown", "path": str(item.get("path") or "")}
                if check.get("status") == "missing_artifact":
                    missing_entries.append({**item, **check})
                stale_key = (project_id, draft_id)
                if stale_key not in self.hidden_stale_draft_ids:
                    self.hidden_stale_draft_ids.add(stale_key)
                    self.write_log(f"已隐藏缺失草稿索引: project={project_id} draft_id={draft_id} reason={exc}")
                continue
            readable.append({**item, **draft})
        self.prompt_missing_draft_index_cleanup(project_id, missing_entries)
        return readable

    def prompt_missing_draft_index_cleanup(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        candidates = [
            item
            for item in entries
            if (project_id, str(item.get("draft_id") or "")) not in self.prompted_stale_draft_ids
        ]
        if not candidates:
            return
        for item in candidates:
            draft_id = str(item.get("draft_id") or "")
            if draft_id:
                self.prompted_stale_draft_ids.add((project_id, draft_id))
        labels = [
            f"{item.get('chapter_id') or '-'} / {item.get('draft_id') or '-'}"
            for item in candidates[:5]
        ]
        extra = "" if len(candidates) <= 5 else f"\n...另有 {len(candidates) - 5} 条"
        should_remove = messagebox.askyesno(
            APP_TITLE,
            "检测到草稿索引指向的文件已经不存在。\n\n"
            "软件已二次确认：这些记录的草稿 JSON 文件缺失，因此不会显示到项目列表。\n"
            "是否只删除这些陈旧索引记录？不会删除任何草稿文件或确认章节。\n\n"
            + "\n".join(labels)
            + extra,
        )
        if not should_remove:
            self.write_log(f"保留陈旧草稿索引: project={project_id} count={len(candidates)}")
            return
        try:
            result = self.app.remove_missing_draft_index_entries(
                project_id,
                [str(item.get("draft_id") or "") for item in candidates],
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"清理陈旧索引失败:\n{exc}")
            self.write_log(f"清理陈旧索引失败: {exc}")
            return
        self.write_log(
            f"陈旧草稿索引已清理: project={project_id} "
            f"removed={len(result.get('removed') or [])} skipped={len(result.get('skipped') or [])}"
        )
        self.after(0, lambda: self.load_project_work_nodes(project_id))

    def show_previous_draft_version(self) -> None:
        if self.current_draft_index <= 0 or not self.current_draft_project_id:
            return
        self.save_current_draft_edit(silent=True)
        self.show_draft_workspace(self.current_draft_project_id, self.current_draft_ids[self.current_draft_index - 1])

    def show_next_draft_version(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index + 1 >= len(self.current_draft_ids):
            return
        self.save_current_draft_edit(silent=True)
        self.show_draft_workspace(self.current_draft_project_id, self.current_draft_ids[self.current_draft_index + 1])

    def on_draft_text_modified(self, event: object | None = None) -> None:
        if self.current_draft_loading:
            return
        if not self.draft_body.edit_modified():
            return
        self.draft_body.edit_modified(False)
        if not self.current_draft_project_id or self.current_draft_index < 0:
            return
        if self.current_draft_autosave_job is not None:
            self.after_cancel(self.current_draft_autosave_job)
        self.current_draft_autosave_job = self.after(900, lambda: self.save_current_draft_edit(silent=True))

    def save_current_draft_edit(self, *, silent: bool = False) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            return
        self.current_draft_autosave_job = None
        draft_id = self.current_draft_ids[self.current_draft_index]
        text = self.draft_body.get("1.0", tk.END).rstrip("\n")
        try:
            result = self.app.update_draft_content(self.current_draft_project_id, draft_id, text=text)
        except Exception as exc:
            if not silent:
                messagebox.showerror(APP_TITLE, f"保存编辑失败:\n{exc}")
            self.write_log(f"保存编辑失败: {exc}")
            return
        if not silent:
            messagebox.showinfo(APP_TITLE, "编辑已保存。")
        synced = str(result.get("synced_confirmed_chapter") or "")
        suffix = f" synced_confirmed={synced}" if synced else ""
        self.write_log(f"编辑已保存: draft_id={draft_id}{suffix}")

    def ai_review_current_draft(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            messagebox.showinfo(APP_TITLE, "请先打开一个草稿。")
            return
        project_id = self.current_draft_project_id
        draft_id = self.current_draft_ids[self.current_draft_index]
        self.save_current_draft_edit(silent=True)
        try:
            existing = self.app.find_ai_review_for_draft(project_id, draft_id)
        except Exception:
            existing = None
        if existing is not None:
            self.write_log(
                f"打开已有 AI 审稿: project={project_id} draft_id={draft_id} "
                f"review_id={existing.get('review_id')}"
            )
            self.show_review_window(project_id, existing)
            return
        self.start_ai_review_request(project_id, draft_id)

    def start_ai_review_request(
        self,
        project_id: str,
        draft_id: str,
        *,
        extra_instruction: str = "",
        parent: tk.Misc | None = None,
    ) -> None:
        try:
            settings = self.app.generation_settings(project_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"读取创作设置失败:\n{exc}", parent=parent or self)
            return
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
        self.write_log(
            f"AI审稿请求已发送: project={project_id} draft_id={draft_id} "
            f"extra_instruction_chars={len(str(extra_instruction or '').strip())}"
        )
        review_window, review_body = self.show_live_text_window(
            f"AI审稿意见 - {draft_id}",
            f"{project_id} / {draft_id}    AI 审稿流式返回中...\n\n",
            parent=parent,
        )
        self.reset_thinking_stream_window()
        self.live_generation_key = (project_id, draft_id)
        self.thinking_closed_generation_key = None
        streamed_review = {"seen": False}

        def stream_callback(chunk: str) -> None:
            streamed_review["seen"] = True
            self.after(0, lambda chunk=chunk: self.append_text_window_chunk(review_body, chunk))

        def reasoning_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: self.append_live_reasoning_chunk(project_id, draft_id, chunk))

        def worker() -> None:
            try:
                result = self.app.ai_review_draft(
                    project_id,
                    draft_id,
                    max_context_tokens=optional_int(context_settings.get("max_context_tokens")),
                    stream=True,
                    stream_callback=stream_callback,
                    reasoning_callback=reasoning_callback,
                    extra_instruction=extra_instruction,
                )
                review = self.app.read_review(project_id, str(result.get("review_id") or ""))
            except Exception as exc:
                self.after(0, lambda exc=exc: finish(error=exc))
                return
            self.after(0, lambda result=result, review=review: finish(result=result, review=review))

        def finish(
            *,
            result: dict[str, Any] | None = None,
            review: dict[str, Any] | None = None,
            error: BaseException | None = None,
        ) -> None:
            if self.live_generation_key == (project_id, draft_id):
                self.live_generation_key = None
            if error is not None:
                self.append_text_window_chunk(review_body, f"\n\n[AI审稿失败]\n{error}\n")
                messagebox.showerror(APP_TITLE, f"AI审稿失败:\n{error}")
                self.write_log(f"AI审稿失败: {error}")
                return
            result = result or {}
            review = review or {}
            if not streamed_review["seen"]:
                self.append_text_window_chunk(review_body, str(review.get("comment") or "AI 审稿无可显示内容。"))
            self.append_text_window_chunk(
                review_body,
                f"\n\n[已保存到审稿意见汇总] review_id={result.get('review_id')} status={result.get('status')}\n",
            )
            self.write_log(
                f"AI审稿完成: project={project_id} draft_id={draft_id} "
                f"review_id={result.get('review_id')} status={result.get('status')}"
            )
            self.run_project_health(silent=True)
            self.load_project_work_nodes(project_id)
            self.add_text_window_action(
                review_window,
                "让AI再审一遍",
                lambda: self.prompt_ai_review_rerun(project_id, draft_id, parent=review_window),
            )
            try:
                review_window.lift()
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="NovelAIReview", daemon=True).start()

    def review_current_draft(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            messagebox.showinfo(APP_TITLE, "请先打开一个草稿。")
            return
        project_id = self.current_draft_project_id
        draft_id = self.current_draft_ids[self.current_draft_index]
        self.save_current_draft_edit(silent=True)
        try:
            existing = self.app.find_review_for_draft(project_id, draft_id)
        except Exception:
            existing = None
        if existing is not None:
            self.write_log(
                f"打开已有本地初审/确认记录: project={project_id} draft_id={draft_id} "
                f"review_id={existing.get('review_id')}"
            )
            self.show_review_window(project_id, existing)
            return
        try:
            result = self.app.review_draft(project_id, draft_id)
            review = self.app.read_review(project_id, str(result.get("review_id") or ""))
        except Exception as exc:
            if "already has a review" in str(exc):
                try:
                    existing = self.app.find_review_for_draft(project_id, draft_id)
                except Exception:
                    existing = None
                if existing is not None:
                    self.show_review_window(project_id, existing)
                    return
            messagebox.showerror(APP_TITLE, f"本地初审失败:\n{exc}")
            self.write_log(f"本地初审失败: {exc}")
            return
        self.write_log(
            f"本地初审完成: project={project_id} draft_id={draft_id} "
            f"review_id={result.get('review_id')} status={result.get('status')}"
        )
        self.run_project_health(silent=True)
        self.load_project_work_nodes(project_id)
        self.show_review_window(project_id, review)

    def show_review_window(self, project_id: str, review: dict[str, Any]) -> None:
        review_id = str(review.get("review_id") or "")
        title = f"审稿意见 - {review.get('chapter_id') or '-'}"
        draft_id = str(review.get("draft_id") or "")
        actions: tuple[tuple[str, Callable[[], None]], ...] = ()
        if str(review.get("review_type") or "") == "ai" and draft_id:
            actions = (("让AI再审一遍", lambda: self.prompt_ai_review_rerun(project_id, draft_id, parent=self)),)
        self.show_text_window(title, format_review_details(project_id, review), actions=actions, parent=self)

    def review_draft_by_id(self, project_id: str, draft_id: str) -> None:
        self.show_draft_workspace(project_id, draft_id)
        self.review_current_draft()

    def ai_review_draft_by_id(self, project_id: str, draft_id: str) -> None:
        self.show_draft_workspace(project_id, draft_id)
        self.ai_review_current_draft()

    def confirm_draft_by_id(self, project_id: str, draft_id: str) -> None:
        self.show_draft_workspace(project_id, draft_id)
        self.confirm_current_draft()

    def rewrite_draft_by_id(self, project_id: str, draft_id: str) -> None:
        self.show_draft_workspace(project_id, draft_id)
        self.rewrite_current_draft()

    def refine_draft_by_id(self, project_id: str, draft_id: str) -> None:
        self.show_draft_workspace(project_id, draft_id)
        self.refine_current_draft_from_ai_review()

    def confirm_current_draft(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            messagebox.showinfo(APP_TITLE, "请先打开一个草稿。")
            return
        project_id = self.current_draft_project_id
        draft_id = self.current_draft_ids[self.current_draft_index]
        self.save_current_draft_edit(silent=True)
        try:
            draft = self.app.read_draft(project_id, draft_id)
            if str(draft.get("status") or "") == "committed":
                messagebox.showinfo(APP_TITLE, "这个版本已经是确认稿。")
                return
            self.app.accept_draft_manually(project_id, draft_id, reason_code="desktop_confirm")
            result = self.app.commit_draft(project_id, draft_id, replace_existing=True)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"确认稿件失败:\n{exc}")
            self.write_log(f"确认稿件失败: {exc}")
            return
        chapter_id = str(result.get("chapter_id") or "")
        if chapter_id:
            self.load_confirmed_chapter_nodes(project_id)
            node_id = project_node_id(project_id)
            if self.project_tree.exists(node_id):
                self.project_tree.item(node_id, open=True)
        self.write_log(f"确认稿件: project={project_id} chapter={chapter_id} draft_id={draft_id}")
        self.run_project_health(silent=True)
        self.show_draft_workspace(project_id, draft_id)

    def rewrite_current_draft(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            messagebox.showinfo(APP_TITLE, "请先打开一个草稿。")
            return
        project_id = self.current_draft_project_id
        draft_id = self.current_draft_ids[self.current_draft_index]
        self.save_current_draft_edit(silent=True)
        try:
            draft = self.app.read_draft(project_id, draft_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"读取当前稿件失败:\n{exc}")
            return
        instruction = simpledialog.askstring(APP_TITLE, "重写要求（可留空）:")
        if instruction is None:
            return
        settings = self.app.generation_settings(project_id)
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        sampling = settings.get("sampling") if isinstance(settings.get("sampling"), dict) else {}
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
        chapter_id = str(draft.get("chapter_id") or "")
        source_text = self.draft_body.get("1.0", tk.END).strip()
        prompt = "\n\n".join(
            [
                "请重写当前章节，生成一个新的版本；不要覆盖上一版。",
                f"重写要求：{instruction.strip() or '保持剧情含义，优化节奏、细节和表达。'}",
                "【上一版稿件】",
                source_text,
            ]
        )
        request = {
            "chapter_id": chapter_id,
            "title": str(draft.get("title") or ""),
            "prompt": prompt,
            "system_prompt": str(prompting.get("system_prompt") or ""),
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
            "metadata": {"ui_action": "desktop_rewrite_draft", "source_draft_id": draft_id},
        }
        self.start_live_draft_generation(project_id, chapter_id, request["title"] or chapter_id)
        self.write_log(f"重写请求已发送: project={project_id} source={draft_id} chapter={chapter_id}")

        def stream_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: self.append_live_draft_chunk(project_id, chapter_id, chunk))

        def reasoning_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: self.append_live_reasoning_chunk(project_id, chapter_id, chunk))

        def worker() -> None:
            try:
                result = self.app.generate_context_draft(
                    project_id,
                    **request,
                    stream_callback=stream_callback,
                    reasoning_callback=reasoning_callback,
                )
            except Exception as exc:
                self.after(0, lambda exc=exc: finish(error=exc))
                return
            self.after(0, lambda result=result: finish(result=result))

        def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
            if error is not None:
                self.finish_live_draft_generation(project_id, chapter_id, error=error)
                messagebox.showerror(APP_TITLE, f"重写失败:\n{error}")
                self.write_log(f"重写失败: {error}")
                return
            result = result or {}
            new_draft_id = str(result.get("draft_id") or "")
            self.finish_live_draft_generation(project_id, chapter_id)
            self.write_log(f"重写生成新版本: project={project_id} source={draft_id} new={new_draft_id}")
            self.run_project_health(silent=True)
            self.load_project_work_nodes(project_id)
            self.show_draft_workspace(project_id, new_draft_id)

        threading.Thread(target=worker, name="NovelDraftRewrite", daemon=True).start()

    def refine_current_draft_from_ai_review(self) -> None:
        if not self.current_draft_project_id or self.current_draft_index < 0:
            messagebox.showinfo(APP_TITLE, "请先打开一个草稿。")
            return
        project_id = self.current_draft_project_id
        draft_id = self.current_draft_ids[self.current_draft_index]
        self.save_current_draft_edit(silent=True)
        try:
            ai_review = self.app.find_ai_review_for_draft(project_id, draft_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"读取 AI 审稿失败:\n{exc}")
            return
        if ai_review is None:
            messagebox.showinfo(APP_TITLE, "当前草稿还没有 AI 审稿，不能根据审稿精修。")
            return
        instruction = simpledialog.askstring(APP_TITLE, "根据审稿精修要求（可留空）:")
        if instruction is None:
            return
        try:
            settings = self.app.generation_settings(project_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"读取创作设置失败:\n{exc}")
            return
        sampling = settings.get("sampling") if isinstance(settings.get("sampling"), dict) else {}
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
        review_id = str(ai_review.get("review_id") or "")
        self.write_log(
            f"AI精修请求已发送: project={project_id} draft_id={draft_id} review_id={review_id}"
        )
        chapter_id = str(self.app.read_draft(project_id, draft_id).get("chapter_id") or "")
        self.start_live_draft_generation(project_id, chapter_id, f"AI精修 {chapter_id}")

        def stream_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: self.append_live_draft_chunk(project_id, chapter_id, chunk))

        def reasoning_callback(chunk: str) -> None:
            self.after(0, lambda chunk=chunk: self.append_live_reasoning_chunk(project_id, chapter_id, chunk))

        def worker() -> None:
            try:
                result = self.app.refine_draft_from_ai_review(
                    project_id,
                    draft_id,
                    review_id=review_id,
                    instruction=instruction,
                    temperature=optional_float(sampling.get("temperature")),
                    top_p=optional_float(sampling.get("top_p")),
                    top_k=optional_int(sampling.get("top_k")),
                    min_p=optional_float(sampling.get("min_p")),
                    max_tokens=optional_int(sampling.get("max_tokens")),
                    presence_penalty=optional_float(sampling.get("presence_penalty")),
                    frequency_penalty=optional_float(sampling.get("frequency_penalty")),
                    repetition_penalty=optional_float(sampling.get("repetition_penalty")),
                    max_context_tokens=optional_int(context_settings.get("max_context_tokens")),
                    stream=True,
                    stream_callback=stream_callback,
                    reasoning_callback=reasoning_callback,
                )
            except Exception as exc:
                self.after(0, lambda exc=exc: finish(error=exc))
                return
            self.after(0, lambda result=result: finish(result=result))

        def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
            if error is not None:
                self.finish_live_draft_generation(project_id, chapter_id, error=error)
                messagebox.showerror(APP_TITLE, f"根据审稿精修失败:\n{error}")
                self.write_log(f"根据审稿精修失败: {error}")
                return
            result = result or {}
            new_draft_id = str(result.get("draft_id") or "")
            self.finish_live_draft_generation(project_id, chapter_id)
            self.write_log(
                f"AI精修生成新版本: project={project_id} source={draft_id} "
                f"review={review_id} new={new_draft_id}"
            )
            self.run_project_health(silent=True)
            self.load_project_work_nodes(project_id)
            self.show_draft_workspace(project_id, new_draft_id)

        threading.Thread(target=worker, name="NovelAIRefinement", daemon=True).start()

    def show_review_rewrite(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records(
            "审稿与改写",
            lambda: [
                ("草稿", self.app.list_drafts(project_id), ("draft_id", "chapter_id", "status", "provider", "created_at")),
                (
                    "审稿记录",
                    self.app.list_reviews(project_id),
                    ("review_id", "review_type", "draft_id", "decision", "reason_code", "created_at"),
                ),
                ("改写请求", self.app.list_revision_requests(project_id), ("revision_request_id", "review_id", "status", "created_at")),
                ("人工改写任务", self.app.list_manual_rewrite_tasks(project_id), ("task_id", "status", "draft_id", "created_at")),
            ],
        )

    def show_confirmed_chapters(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_text_window(
            "确认章节",
            self.format_confirmed_chapters(project_id),
            actions=(("导出TXT文稿", lambda: self.export_txt_dialog(project_id)),),
            refresh=lambda: self.format_confirmed_chapters(project_id),
        )

    def export_txt_dialog(self, project_id: str | None = None) -> None:
        project_id = project_id or self.require_project()
        if not project_id:
            return
        chapters = self.app.list_confirmed_chapters(project_id)
        if not chapters:
            messagebox.showinfo(APP_TITLE, "当前作品还没有已确认章节，不能导出 TXT。")
            return
        default_name = self.default_txt_export_filename(project_id)
        output_path = filedialog.asksaveasfilename(
            title="导出TXT文稿",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=(("TXT 文稿", "*.txt"), ("所有文件", "*.*")),
        )
        if not output_path:
            return
        try:
            result = self.app.export_confirmed_chapters_txt(project_id, output_path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"导出 TXT 失败：\n{exc}")
            return
        self.write_log(
            f"导出TXT文稿: project={project_id} chapters={result.get('chapter_count')} path={result.get('path')}"
        )
        messagebox.showinfo(
            APP_TITLE,
            "\n".join(
                [
                    "TXT 文稿已导出。",
                    f"章节数：{result.get('chapter_count')}",
                    f"编码：{result.get('encoding')}",
                    f"文件：{result.get('path')}",
                ]
            ),
        )

    def default_txt_export_filename(self, project_id: str) -> str:
        title = project_id
        for project in self.app.list_projects():
            if str(project.get("project_id") or "") == project_id:
                title = str(project.get("title") or project_id)
                break
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", title).strip(" ._")
        return f"{safe or project_id}.txt"

    def show_planning_library(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_outline_chapter_plan_window(project_id)

    def show_outline_chapter_plan_window(self, project_id: str) -> None:
        window = tk.Toplevel(self)
        window.title("大纲与章节")
        window.transient(self)
        window.geometry("960x620")
        window.columnconfigure(1, weight=1)
        window.rowconfigure(1, weight=1)

        ttk.Label(
            window,
            text="这里只管理总纲和章节计划。章节计划可以按阶段拆成 01-05、06-10 等多条，左侧选择后在右侧读取、修改和保存。",
            foreground="#6b7280",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 8))

        list_frame = ttk.Frame(window)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(14, 8), pady=8)
        list_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)
        ttk.Label(list_frame, text="阶段资料").grid(row=0, column=0, sticky="w", pady=(0, 6))
        plan_tree = ttk.Treeview(list_frame, show="tree", selectmode="browse", height=20)
        plan_tree.grid(row=1, column=0, sticky="nsew")

        editor = ttk.Frame(window)
        editor.grid(row=1, column=1, sticky="nsew", padx=(8, 14), pady=8)
        editor.columnconfigure(1, weight=1)
        editor.rowconfigure(5, weight=1)

        type_var = tk.StringVar(value=label_for_value(PLANNING_TYPE_OPTIONS, "outline"))
        title_var = tk.StringVar(value="")
        id_var = tk.StringVar(value="")
        range_var = tk.StringVar(value="")
        include_context_var = tk.BooleanVar(value=True)
        adherence_labels = [label for _, label in PLANNING_ADHERENCE_OPTIONS]
        adherence_var = tk.StringVar(value=label_for_value(PLANNING_ADHERENCE_OPTIONS, "balanced"))
        current_item: dict[str, Any] = {}
        current_mode = {"creating": False}

        ttk.Label(editor, text="资料类型").grid(row=0, column=0, sticky="e", padx=(0, 10), pady=(0, 8))
        type_box = ttk.Combobox(
            editor,
            textvariable=type_var,
            values=[
                label_for_value(PLANNING_TYPE_OPTIONS, "outline"),
                label_for_value(PLANNING_TYPE_OPTIONS, "chapter_plan"),
            ],
            state="disabled",
        )
        type_box.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        ttk.Label(editor, text="标题").grid(row=1, column=0, sticky="e", padx=(0, 10), pady=8)
        ttk.Entry(editor, textvariable=title_var).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Label(editor, text="内部编号").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=8)
        ttk.Entry(editor, textvariable=id_var, state="readonly").grid(row=2, column=1, sticky="ew", pady=8)
        ttk.Label(editor, text="章节范围").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=8)
        ttk.Entry(editor, textvariable=range_var).grid(row=3, column=1, sticky="ew", pady=8)
        ttk.Label(editor, text="参考强度").grid(row=4, column=0, sticky="e", padx=(0, 10), pady=8)
        adherence_box = ttk.Combobox(editor, textvariable=adherence_var, values=adherence_labels, state="readonly")
        adherence_box.grid(row=4, column=1, sticky="ew", pady=8)

        content_box = tk.Text(editor, wrap="word", height=18)
        content_box.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(8, 8))
        ttk.Checkbutton(editor, text="加入生成上下文", variable=include_context_var).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        def item_label(item: dict[str, Any]) -> str:
            item_type = str(item.get("item_type") or "")
            prefix = "☑" if item.get("enabled") is not False and bool(item.get("active")) else "☐"
            type_label = label_for_value(PLANNING_TYPE_OPTIONS, item_type)
            title = str(item.get("title") or item.get("planning_id") or "")
            chapter_range = str(item.get("chapter_range") or "").strip()
            range_text = f" {chapter_range}" if chapter_range else ""
            return f"{prefix} {type_label}{range_text}  {title}".strip()

        def readable_items() -> list[dict[str, Any]]:
            return [
                item
                for item in self.app.list_planning_items(project_id, include_text=True)
                if str(item.get("item_type") or "") in {"outline", "chapter_plan"}
            ]

        def clear_editor(*, item_type: str) -> None:
            current_item.clear()
            current_mode["creating"] = True
            type_var.set(label_for_value(PLANNING_TYPE_OPTIONS, item_type))
            title_var.set("")
            id_var.set(default_planning_id(item_type))
            range_var.set("")
            include_context_var.set(True)
            adherence_var.set(label_for_value(PLANNING_ADHERENCE_OPTIONS, "balanced"))
            content_box.delete("1.0", tk.END)

        def load_item(item: dict[str, Any]) -> None:
            current_item.clear()
            current_item.update(item)
            current_mode["creating"] = False
            item_type = str(item.get("item_type") or "outline")
            type_var.set(label_for_value(PLANNING_TYPE_OPTIONS, item_type))
            title_var.set(str(item.get("title") or ""))
            id_var.set(str(item.get("planning_id") or ""))
            range_var.set(str(item.get("chapter_range") or ""))
            include_context_var.set(item.get("enabled") is not False and bool(item.get("active")))
            adherence_var.set(label_for_value(PLANNING_ADHERENCE_OPTIONS, str(item.get("adherence_level") or "balanced")))
            content_box.delete("1.0", tk.END)
            content_box.insert("1.0", str(item.get("text") or ""))

        def refresh(select_id: str = "") -> None:
            existing_selection = select_id or str(current_item.get("memory_id") or "").strip()
            for child in plan_tree.get_children(""):
                plan_tree.delete(child)
            items = readable_items()
            for item in items:
                planning_id = str(item.get("planning_id") or "")
                if not planning_id:
                    continue
                plan_tree.insert("", "end", iid=f"plan:{planning_id}", text=item_label(item))
            target_id = f"plan:{existing_selection}" if existing_selection else ""
            if target_id and plan_tree.exists(target_id):
                plan_tree.selection_set(target_id)
                plan_tree.focus(target_id)
                selected = next((item for item in items if str(item.get("planning_id") or "") == existing_selection), {})
                if selected:
                    load_item(selected)
                return
            if items:
                first = str(items[0].get("planning_id") or "")
                if first and plan_tree.exists(f"plan:{first}"):
                    plan_tree.selection_set(f"plan:{first}")
                    plan_tree.focus(f"plan:{first}")
                    load_item(items[0])
            else:
                clear_editor(item_type="outline")

        def selected_planning_id() -> str:
            selection = plan_tree.selection()
            if not selection:
                return ""
            return str(selection[0]).removeprefix("plan:")

        def on_select(event: object | None = None) -> None:
            planning_id = selected_planning_id()
            if not planning_id:
                return
            try:
                load_item(self.app.read_planning_item(project_id, planning_id, include_text=True))
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"读取资料失败:\n{exc}", parent=window)

        def save_current() -> None:
            planning_id = id_var.get().strip()
            item_type = value_for_label(PLANNING_TYPE_OPTIONS, type_var.get())
            payload = {
                "text": content_box.get("1.0", tk.END).strip(),
                "title": title_var.get().strip(),
                "item_type": item_type,
                "active": include_context_var.get(),
                "enabled": include_context_var.get(),
                "adherence_level": value_for_label(PLANNING_ADHERENCE_OPTIONS, adherence_var.get()),
                "chapter_range": range_var.get().strip(),
            }
            try:
                if current_mode["creating"]:
                    result = self.app.create_planning_item(project_id, planning_id, **payload)
                else:
                    result = self.app.update_planning_item(project_id, planning_id, **payload)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"保存资料失败:\n{exc}", parent=window)
                return
            saved_id = str(result.get("planning_id") or planning_id)
            self.write_log(f"大纲与章节已保存: project={project_id} planning_id={saved_id}")
            refresh(saved_id)
            self.run_project_health(silent=True)

        def toggle_context() -> None:
            include_context_var.set(not include_context_var.get())
            if id_var.get().strip() and not current_mode["creating"]:
                save_current()

        def select_or_create_outline() -> None:
            outline = next((item for item in readable_items() if str(item.get("item_type") or "") == "outline"), {})
            planning_id = str(outline.get("planning_id") or "")
            if planning_id and plan_tree.exists(f"plan:{planning_id}"):
                plan_tree.selection_set(f"plan:{planning_id}")
                plan_tree.focus(f"plan:{planning_id}")
                load_item(outline)
                return
            clear_editor(item_type="outline")

        button_row = ttk.Frame(window)
        button_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))
        ttk.Button(button_row, text="新增章节计划", command=lambda: clear_editor(item_type="chapter_plan")).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="选择/编辑总纲", command=select_or_create_outline).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(button_row, text="切换加入上下文", command=toggle_context).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="刷新", command=refresh).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="保存当前", command=save_current).pack(side="right", padx=(8, 0))
        ttk.Button(button_row, text="关闭", command=window.destroy).pack(side="right")

        plan_tree.bind("<<TreeviewSelect>>", on_select)
        refresh()

    def show_world_materials(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_planning_records_window(
            project_id,
            "世界观与人物",
            section_title="人物、地点、势力与世界规则",
            item_types={"character_plan", "world_plan", "constraint"},
            actions=(
                ("新增角色", "character_plan"),
                ("编辑世界观", "world_plan"),
                ("新增约束", "constraint"),
            ),
        )

    def show_planning_records_window(
        self,
        project_id: str,
        title: str,
        *,
        section_title: str,
        item_types: set[str],
        actions: tuple[tuple[str, str], ...],
    ) -> None:
        def render() -> str:
            return format_planning_records(
                section_title,
                planning_display_rows(
                    self.app.list_planning_items(project_id, include_text=True),
                    item_types=item_types,
                ),
            )

        refs: dict[str, Any] = {}

        def refresh() -> None:
            body = refs.get("body")
            if isinstance(body, tk.Text):
                self.replace_text_window_content(body, render())
            self.refresh_projects()
            self.run_project_health(silent=True)

        def open_editor(item_type: str) -> Callable[[], None]:
            return lambda: self.create_planning_item_dialog(
                project_id,
                default_type=item_type,
                parent=refs.get("window") if isinstance(refs.get("window"), tk.Toplevel) else self,
                on_saved=refresh,
            )

        window, body = self.show_text_window(
            title,
            render(),
            actions=tuple((label, open_editor(item_type)) for label, item_type in actions),
            refresh=render,
        )
        refs["window"] = window
        refs["body"] = body

    def show_memory_bank(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_memory_bank_window(project_id)

    def show_memory_bank_window(self, project_id: str) -> None:
        window = tk.Toplevel(self)
        window.title("记忆银行")
        window.transient(self)
        window.geometry("1080x700")
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
        chapter_tree = ttk.Treeview(list_frame, show="tree", selectmode="none", height=20)
        chapter_tree.grid(row=2, column=0, sticky="nsew")

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
        text_box = tk.Text(editor, wrap="word", height=22)
        text_box.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        ttk.Label(editor, textvariable=api_status_var, foreground="#6b7280", wraplength=680).grid(
            row=8, column=0, columnspan=2, sticky="ew"
        )

        def chapter_label(chapter: dict[str, Any]) -> str:
            chapter_id = str(chapter.get("chapter_id") or "")
            title = str(chapter.get("title") or "").strip()
            committed_at = str(chapter.get("committed_at") or "").strip()
            prefix = "✓" if chapter_id in checked_chapter_ids else "□"
            parts = [prefix, readable_chapter_label(chapter_id)]
            if title:
                parts.append(title)
            if committed_at:
                parts.append(committed_at[:8])
            return "  ".join(parts)

        def checked_ids_in_order() -> list[str]:
            return [
                str(chapter.get("chapter_id") or "")
                for chapter in confirmed_chapters
                if str(chapter.get("chapter_id") or "") in checked_chapter_ids
            ]

        def checked_label() -> str:
            ids = checked_ids_in_order()
            if not ids:
                return "尚未勾选章节"
            labels = [readable_chapter_label(chapter_id) for chapter_id in ids]
            if len(labels) <= 5:
                return "、".join(labels)
            return "、".join(labels[:5]) + f" 等 {len(labels)} 章"

        def current_target_tokens(*, normalize_entry: bool = False) -> int:
            target_tokens = normalize_memory_target_tokens(token_target_var.get())
            if normalize_entry:
                token_target_var.set(str(target_tokens))
            return target_tokens

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
            try:
                item = self.app.ensure_main_memory_item(project_id)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"读取记忆银行失败:\n{exc}", parent=window)
                return
            current_memory_item.clear()
            current_memory_item.update(item)
            include_context_var.set(item.get("enabled") is not False)
            token_target_var.set(str(normalize_memory_target_tokens(item.get("target_token_budget"))))
            text_box.delete("1.0", tk.END)
            text_box.insert("1.0", str(item.get("text") or ""))
            refresh_chapters(select_chapter_id)

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
                chapters = selected_confirmed_chapters()
            except Exception as exc:
                messagebox.showinfo(APP_TITLE, str(exc), parent=window)
                return
            prompt = format_memory_update_prompt(
                current_memory=text_box.get("1.0", tk.END).strip(),
                chapters=chapters,
                target_tokens=current_target_tokens(normalize_entry=True),
            )
            self.show_text_window(
                "记忆银行更新提示词预览",
                prompt,
                parent=window,
                refresh=lambda: format_memory_update_prompt(
                    current_memory=text_box.get("1.0", tk.END).strip(),
                    chapters=selected_confirmed_chapters(),
                    target_tokens=current_target_tokens(normalize_entry=True),
                ),
            )

        def set_api_generating(active: bool) -> None:
            api_generating["active"] = active
            state = "disabled" if active else "normal"
            for button in (api_generate_button, api_preview_button, update_prompt_button, compression_prompt_button):
                button.configure(state=state)
            if active:
                api_status_var.set("正在调用当前 writer 模型服务生成记忆正文；返回前请不要重复点击。")

        def show_memory_api_request_preview() -> None:
            try:
                preview = self.app.preview_memory_generation_request(
                    project_id,
                    current_memory=text_box.get("1.0", tk.END).strip(),
                    chapters=selected_confirmed_chapters(),
                    target_token_budget=current_target_tokens(normalize_entry=True),
                )
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"生成 API 发送结构失败:\n{exc}", parent=window)
                return
            self.show_text_window(
                "记忆银行 API 发送结构",
                format_memory_generation_request_preview(preview),
                parent=window,
                refresh=lambda: format_memory_generation_request_preview(
                    self.app.preview_memory_generation_request(
                        project_id,
                        current_memory=text_box.get("1.0", tk.END).strip(),
                        chapters=selected_confirmed_chapters(),
                        target_token_budget=current_target_tokens(normalize_entry=True),
                    )
                ),
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
            set_api_generating(True)
            self.write_log(f"记忆银行 API 生成请求已发送: project={project_id} chapters={len(chapters)}")

            def worker() -> None:
                try:
                    result = self.app.generate_memory_bank_text(
                        project_id,
                        current_memory=current_memory,
                        chapters=chapters,
                        target_token_budget=target_tokens,
                    )
                except Exception as exc:
                    self.after(0, lambda exc=exc: finish(error=exc))
                    return
                self.after(0, lambda result=result: finish(result=result))

            def finish(*, result: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
                set_api_generating(False)
                if error is not None:
                    api_status_var.set("AI 生成记忆失败。")
                    messagebox.showerror(APP_TITLE, f"AI 生成记忆失败:\n{error}", parent=window)
                    self.write_log(f"记忆银行 API 生成失败: {error}")
                    return
                result = result or {}
                generated_text = str(result.get("text") or "").strip()
                text_box.delete("1.0", tk.END)
                text_box.insert("1.0", generated_text)
                summary = result.get("request_summary") if isinstance(result.get("request_summary"), dict) else {}
                api_status_var.set(
                    "AI 已生成记忆正文，已填入右侧文本框；请检查后点击“保存记忆正文”。"
                    f" provider={result.get('provider') or '-'} model={result.get('model') or '-'}"
                    f" chars={len(generated_text)} prompt_chars={summary.get('prompt_chars') or '-'}"
                )
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

        ttk.Button(select_buttons, text="勾选建议章节", command=check_recommended_chapters).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(select_buttons, text="全选", command=check_all_chapters).pack(side="left", padx=(0, 6))
        ttk.Button(select_buttons, text="清空", command=clear_checked_chapters).pack(side="left")

        button_row = ttk.Frame(window)
        button_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))
        update_prompt_button = ttk.Button(button_row, text="生成更新记忆提示词", command=show_memory_update_prompt)
        update_prompt_button.pack(side="left", padx=(0, 8))
        api_preview_button = ttk.Button(button_row, text="查看API发送结构", command=show_memory_api_request_preview)
        api_preview_button.pack(side="left", padx=(0, 8))
        api_generate_button = ttk.Button(button_row, text="发送给AI生成记忆", command=generate_memory_via_api)
        api_generate_button.pack(side="left", padx=(0, 8))
        compression_prompt_button = ttk.Button(button_row, text="生成缩写提示词", command=show_memory_compression_prompt)
        compression_prompt_button.pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="查看生成时会带的上下文", command=show_context_preview).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="刷新窗口", command=refresh).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="保存加入上下文设置", command=save_lifecycle).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="保存记忆正文", command=save_text).pack(side="right", padx=(8, 0))
        ttk.Button(button_row, text="关闭", command=window.destroy).pack(side="right")

        refresh()

    def format_memory_bank(self, project_id: str) -> str:
        return format_memory_records(
            memory_display_rows(self.app.list_memory_items(project_id, include_text=True)),
            self.app.list_memory_apply_previews(project_id),
        )

    def format_confirmed_chapters(self, project_id: str) -> str:
        chapters = self.app.list_confirmed_chapters(project_id)
        lines = ["已确认章节", "----------"]
        if not chapters:
            lines.append("暂无记录。")
            return "\n".join(lines)
        for index, item in enumerate(chapters, start=1):
            chapter_id = str(item.get("chapter_id") or "")
            content = ""
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

    def show_corpus_style(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records(
            "参考作品与风格（开发中）",
            lambda: [
                (
                    "功能状态",
                    [
                        {
                            "status": "开发中",
                            "available": "可做本地 TXT/MD 参考作品统计、章节边界识别、从已确认章节建立本地风格基线。",
                            "not_ready": "尚未形成导入参考作品后自动影响生成、审稿、精修的正式闭环。",
                        }
                    ],
                    ("status", "available", "not_ready"),
                ),
                ("参考片段", self.app.list_corpus_samples(project_id), ("status", "source_label", "created_at")),
                ("章节结构", self.app.list_corpus_boundaries(project_id), ("status", "file_name", "chapter_count", "created_at")),
                ("风格分析", self.app.list_corpus_profiles(project_id), ("status", "created_at")),
                ("我的风格基线", self.app.list_self_style_baselines(project_id), ("status", "created_at")),
                ("风格检查", self.app.list_draft_style_checks(project_id), ("check_id", "draft_id", "status", "created_at")),
                ("风格建议", self.app.list_style_suggestions(project_id), ("suggestion_id", "status", "created_at")),
            ],
            actions=(
                ("分析参考作品", lambda: self.import_corpus_profile_dialog(project_id)),
                ("识别章节结构", lambda: self.import_corpus_boundaries_dialog(project_id)),
                ("从确认章节建立风格", lambda: self.create_style_baseline(project_id)),
            ),
        )

    def show_model_self_check(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records("连接检查", lambda: self.model_self_check_sections(project_id))

    def model_self_check_sections(self, project_id: str) -> list[tuple[str, list[dict[str, Any]], tuple[str, ...]]]:
        sections: list[tuple[str, list[dict[str, Any]], tuple[str, ...]]] = []
        for role, role_label in MODEL_ROLE_OPTIONS:
            try:
                status = self.app.provider_status(project_id, role)
            except Exception as exc:
                status = {"role": role, "message": str(exc), "ok": False}
            sections.append((role_label, [status], ("ok", "provider", "model", "has_api_key", "message")))
        return sections

    def show_generation_params(self) -> None:
        self.show_generation_settings_dialog(scope="global")

    def show_project_generation_settings_dialog(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_generation_settings_dialog(project_id=project_id, scope="project")

    def show_generation_settings_dialog(self, project_id: str = "", *, scope: str = "global") -> None:
        project_scope = scope == "project"
        if project_scope:
            state = self.app.project_generation_settings_state(project_id)
            settings = state["settings"]
            source_text = project_settings_source_text(state)
            title = f"项目专属创作设置 - {project_id}"
            explain_text = (
                "此处保存到当前项目文件夹。项目专属设置优先于全局设置；"
                "清除项目覆盖后，会自动套用全局默认。"
            )
            save_label = "保存项目设置"
            reset_label = "清除项目覆盖"
            save_path_text = f"保存位置：{state['project_config_path']}"
        else:
            settings = self.app.global_generation_settings()
            source_text = "当前编辑：全局默认设置"
            title = "全局创作设置"
            explain_text = (
                "此处仅控制全局默认设置，优先度低于项目专属设置。"
                "需要单独设置某本小说时，在左侧项目上点右键进入“项目专属设置”。"
            )
            save_label = "保存全局设置"
            reset_label = "恢复出厂默认"
            save_path_text = f"保存位置：{self.projects_root / 'global_settings.json'}"

        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.geometry("820x720")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)

        source_var = tk.StringVar(value=source_text)
        ttk.Label(
            dialog,
            textvariable=source_var,
            wraplength=760,
            foreground="#374151",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 2))
        ttk.Label(
            dialog,
            text=f"{explain_text}\n{save_path_text}",
            wraplength=760,
            foreground="#6b7280",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))

        notebook = ttk.Notebook(dialog)
        notebook.grid(row=2, column=0, sticky="nsew", padx=14, pady=8)
        prompt_tab = ttk.Frame(notebook)
        params_tab = ttk.Frame(notebook)
        review_tab = ttk.Frame(notebook)
        notebook.add(prompt_tab, text="提示词")
        notebook.add(params_tab, text="采样参数与上下文")
        notebook.add(review_tab, text="审稿")

        prompt_tab.columnconfigure(1, weight=1)
        prompt_tab.rowconfigure(1, weight=1)
        prompt_tab.rowconfigure(3, weight=1)
        ttk.Label(prompt_tab, text="系统提示词").grid(row=0, column=0, sticky="ne", padx=(14, 10), pady=(14, 6))
        system_box = tk.Text(prompt_tab, wrap="word", height=10)
        system_box.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 14), pady=(14, 8))
        ttk.Label(prompt_tab, text="默认写作要求").grid(row=2, column=0, sticky="ne", padx=(14, 10), pady=8)
        user_box = tk.Text(prompt_tab, wrap="word", height=8)
        user_box.grid(row=2, column=1, rowspan=2, sticky="nsew", padx=(0, 14), pady=8)

        params_tab.columnconfigure(1, weight=1)
        field_vars: dict[str, tk.StringVar] = {}
        row = 0
        for key, label in (
            ("temperature", "Temperature"),
            ("top_p", "Top P"),
            ("top_k", "Top K"),
            ("min_p", "Min P"),
            ("max_tokens", "Max Tokens"),
            ("presence_penalty", "Presence Penalty"),
            ("frequency_penalty", "Frequency Penalty"),
            ("repetition_penalty", "Repetition Penalty"),
            ("max_context_tokens", "上下文 Token 上限"),
            ("recent_confirmed_chapter_count", "自动带入前文章数"),
        ):
            ttk.Label(params_tab, text=label).grid(row=row, column=0, sticky="e", padx=(18, 10), pady=6)
            var = tk.StringVar(value="")
            ttk.Entry(params_tab, textvariable=var).grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=6)
            field_vars[key] = var
            row += 1
        stream_var = tk.BooleanVar(value=False)
        include_recent_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(params_tab, text="请求流式输出（仅在模型服务支持后生效）", variable=stream_var).grid(
            row=row, column=1, sticky="w", padx=(0, 18), pady=6
        )
        row += 1
        ttk.Checkbutton(params_tab, text="生成时带入前文片段", variable=include_recent_var).grid(
            row=row, column=1, sticky="w", padx=(0, 18), pady=6
        )
        row += 1
        ttk.Label(
            params_tab,
            text="Temperature、Top P、Top K、Min P 等只决定写作采样；API 地址和 Key 请在“模型服务”里设置。",
            wraplength=600,
            foreground="#6b7280",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 0))

        scorer_enabled_var = tk.BooleanVar(value=False)
        review_prompt_status_var = tk.StringVar(value="")
        review_tab.columnconfigure(0, weight=1)
        review_tab.rowconfigure(7, weight=1)
        ttk.Checkbutton(
            review_tab,
            text="启用评分模型辅助审稿（可选）",
            variable=scorer_enabled_var,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))
        ttk.Label(
            review_tab,
            text=(
                "关闭时，确认稿件和人工审稿不需要额外配置评分模型；"
                "开启后，“AI审稿”会调用“模型服务”里的 AI审稿 角色。"
            ),
            wraplength=720,
            foreground="#6b7280",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        ttk.Label(
            review_tab,
            text=(
                "这是当前设置范围内的审稿默认值；项目专属设置会优先于全局默认。"
                "下方文本会真实进入 AI 审稿请求，修改后点保存生效。"
            ),
            wraplength=720,
            foreground="#6b7280",
            justify="left",
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        ttk.Label(review_tab, text="审稿系统提示词").grid(row=3, column=0, sticky="w", padx=18, pady=(0, 4))
        review_system_frame = ttk.Frame(review_tab)
        review_system_frame.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))
        review_system_frame.columnconfigure(0, weight=1)
        review_system_box = tk.Text(review_system_frame, wrap="word", height=3, undo=True)
        review_system_scrollbar = ttk.Scrollbar(review_system_frame, orient="vertical", command=review_system_box.yview)
        review_system_box.configure(yscrollcommand=review_system_scrollbar.set)
        review_system_box.grid(row=0, column=0, sticky="ew")
        review_system_scrollbar.grid(row=0, column=1, sticky="ns")
        ttk.Label(
            review_tab,
            text="AI审稿提示词（可使用 {chapter_heading}、{chapter_id}、{title}）",
        ).grid(row=5, column=0, sticky="w", padx=18, pady=(0, 4))
        review_prompt_frame = ttk.Frame(review_tab)
        review_prompt_frame.grid(row=6, column=0, rowspan=2, sticky="nsew", padx=18, pady=(0, 8))
        review_prompt_frame.columnconfigure(0, weight=1)
        review_prompt_frame.rowconfigure(0, weight=1)
        review_prompt_box = tk.Text(review_prompt_frame, wrap="word", height=14, undo=True)
        review_prompt_scrollbar = ttk.Scrollbar(review_prompt_frame, orient="vertical", command=review_prompt_box.yview)
        review_prompt_box.configure(yscrollcommand=review_prompt_scrollbar.set)
        review_prompt_box.grid(row=0, column=0, sticky="nsew")
        review_prompt_scrollbar.grid(row=0, column=1, sticky="ns")
        ttk.Label(
            review_tab,
            textvariable=review_prompt_status_var,
            foreground="#6b7280",
        ).grid(row=8, column=0, sticky="w", padx=18, pady=(0, 8))

        def refresh_review_prompt_status(_event: object | None = None) -> None:
            system_chars = len(review_system_box.get("1.0", tk.END).strip())
            task_chars = len(review_prompt_box.get("1.0", tk.END).strip())
            review_prompt_status_var.set(f"当前审稿提示词约 {system_chars + task_chars} 字，可直接编辑后保存。")

        review_system_box.bind("<KeyRelease>", refresh_review_prompt_status)
        review_prompt_box.bind("<KeyRelease>", refresh_review_prompt_status)

        def load(value: dict[str, Any]) -> None:
            prompting = value.get("prompting") if isinstance(value.get("prompting"), dict) else {}
            sampling = value.get("sampling") if isinstance(value.get("sampling"), dict) else {}
            context = value.get("context") if isinstance(value.get("context"), dict) else {}
            review = value.get("review") if isinstance(value.get("review"), dict) else {}
            system_box.configure(state="normal")
            user_box.configure(state="normal")
            review_system_box.configure(state="normal")
            review_prompt_box.configure(state="normal")
            system_box.delete("1.0", tk.END)
            system_box.insert("1.0", str(prompting.get("system_prompt") or ""))
            user_box.delete("1.0", tk.END)
            user_box.insert("1.0", str(prompting.get("default_user_prompt") or ""))
            review_system_box.delete("1.0", tk.END)
            review_system_box.insert("1.0", str(review.get("system_prompt") or ""))
            review_prompt_box.delete("1.0", tk.END)
            review_prompt_box.insert("1.0", str(review.get("task_prompt") or ""))
            for key in (
                "temperature",
                "top_p",
                "top_k",
                "min_p",
                "max_tokens",
                "presence_penalty",
                "frequency_penalty",
                "repetition_penalty",
            ):
                field_vars[key].set("" if sampling.get(key) is None else str(sampling.get(key)))
            field_vars["max_context_tokens"].set(str(context.get("max_context_tokens") or ""))
            field_vars["recent_confirmed_chapter_count"].set(str(context.get("recent_confirmed_chapter_count") or ""))
            stream_var.set(bool(sampling.get("stream")))
            include_recent_var.set(bool(context.get("include_recent_chapters", True)))
            scorer_enabled_var.set(bool(review.get("scorer_enabled")))
            refresh_review_prompt_status()

        def collect() -> dict[str, Any]:
            value = {
                "prompting": {
                    "system_prompt": system_box.get("1.0", tk.END).strip(),
                    "default_user_prompt": user_box.get("1.0", tk.END).strip(),
                    "skip_empty_sections": True,
                    "section_format": "chinese_labeled_blocks",
                },
                "sampling": {
                    "temperature": parse_optional_float(field_vars["temperature"].get(), "Temperature"),
                    "top_p": parse_optional_float(field_vars["top_p"].get(), "Top P"),
                    "top_k": parse_optional_int(field_vars["top_k"].get(), "Top K"),
                    "min_p": parse_optional_float(field_vars["min_p"].get(), "Min P"),
                    "max_tokens": parse_optional_int(field_vars["max_tokens"].get(), "Max Tokens"),
                    "presence_penalty": parse_optional_float(field_vars["presence_penalty"].get(), "Presence Penalty"),
                    "frequency_penalty": parse_optional_float(field_vars["frequency_penalty"].get(), "Frequency Penalty"),
                    "repetition_penalty": parse_optional_float(field_vars["repetition_penalty"].get(), "Repetition Penalty"),
                    "stream": stream_var.get(),
                },
                "context": {
                    "max_context_tokens": parse_optional_int(field_vars["max_context_tokens"].get(), "上下文 Token 上限"),
                    "recent_confirmed_chapter_count": parse_optional_int(
                        field_vars["recent_confirmed_chapter_count"].get(),
                        "自动带入前文章数",
                    ),
                    "include_planning_library": True,
                    "include_memory_bank": True,
                    "include_world_and_character": True,
                    "include_recent_chapters": include_recent_var.get(),
                },
                "review": {
                    "scorer_enabled": scorer_enabled_var.get(),
                    "manual_review_when_disabled": True,
                    "system_prompt": review_system_box.get("1.0", tk.END).strip(),
                    "task_prompt": review_prompt_box.get("1.0", tk.END).strip(),
                },
            }
            return value

        def save() -> None:
            try:
                if project_scope:
                    updated = self.app.update_generation_settings(project_id, collect())
                    source_var.set("当前来源：项目专属设置（优先于全局）")
                else:
                    updated = self.app.update_global_generation_settings(collect())
                    source_var.set("当前编辑：全局默认设置")
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"保存创作设置失败:\n{exc}", parent=dialog)
                return
            load(updated)
            target = f"project={project_id}" if project_scope else "global"
            self.write_log(f"创作设置已保存: {target}")
            messagebox.showinfo(APP_TITLE, "创作设置已保存。", parent=dialog)

        def restore_defaults() -> None:
            if project_scope:
                try:
                    updated = self.app.clear_project_generation_settings(project_id)
                    state = self.app.project_generation_settings_state(project_id)
                    source_var.set(project_settings_source_text(state))
                except Exception as exc:
                    messagebox.showerror(APP_TITLE, f"清除项目覆盖失败:\n{exc}", parent=dialog)
                    return
                load(updated)
                self.write_log(f"项目创作设置已清除，改用全局默认: project={project_id}")
                messagebox.showinfo(APP_TITLE, "项目覆盖已清除，现在使用全局默认。", parent=dialog)
            else:
                load(default_generation_settings())

        def preview() -> None:
            preview_project_id = project_id or self.selected_project_id
            if not preview_project_id:
                messagebox.showinfo(APP_TITLE, "预览格式需要先选择一个项目，因为资料库和前文来自具体项目。", parent=dialog)
                return
            try:
                value = collect()
                render = self.app.prompt_render_dry_run(
                    preview_project_id,
                    prompt=str(value["prompting"]["default_user_prompt"]),
                    system_prompt=str(value["prompting"]["system_prompt"]),
                    max_context_tokens=value["context"]["max_context_tokens"],
                    include_prompt_text=True,
                    include_context_text=False,
                )
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"预览失败:\n{exc}", parent=dialog)
                return
            self.show_text_window("将发送给模型的结构预览", format_prompt_preview(render), parent=dialog)

        load(settings)
        button_row = ttk.Frame(dialog)
        button_row.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        ttk.Button(button_row, text=reset_label, command=restore_defaults).pack(side="left")
        ttk.Button(button_row, text="预览格式", command=preview).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="关闭", command=dialog.destroy).pack(side="right")
        ttk.Button(button_row, text=save_label, command=save).pack(side="right", padx=(0, 8))

    def show_model_call_records(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records(
            "模型调用记录（排障）",
            lambda: [
                ("连接检查记录", self.app.list_provider_smoke_tests(project_id), ("status", "provider", "model", "created_at")),
                ("真实生成记录", self.app.list_final_provider_real_executions(project_id), ("status", "provider", "model", "created_at")),
            ],
        )

    def show_final_checklist(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_project_records(
            "出稿清单（开发中）",
            lambda: [
                (
                    "功能状态",
                    [
                        {
                            "status": "开发中",
                            "available": "可以查看已确认章节和内部定稿检查记录。",
                            "not_ready": "尚未提供一键正式导出；开发者诊断不应作为普通用户定稿步骤。",
                        }
                    ],
                    ("status", "available", "not_ready"),
                ),
                ("已确认章节", self.app.list_confirmed_chapters(project_id), ("chapter_id", "title", "draft_id", "committed_at")),
                ("定稿检查", self.app.list_final_assembly_gates(project_id), ("status", "created_at")),
                ("模型执行说明", self.app.list_final_provider_runbooks(project_id), ("status", "created_at")),
            ],
        )

    def show_export_settings(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.show_text_window(
            "导出设置",
            self.format_export_settings(project_id),
            actions=(("导出TXT文稿", lambda: self.export_txt_dialog(project_id)),),
            refresh=lambda: self.format_export_settings(project_id),
        )

    def format_export_settings(self, project_id: str) -> str:
        project_path = self.selected_project_path(project_id)
        settings_path = project_path / "data" / "export_settings.json"
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            return f"读取导出设置失败:\n{exc}"
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
            ]
        )

    def show_user_guide(self) -> None:
        self.show_text_window(
            "使用说明",
            "\n".join(
                [
                    "基本流程",
                    "--------",
                    "1. 在左侧选择或新建作品。",
                    "2. 在资料库里录入总纲、章节计划、世界观、人物设定和项目记忆银行。",
                    "3. 在创作设置里配置系统提示词、上下文数量、Temperature、Top P、Top K 等参数。",
                    "4. 在模型服务里填写 API 地址、API Key 和模型 ID；本地 LM Studio / Ollama 可使用本地端口。",
                    "5. 点击左侧“生成草稿”，预览将发送给模型的结构，再生成草稿。",
                    "6. 草稿进入审稿、改写、确认章节后，才参与后续上下文和定稿流程。",
                    "",
                    "安全边界",
                    "--------",
                    "保存设置不会联网。",
                    "测试连接、真实生成和导出动作都需要用户主动触发。",
            "API Key 只保存在软件级本地密钥文件，不写入作品配置或运行记录。",
                ]
            ),
        )

    def show_run_log_window(self) -> None:
        self.show_text_window("运行记录", self.current_run_log_text(), refresh=self.current_run_log_text)

    def current_run_log_text(self) -> str:
        return self.log.get("1.0", tk.END).strip() or "暂无运行记录。"

    def show_about(self) -> None:
        self.show_text_window(
            "关于软件",
            "\n".join(
                [
                    APP_TITLE,
                    "",
                    "本地小说创作工作台。",
                    "作品数据保存在本机；模型服务保存设置不会自动联网。",
                    "真实生成、测试连接、导出动作都需要用户主动触发。",
                ]
            ),
        )

    def show_project_records(
        self,
        title: str,
        sections: list[tuple[str, list[dict[str, Any]], tuple[str, ...]]] | Callable[[], list[tuple[str, list[dict[str, Any]], tuple[str, ...]]]],
        *,
        actions: tuple[tuple[str, Callable[[], None]], ...] = (),
    ) -> None:
        if callable(sections):
            refs: dict[str, Any] = {}

            def render() -> str:
                return format_record_sections(sections())

            def refresh_records() -> None:
                body = refs.get("body")
                if isinstance(body, tk.Text):
                    self.replace_text_window_content(body, render())
                self.refresh_projects()
                if self.selected_project_id:
                    self.run_project_health(silent=True)

            def wrapped_action(command: Callable[[], None]) -> Callable[[], None]:
                def run() -> None:
                    command()
                    refresh_records()

                return run

            window, body = self.show_text_window(
                title,
                render(),
                actions=(("刷新", refresh_records),)
                + tuple((label, wrapped_action(command)) for label, command in actions),
            )
            refs["window"] = window
            refs["body"] = body
            return
        self.show_text_window(title, format_record_sections(sections), actions=actions)

    def show_text_window(
        self,
        title: str,
        text: str,
        *,
        actions: tuple[tuple[str, Callable[[], None]], ...] = (),
        parent: tk.Misc | None = None,
        refresh: Callable[[], str] | None = None,
    ) -> tuple[tk.Toplevel, tk.Text]:
        owner = parent or self
        window = tk.Toplevel(owner)
        window.title(title)
        window.transient(owner)
        window.geometry("760x520")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        body = tk.Text(window, wrap="word", font=("Consolas", 10), borderwidth=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scrollbar.set)
        body.grid(row=0, column=0, sticky="nsew", padx=(16, 0), pady=16)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 16), pady=16)
        body.insert("1.0", text.rstrip() + "\n")
        body.configure(state="disabled")
        button_bar = ttk.Frame(window)
        button_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        if refresh is not None:
            ttk.Button(
                button_bar,
                text="刷新",
                command=lambda: self.replace_text_window_content(body, refresh()),
            ).pack(side="left", padx=(0, 8))
        for label, command in actions:
            ttk.Button(button_bar, text=label, command=command).pack(side="left", padx=(0, 8))
        ttk.Button(button_bar, text="关闭", command=window.destroy).pack(side="right")
        return window, body

    def replace_text_window_content(self, body: tk.Text, text: str) -> None:
        try:
            body.configure(state="normal")
            body.delete("1.0", tk.END)
            body.insert("1.0", text.rstrip() + "\n")
            body.configure(state="disabled")
        except tk.TclError:
            return

    def show_live_text_window(
        self,
        title: str,
        initial_text: str = "",
        *,
        parent: tk.Misc | None = None,
    ) -> tuple[tk.Toplevel, tk.Text]:
        owner = parent or self
        window = tk.Toplevel(owner)
        window.title(title)
        window.transient(owner)
        window.geometry("760x520")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        body = tk.Text(window, wrap="word", font=("Consolas", 10), borderwidth=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scrollbar.set)
        body.grid(row=0, column=0, sticky="nsew", padx=(16, 0), pady=16)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 16), pady=16)
        if initial_text:
            body.insert("1.0", initial_text)
        body.configure(state="disabled")
        button_bar = ttk.Frame(window)
        button_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        setattr(window, "_button_bar", button_bar)
        ttk.Button(button_bar, text="关闭", command=window.destroy).pack(side="right")
        return window, body

    def add_text_window_action(self, window: tk.Toplevel, label: str, command: Callable[[], None]) -> None:
        try:
            button_bar = getattr(window, "_button_bar", None)
            if button_bar is None or not button_bar.winfo_exists():
                return
            ttk.Button(button_bar, text=label, command=command).pack(side="left", padx=(0, 8))
        except tk.TclError:
            return

    def prompt_ai_review_rerun(self, project_id: str, draft_id: str, *, parent: tk.Misc | None = None) -> None:
        extra_instruction = self.ask_multiline_text(
            title="审稿特殊要求",
            prompt="这次希望 AI 额外注意什么？内容会放在审稿提示词下面，只用于本次再审。",
            parent=parent or self,
        )
        if extra_instruction is None:
            return
        self.start_ai_review_request(project_id, draft_id, extra_instruction=extra_instruction, parent=parent)

    def ask_multiline_text(
        self,
        *,
        title: str,
        prompt: str,
        parent: tk.Misc | None = None,
        initial_text: str = "",
    ) -> str | None:
        owner = parent or self
        dialog = tk.Toplevel(owner)
        dialog.title(title)
        dialog.transient(owner)
        dialog.geometry("660x360")
        dialog.minsize(520, 280)
        dialog.resizable(True, True)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text=prompt, wraplength=600, justify="left").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(16, 8),
        )
        text_frame = ttk.Frame(dialog)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        body = tk.Text(text_frame, wrap="word", height=9, undo=True)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scrollbar.set)
        body.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        if initial_text:
            body.insert("1.0", initial_text)
        result: dict[str, str | None] = {"value": None}

        def confirm() -> None:
            result["value"] = body.get("1.0", tk.END).strip()
            dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            dialog.destroy()

        button_bar = ttk.Frame(dialog)
        button_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        ttk.Button(button_bar, text="取消", command=cancel).pack(side="right")
        ttk.Button(button_bar, text="开始再审", command=confirm).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        body.focus_set()
        dialog.wait_window()
        return result["value"]

    def append_text_window_chunk(self, body: tk.Text, chunk: str) -> None:
        if not chunk:
            return
        try:
            body.configure(state="normal")
            body.insert(tk.END, chunk)
            body.see(tk.END)
            body.configure(state="disabled")
        except tk.TclError:
            return

    def create_planning_item_dialog(
        self,
        project_id: str,
        *,
        default_type: str = "outline",
        parent: tk.Misc | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        existing_item = self.latest_planning_item_of_type(project_id, default_type) if default_type in SINGLETON_PLANNING_TYPES else {}
        editing = bool(existing_item)
        owner = parent or self
        dialog = tk.Toplevel(owner)
        dialog.title("编辑资料" if editing else "新增资料")
        dialog.transient(owner)
        dialog.geometry("640x520")
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(5, weight=1)

        type_labels = [label for _, label in PLANNING_TYPE_OPTIONS]
        default_label = label_for_value(PLANNING_TYPE_OPTIONS, default_type)
        item_type = str(existing_item.get("item_type") or default_type)
        type_var = tk.StringVar(value=label_for_value(PLANNING_TYPE_OPTIONS, item_type) or default_label)
        title_var = tk.StringVar(value=str(existing_item.get("title") or ""))
        initial_planning_id = str(existing_item.get("planning_id") or default_planning_id(item_type))
        id_var = tk.StringVar(value=initial_planning_id)
        last_auto_id = {"value": initial_planning_id}
        include_context_var = tk.BooleanVar(
            value=(existing_item.get("enabled") is not False and bool(existing_item.get("active"))) if editing else True
        )
        adherence_labels = [label for _, label in PLANNING_ADHERENCE_OPTIONS]
        adherence_var = tk.StringVar(
            value=label_for_value(PLANNING_ADHERENCE_OPTIONS, str(existing_item.get("adherence_level") or "balanced"))
        )

        ttk.Label(dialog, text="资料类型").grid(row=0, column=0, sticky="e", padx=(18, 10), pady=(18, 8))
        type_box = ttk.Combobox(
            dialog,
            textvariable=type_var,
            values=type_labels,
            state="disabled" if editing else "readonly",
        )
        type_box.grid(
            row=0, column=1, sticky="ew", padx=(0, 18), pady=(18, 8)
        )
        ttk.Label(dialog, text="标题").grid(row=1, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=title_var).grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=8)
        ttk.Label(dialog, text="内部编号（自动）").grid(row=2, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=id_var, state="readonly" if editing else "normal").grid(
            row=2, column=1, sticky="ew", padx=(0, 18), pady=8
        )
        ttk.Label(dialog, text="参考强度").grid(row=3, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Combobox(dialog, textvariable=adherence_var, values=adherence_labels, state="readonly").grid(
            row=3, column=1, sticky="ew", padx=(0, 18), pady=8
        )
        flags = ttk.Frame(dialog)
        flags.grid(row=4, column=1, sticky="w", padx=(0, 18), pady=8)
        ttk.Checkbutton(flags, text="用于生成上下文", variable=include_context_var).pack(side="left")
        ttk.Label(dialog, text="内容").grid(row=5, column=0, sticky="ne", padx=(18, 10), pady=8)
        text_box = tk.Text(dialog, wrap="word", height=12)
        text_box.grid(row=5, column=1, sticky="nsew", padx=(0, 18), pady=8)
        text_box.insert("1.0", str(existing_item.get("text") or ""))
        note = ttk.Label(dialog, text="勾选后会随写作请求一起进入上下文；保存资料本身不会调用模型。", foreground="#6b7280")
        note.grid(row=6, column=1, sticky="w", padx=(0, 18), pady=(0, 8))

        def on_type_changed(event: object | None = None) -> None:
            if editing:
                return
            selected_type = value_for_label(PLANNING_TYPE_OPTIONS, type_var.get())
            if id_var.get().strip() == last_auto_id["value"]:
                new_id = default_planning_id(selected_type)
                id_var.set(new_id)
                last_auto_id["value"] = new_id

        def save() -> None:
            try:
                include_context = include_context_var.get()
                payload = {
                    "text": text_box.get("1.0", "end").strip(),
                    "title": title_var.get().strip(),
                    "item_type": value_for_label(PLANNING_TYPE_OPTIONS, type_var.get()),
                    "active": include_context,
                    "enabled": include_context,
                    "adherence_level": value_for_label(PLANNING_ADHERENCE_OPTIONS, adherence_var.get()),
                }
                if editing:
                    result = self.app.update_planning_item(project_id, id_var.get().strip(), **payload)
                else:
                    result = self.app.create_planning_item(project_id, id_var.get().strip(), **payload)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"保存资料失败:\n{exc}", parent=dialog)
                return
            action = "更新" if editing else "新增"
            self.write_log(f"资料库{action}条目: project={project_id} planning_id={result.get('planning_id')}")
            if on_saved:
                on_saved()
            messagebox.showinfo(APP_TITLE, "资料已保存。", parent=dialog)
            dialog.destroy()

        type_box.bind("<<ComboboxSelected>>", on_type_changed)
        buttons = ttk.Frame(dialog)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", padx=18, pady=(4, 18))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="保存", command=save).pack(side="right", padx=(0, 8))

    def latest_planning_item_of_type(self, project_id: str, item_type: str) -> dict[str, Any]:
        try:
            items = self.app.list_planning_items(project_id, include_text=True)
        except Exception:
            return {}
        candidates = [item for item in items if str(item.get("item_type") or "") == item_type]
        if not candidates:
            return {}
        return sorted(candidates, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""))[-1]

    def import_corpus_profile_dialog(self, project_id: str) -> None:
        path = filedialog.askopenfilename(
            title="选择参考作品文件",
            filetypes=(("Text files", "*.txt *.md"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            result = self.app.save_corpus_profile(project_id, path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"分析参考作品失败:\n{exc}")
            return
        self.write_log(f"参考作品风格分析已保存: project={project_id} profile_id={result.get('profile_id')}")
        messagebox.showinfo(APP_TITLE, "参考作品风格分析已保存。")

    def import_corpus_boundaries_dialog(self, project_id: str) -> None:
        path = filedialog.askopenfilename(
            title="选择参考作品文件",
            filetypes=(("Text files", "*.txt *.md"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            result = self.app.save_corpus_boundaries(project_id, path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"识别章节结构失败:\n{exc}")
            return
        self.write_log(f"章节结构已保存: project={project_id} boundary_id={result.get('boundary_id')}")
        messagebox.showinfo(APP_TITLE, "章节结构已保存。")

    def create_style_baseline(self, project_id: str) -> None:
        try:
            result = self.app.create_self_style_baseline(project_id)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"建立我的风格基线失败:\n{exc}")
            return
        self.write_log(f"我的风格基线已建立: project={project_id} baseline_id={result.get('baseline_id')}")
        messagebox.showinfo(APP_TITLE, "我的风格基线已建立。")

    def configure_model_connection(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("模型服务")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.columnconfigure(1, weight=1)

        role_labels = [label for _, label in MODEL_ROLE_OPTIONS]
        preset_labels = [str(item["label"]) for item in MODEL_PROVIDER_PRESETS]
        current_role = "writer"
        current_state = model_connection_form_state(self.safe_model_role_config(current_role))
        role_var = tk.StringVar(value=role_labels[0])
        preset_var = tk.StringVar(value=str(current_state["preset"]["label"]))
        model_var = tk.StringVar(value=str(current_state["model"]))
        base_url_var = tk.StringVar(value=str(current_state["base_url"]))
        api_key_var = tk.StringVar(value=str(current_state["api_key_display"]))
        timeout_var = tk.StringVar(value=str(current_state["timeout_seconds"]))
        thinking_var = tk.BooleanVar(value=bool(current_state["deepseek_thinking_enabled"]))
        note_var = tk.StringVar(value=str(current_state["note"]))

        ttk.Label(dialog, text="用途").grid(row=0, column=0, sticky="e", padx=(18, 10), pady=(18, 8))
        role_box = ttk.Combobox(dialog, textvariable=role_var, values=role_labels, state="readonly", width=36)
        role_box.grid(
            row=0, column=1, sticky="ew", padx=(0, 18), pady=(18, 8)
        )

        ttk.Label(dialog, text="服务类型").grid(row=1, column=0, sticky="e", padx=(18, 10), pady=8)
        preset_box = ttk.Combobox(dialog, textvariable=preset_var, values=preset_labels, state="readonly", width=36)
        preset_box.grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=8)

        ttk.Label(dialog, text="模型 ID").grid(row=2, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=model_var, width=40).grid(row=2, column=1, sticky="ew", padx=(0, 18), pady=8)

        ttk.Label(dialog, text="API 地址").grid(row=3, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=base_url_var, width=40).grid(row=3, column=1, sticky="ew", padx=(0, 18), pady=8)

        ttk.Label(dialog, text="API Key").grid(row=4, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=api_key_var, width=40, show="*").grid(
            row=4, column=1, sticky="ew", padx=(0, 18), pady=8
        )

        ttk.Label(dialog, text="生成等待上限（秒）").grid(row=5, column=0, sticky="e", padx=(18, 10), pady=8)
        ttk.Entry(dialog, textvariable=timeout_var, width=40).grid(
            row=5, column=1, sticky="ew", padx=(0, 18), pady=8
        )

        thinking_check = ttk.Checkbutton(
            dialog,
            text="DeepSeek 启用思考模式",
            variable=thinking_var,
        )
        thinking_check.grid(row=6, column=1, sticky="w", padx=(0, 18), pady=8)

        ttk.Label(
            dialog,
            textvariable=note_var,
            wraplength=430,
            justify="left",
        ).grid(row=7, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 14))

        button_row = ttk.Frame(dialog)
        button_row.grid(row=8, column=0, columnspan=2, sticky="e", padx=18, pady=(0, 18))

        def sync_thinking_visibility(preset: dict[str, Any]) -> None:
            if str(preset.get("provider") or "") == "deepseek":
                thinking_check.grid(row=6, column=1, sticky="w", padx=(0, 18), pady=8)
                thinking_check.state(["!disabled"])
            else:
                thinking_var.set(False)
                thinking_check.grid_remove()

        def apply_form_state(state: dict[str, Any]) -> None:
            preset = state["preset"] if isinstance(state.get("preset"), dict) else MODEL_PROVIDER_PRESETS[0]
            preset_var.set(str(preset["label"]))
            model_var.set(str(state.get("model") or preset["default_model"]))
            base_url_var.set(str(state.get("base_url") or preset["default_base_url"]))
            api_key_var.set(str(state.get("api_key_display") or ""))
            timeout_var.set(str(state.get("timeout_seconds") or int(DEFAULT_PROVIDER_TIMEOUT_SECONDS)))
            thinking_var.set(bool(state.get("deepseek_thinking_enabled")))
            sync_thinking_visibility(preset)
            note_var.set(str(state.get("note") or model_connection_note(preset)))

        def load_role(role: str) -> None:
            apply_form_state(model_connection_form_state(self.safe_model_role_config(role)))

        def on_preset_changed(event: object | None = None) -> None:
            preset = model_provider_preset(preset_var.get())
            apply_form_state(model_connection_default_state(preset))

        def on_role_changed(event: object | None = None) -> None:
            load_role(model_role_id(role_var.get()))

        apply_form_state(current_state)

        def save() -> None:
            preset = model_provider_preset(preset_var.get())
            role = model_role_id(role_var.get())
            provider = str(preset["provider"])
            model = model_var.get().strip()
            base_url = base_url_var.get().strip()
            api_key = api_key_var.get()
            key_is_existing_mask = is_saved_secret_mask(api_key)
            timeout_seconds = parse_optional_float(timeout_var.get(), "生成等待上限") or DEFAULT_PROVIDER_TIMEOUT_SECONDS
            if not model:
                messagebox.showerror(APP_TITLE, "模型 ID 不能为空。")
                return
            if provider != "mock" and not base_url:
                messagebox.showerror(APP_TITLE, "云端 API 或本地端口需要填写 API 地址。")
                return
            try:
                global_current = self.app.global_model_role_config(role)
            except Exception:
                global_current = {}
            current = self.safe_model_role_config(role)
            existing_api_key_ref = str(current.get("api_key_ref") or "")
            global_api_key_ref = str(global_current.get("api_key_ref") or "")
            current_provider = str(current.get("provider") or "")
            global_provider = str(global_current.get("provider") or "")
            reusable_api_key_ref = global_api_key_ref if global_provider == provider else ""
            if bool(preset["secret_required"]) and not api_key and not reusable_api_key_ref:
                messagebox.showerror(APP_TITLE, "这个接入方式需要填写 API Key。")
                return
            secret_name = model_secret_name(role, provider)
            if provider == "mock":
                api_key_ref = ""
            elif key_is_existing_mask:
                api_key_ref = reusable_api_key_ref or f"project_secret.{secret_name}"
            elif api_key:
                api_key_ref = f"project_secret.{secret_name}"
            else:
                api_key_ref = reusable_api_key_ref
            try:
                if api_key and not key_is_existing_mask:
                    self.app.set_global_secret(secret_name, api_key)
                elif (
                    key_is_existing_mask
                    and not reusable_api_key_ref
                    and self.selected_project_id
                    and existing_api_key_ref
                    and current_provider == provider
                ):
                    self.app.copy_project_secret_to_global(self.selected_project_id, existing_api_key_ref, secret_name)
                self.app.configure_global_provider_role(
                    role,
                    provider=provider,
                    model=model,
                    api_key_ref=api_key_ref,
                    base_url=base_url,
                    settings={
                        "timeout_seconds": timeout_seconds,
                        **(
                            {"thinking": {"type": "enabled" if thinking_var.get() else "disabled"}}
                            if provider == "deepseek"
                            else {}
                        ),
                    },
                )
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"模型服务保存失败:\n{exc}")
                self.write_log(f"模型服务保存失败: {exc}")
                return
            key_state = "已保存" if api_key_ref else "未使用"
            self.write_log(
                f"模型服务已保存: role={role} provider={provider_display_name(provider)} "
                f"model={model} endpoint={safe_endpoint_label(base_url)} key={key_state}"
            )
            dialog.destroy()
            if self.selected_project_id:
                self.run_project_health(silent=True)
            else:
                self.set_provider_summary("模型服务已保存。创建或打开作品后，生成、审稿、精修会使用这套软件级设置。")

        preset_box.bind("<<ComboboxSelected>>", on_preset_changed)
        role_box.bind("<<ComboboxSelected>>", on_role_changed)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(button_row, text="保存设置", command=save).pack(side="right")
        dialog.grab_set()
        dialog.wait_window()

    def safe_model_role_config(self, role: str) -> dict[str, Any]:
        try:
            current = self.app.global_model_role_config(role)
        except Exception:
            current = {}
        if str(current.get("provider") or "").strip() and str(current.get("model") or "").strip():
            return current
        if self.selected_project_id:
            try:
                return self.app.model_role_config(self.selected_project_id, role)
            except Exception:
                return current
        return current

    def require_project(self) -> str:
        if not self.selected_project_id:
            messagebox.showinfo(APP_TITLE, "请先选择一个项目。")
            return ""
        return self.selected_project_id

    def open_data_root(self) -> None:
        self.open_folder(self.projects_root)

    def open_selected_project_folder(self) -> None:
        project_id = self.require_project()
        if not project_id:
            return
        self.open_folder(self.selected_project_path(project_id))

    def selected_project_path(self, project_id: str) -> Path:
        project = next((item for item in self.projects if item.get("project_id") == project_id), {})
        return Path(str(project.get("path") or self.projects_root / project_id))

    def open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"打开文件夹失败:\n{exc}")

    def write_log(self, text: str) -> None:
        self.log.insert(tk.END, text.rstrip() + "\n")
        self.log.see(tk.END)


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


def format_planning_records(section_title: str, items: list[dict[str, Any]]) -> str:
    lines = [section_title, "-" * len(section_title)]
    if not items:
        lines.append("暂无记录。")
        return "\n".join(lines)
    for index, item in enumerate(items, start=1):
        title = str(item.get("title") or "").strip() or str(item.get("planning_id") or "")
        lines.extend(
            [
                f"{index}. 类型={safe_record_value(item.get('type_label'))} | 标题={safe_record_value(title)} | 加入上下文={safe_record_value(item.get('used_in_context'))} | 字数={safe_record_value(item.get('text_chars'))} | 更新时间={safe_record_value(item.get('updated_at'))}",
                "内容:",
                str(item.get("text") or "").strip() or "（暂无内容）",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_memory_records(items: list[dict[str, Any]], previews: list[dict[str, Any]]) -> str:
    lines = ["记忆条目", "--------"]
    if not items:
        lines.append("暂无记录。")
    else:
        for index, item in enumerate(items, start=1):
            title = str(item.get("title") or item.get("memory_id") or "")
            lines.extend(
                [
                    f"{index}. 目标={safe_record_value(item.get('target'))} | 标题={safe_record_value(title)} | 权重={safe_record_value(item.get('memory_weight'))} | 加入上下文={safe_record_value(item.get('used_in_context'))} | 更新时间={safe_record_value(item.get('updated_at'))}",
                    "内容:",
                    str(item.get("text") or "").strip() or "（暂无内容）",
                    "",
                ]
            )
    lines.extend(["", "记忆应用预览", "------------"])
    if not previews:
        lines.append("暂无记录。")
    else:
        for index, item in enumerate(previews, start=1):
            lines.append(
                f"{index}. 状态={safe_record_value(item.get('status'))} | 创建时间={safe_record_value(item.get('created_at'))}"
            )
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


def memory_status_label(status: str) -> str:
    labels = {
        "manual_text_required": "待填写",
        "ready": "已填写",
        "disabled": "已停用",
    }
    value = str(status or "").strip()
    return labels.get(value, value or "待填写")


def memory_text_status_label(text_status: str) -> str:
    labels = {
        "not_extracted": "还没有记忆内容",
        "manual": "已手动填写",
    }
    value = str(text_status or "").strip()
    return labels.get(value, value or "还没有记忆内容")


def memory_weight_label(value: object) -> str:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return "标准"
    if weight >= 0.9:
        return "高"
    if weight >= 0.5:
        return "中"
    return "低"


def readable_chapter_label(chapter_id: str) -> str:
    value = str(chapter_id or "").strip()
    if not value:
        return "全局"
    match = re.search(r"(\d+)$", value)
    if not match:
        return value
    return f"第 {int(match.group(1)):03d} 章"


def short_identifier(value: str) -> str:
    text = str(value or "").strip()
    if len(text) <= 24:
        return text
    return f"{text[:10]}...{text[-8:]}"


def memory_progress_label(memory_item: dict[str, Any], chapters: list[dict[str, Any]]) -> str:
    last_chapter_id = str(memory_item.get("last_updated_chapter_id") or "").strip()
    last_number = memory_progress_number(memory_item)
    has_memory = bool(str(memory_item.get("text") or "").strip()) or int(memory_item.get("text_chars") or 0) > 0
    if last_number > 0:
        return (
            f"当前记忆银行已记录到 {readable_chapter_label(last_chapter_id)}。"
            f"建议从第 {last_number + 1:03d} 章开始勾选新定稿。"
        )
    if has_memory:
        return "当前记忆银行已有正文，但没有记录章节进度。请手动勾选尚未汇总过的定稿章节。"
    if chapters:
        return "当前记忆银行尚未建立。建议从第 001 章开始勾选定稿章节。"
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


def format_memory_update_prompt(
    *,
    current_memory: str,
    chapters: list[dict[str, Any]] | None = None,
    chapter: dict[str, Any] | None = None,
    target_tokens: int = DEFAULT_MEMORY_TARGET_TOKENS,
) -> str:
    selected_chapters = list(chapters or ([] if chapter is None else [chapter]))
    safe_target_tokens = normalize_memory_target_tokens(target_tokens)
    existing_memory = str(current_memory or "").strip()
    if not existing_memory:
        existing_memory = "（当前记忆银行为空，请根据本次发送的定稿章节建立项目长期记忆。）"
    chapter_lines: list[str] = []
    if not selected_chapters:
        chapter_lines.append("（未选择本次要增量合并的定稿章节。）")
    for index, item in enumerate(selected_chapters, start=1):
        chapter_id = safe_record_value(item.get("chapter_id")) or f"chapter_{index:03d}"
        title = safe_record_value(item.get("title")) or chapter_id
        content = str(item.get("content") or "").strip() or "（本章正文为空或未读取到正文。）"
        chapter_lines.extend(
            [
                f"--- 章节 {index}: {chapter_id} | {title} ---",
                content,
                "",
            ]
        )
    lines = [
        "你是长篇小说项目的记忆银行整理助手。",
        "请基于“当前记忆银行”，结合“本次新增定稿章节”，输出一份更新后的记忆银行正文。",
        "",
        "整理要求：",
        "1. 这是增量记忆更新：旧记忆中仍然有效的长期信息要保留，新章节带来的重要变化要合并进去。",
        "2. 如果旧记忆与新定稿章节冲突，以新定稿章节为准，并自然修正记忆。",
        "3. 按需覆盖这些方面：世界观/规则变化、人物关系与动机变化、已经发生的剧情事实、伏笔与未解决问题、写作口吻/风格提醒。",
        "4. 不要逐章流水账，不要机械分栏填表；没有新增信息的方面不要硬写。",
        f"5. 目标长度：请尽量把更新后的“记忆银行正文”控制在约 {safe_target_tokens} tokens 左右；这是写作压缩目标，不是 API max_tokens，不是截断上限，必要时可以略超。",
        "6. 预留上下文：后续生成还要放入全局提示词、总纲、章节计划、前文/最近章节等资料，所以记忆银行应精炼但不能丢失关键连续性。",
        "7. 只有在整体过长、会挤占后续创作上下文时，才压缩旧记忆；优先压缩最早、已解决、低影响的旧信息。",
        "8. 不要压缩近期关键因果、人物当前状态、未解决伏笔、世界规则限制和后续章节必须遵守的事实。",
        "9. 不要写评论，不要输出推理过程或 <think>。",
        "10. 输出内容应能直接替换“记忆银行正文”。",
        "",
        "【当前记忆银行】",
        existing_memory,
        "",
        f"【本次新增定稿章节：{len(selected_chapters)} 章】",
        "\n".join(chapter_lines).rstrip(),
    ]
    return "\n".join(lines).strip()


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
    lines.extend([
        "",
        "会发送的内容",
        "------------",
    ])
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


def text_widget_content_is_blank(body: tk.Text) -> bool:
    try:
        return not body.get("1.0", tk.END).strip()
    except tk.TclError:
        return True


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
        str(review.get("comment") or "暂无审稿说明。"),
        "",
        "评分",
        "----",
    ]
    if scores:
        for key, value in scores.items():
            lines.append(f"{key}: {value}")
    else:
        lines.append("暂无评分。")
    lines.extend(["", "问题"])
    lines.append("----")
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


def planning_display_rows(items: list[dict[str, Any]], *, item_types: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        item_type = str(item.get("item_type") or "outline")
        if item_type not in item_types:
            continue
        rows.append(
            {
                **item,
                "type_label": label_for_value(PLANNING_TYPE_OPTIONS, item_type),
                "used_in_context": "是" if item.get("enabled") is not False and bool(item.get("active")) else "否",
            }
        )
    return rows


def memory_display_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append({**item, "used_in_context": "是" if item.get("enabled") is not False else "否"})
    return rows


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
        "【用户本次要求】",
        str(user.get("content") or "（未填写）").strip(),
    ]
    for label in ordered_section_labels(sections):
        lines.append("")
        lines.append(f"【{label}】")
        lines.append("（生成时会填入该类已选资料；空资料会自动忽略）")
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


def format_memory_generation_request_preview(preview: dict[str, Any]) -> str:
    messages = preview.get("messages") if isinstance(preview.get("messages"), list) else []
    sampling = preview.get("sampling") if isinstance(preview.get("sampling"), dict) else {}
    metadata = preview.get("metadata") if isinstance(preview.get("metadata"), dict) else {}
    summary = preview.get("summary") if isinstance(preview.get("summary"), dict) else {}
    system = next((item for item in messages if isinstance(item, dict) and item.get("role") == "system"), {})
    user = next((item for item in messages if isinstance(item, dict) and item.get("role") == "user"), {})
    metadata_lines = [
        f"- {key}: {metadata[key]}"
        for key in sorted(metadata)
        if key != "source_chapter_ids"
    ]
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


def ordered_section_labels(sections: list[object]) -> list[str]:
    groups: dict[str, int] = {}
    for item in sections:
        if not isinstance(item, dict):
            continue
        label = str(item.get("section_label") or item.get("category_id") or "").strip()
        if not label:
            continue
        order = item.get("section_order")
        groups[label] = min(groups.get(label, 999), order if isinstance(order, int) and not isinstance(order, bool) else 999)
    return [label for label, _ in sorted(groups.items(), key=lambda item: (item[1], item[0]))]


def label_for_value(options: tuple[tuple[str, str], ...], value: str) -> str:
    for item_value, label in options:
        if item_value == value:
            return label
    return options[0][1]


def value_for_label(options: tuple[tuple[str, str], ...], label: str) -> str:
    for item_value, item_label in options:
        if item_label == label:
            return item_value
    return options[0][0]


def default_planning_id(item_type: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{safe_secret_part(item_type)}_{stamp}"


def project_node_id(project_id: str) -> str:
    return f"project:{project_id}"


def chapter_node_id(project_id: str, chapter_id: str) -> str:
    return f"chapter:{project_id}:{chapter_id}"


def draft_node_id(project_id: str, draft_id: str) -> str:
    return f"draft:{project_id}:{draft_id}"


def parse_tree_node_id(node_id: str) -> tuple[str, str, str]:
    if node_id.startswith("project:"):
        return "project", node_id.removeprefix("project:"), ""
    if node_id.startswith("chapter:"):
        parts = node_id.split(":", 2)
        if len(parts) == 3:
            project_id, chapter_id = parts[1], parts[2]
            return "chapter", project_id, chapter_id
    if node_id.startswith("draft:"):
        parts = node_id.split(":", 2)
        if len(parts) == 3:
            project_id, draft_id = parts[1], parts[2]
            return "draft", project_id, draft_id
    return "", "", ""


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


def latest_chapter_draft_id(drafts: list[dict[str, Any]]) -> str:
    for draft in reversed(sorted_draft_versions(drafts)):
        draft_id = str(draft.get("draft_id") or "")
        if draft_id:
            return draft_id
    return ""


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


def optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def suggest_next_chapter_id(chapters: list[dict[str, Any]]) -> str:
    max_seen = 0
    width = 3
    retry_candidates: list[tuple[int, int]] = []
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        match = re.fullmatch(r"chapter_(\d+)", chapter_id)
        if not match:
            continue
        number_text = match.group(1)
        number = int(number_text)
        if is_empty_retriable_chapter(chapter):
            retry_candidates.append((number, len(number_text)))
            continue
        max_seen = max(max_seen, number)
        width = max(width, len(number_text))
    if retry_candidates:
        number, candidate_width = min(retry_candidates)
        return f"chapter_{number:0{max(width, candidate_width)}d}"
    return f"chapter_{max_seen + 1:0{width}d}"


def is_empty_retriable_chapter(chapter: dict[str, Any]) -> bool:
    return (
        str(chapter.get("status") or "") in {"planned", "drafting", "blocked"}
        and not str(chapter.get("latest_draft_id") or "")
        and not str(chapter.get("confirmed_chapter_id") or "")
    )


def model_role_id(label: str) -> str:
    for role_id, role_label in MODEL_ROLE_OPTIONS:
        if role_label == label:
            return role_id
    return "writer"


def model_provider_preset(label: str) -> dict[str, Any]:
    for preset in MODEL_PROVIDER_PRESETS:
        if preset["label"] == label:
            return preset
    return MODEL_PROVIDER_PRESETS[0]


def model_connection_form_state(current: dict[str, Any]) -> dict[str, Any]:
    provider = str(current.get("provider") or MODEL_PROVIDER_PRESETS[0]["provider"])
    preset = model_provider_preset(provider_label_for_id(provider))
    settings = current.get("settings") if isinstance(current.get("settings"), dict) else {}
    api_key_ref = str(current.get("api_key_ref") or "")
    return {
        "preset": preset,
        "model": str(current.get("model") or preset["default_model"]),
        "base_url": str(current.get("base_url") or preset["default_base_url"]),
        "api_key_display": SAVED_SECRET_MASK if api_key_ref else "",
        "timeout_seconds": model_timeout_display(settings.get("timeout_seconds")),
        "deepseek_thinking_enabled": deepseek_thinking_enabled(settings.get("thinking")),
        "note": model_connection_note(preset) + (" 软件已保存 API Key。" if api_key_ref else ""),
    }


def model_connection_default_state(preset: dict[str, Any]) -> dict[str, Any]:
    return {
        "preset": preset,
        "model": str(preset["default_model"]),
        "base_url": str(preset["default_base_url"]),
        "api_key_display": "",
        "timeout_seconds": int(DEFAULT_PROVIDER_TIMEOUT_SECONDS),
        "deepseek_thinking_enabled": False,
        "note": model_connection_note(preset),
    }


def deepseek_thinking_enabled(value: object) -> bool:
    if isinstance(value, dict):
        return str(value.get("type") or "").strip().lower() == "enabled"
    return str(value or "").strip().lower() == "enabled"


def model_timeout_display(value: object) -> int:
    if isinstance(value, bool):
        return int(DEFAULT_PROVIDER_TIMEOUT_SECONDS)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return int(DEFAULT_PROVIDER_TIMEOUT_SECONDS)
    return int(parsed) if parsed > 0 else int(DEFAULT_PROVIDER_TIMEOUT_SECONDS)


def is_saved_secret_mask(value: str) -> bool:
    return str(value or "") == SAVED_SECRET_MASK


def provider_label_for_id(provider_id: str) -> str:
    for preset in MODEL_PROVIDER_PRESETS:
        if preset["provider"] == provider_id:
            return str(preset["label"])
    return str(MODEL_PROVIDER_PRESETS[0]["label"])


def model_secret_name(role: str, provider: str) -> str:
    return f"{safe_secret_part(role)}_{safe_secret_part(provider)}_api_key"


def safe_secret_part(value: str) -> str:
    text = "".join(char if char.isalnum() else "_" for char in str(value or "").strip().lower())
    return text.strip("_") or "model"


def project_settings_source_text(state: dict[str, Any]) -> str:
    if state.get("has_project_override"):
        return "当前来源：项目专属设置（优先于全局）"
    return "当前来源：全局默认设置（本项目未设置覆盖项）"


def model_connection_note(preset: dict[str, Any]) -> str:
    provider = str(preset["provider"])
    if provider == "mock":
        return "离线测试只用于验证流程，不联网，也不会调用真实模型。"
    if provider == "local_openai_compatible":
        return "本地端口适合 LM Studio / Ollama 的 OpenAI 兼容服务；API Key 可留空，保存设置不会发起连接。"
    if provider == "openrouter":
        return "OpenRouter 使用 OpenAI Chat Completions 兼容接口；填写 OpenRouter API Key 和模型 ID，保存设置不会发起连接。"
    if bool(preset["secret_required"]):
        return "云端 API 需要 API Key；软件会自动把它保存到软件级本地密钥文件，不写入作品配置或日志。"
    return "保存设置不会发起连接；测试连接和生成草稿由用户主动点击后执行。"


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


def safe_endpoint_label(base_url: str) -> str:
    if not base_url:
        return "-"
    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    return parsed.netloc.split("@")[-1] or "-"


def format_bytes(value: int) -> str:
    size = float(max(0, int(value)))
    units = ("B", "KB", "MB", "GB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(size)} B"


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
            if provider_id in {"local_openai_compatible", "mock"}
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
            "联网生成: 点击生成草稿时调用；AI审稿和AI精修也只在用户点击对应按钮后调用。",
            "说明: 保存模型服务不会联网；测试连接、生成草稿、AI审稿、AI精修由用户点击后执行。",
        ]
    )
    return "\n".join(lines).strip()


def format_health_log(health: dict[str, Any]) -> str:
    audit = health.get("audit", {})
    upload = health.get("upload_readiness", {})
    return (
        f"项目概览 {health.get('project_id')}: 作品状态={health.get('status')}；"
        f"项目审计 阻断={audit.get('blocker_count')} 提示={audit.get('warning_count')}；"
        f"上传前检查 阻断={upload.get('blocker_count')} 提示={upload.get('warning_count')}。"
        "这些是开发/发布诊断项，不是章节内容。"
    )


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


def main() -> int:
    app = WorkbenchDesktopApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
