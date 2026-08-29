"""Classic Tk theme tokens and their single application function."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


PALETTE = {
    "app_bg": "#edf0f6",
    "surface": "#ffffff",
    "surface_sunken": "#f4f6fb",
    "border": "#dfe4ef",
    "border_input": "#c9d2e4",
    "ink": "#1d2637",
    "ink_soft": "#4a5570",
    "muted": "#828da3",
    "accent": "#4c63d2",
    "accent_hover": "#4154ba",
    "accent_pressed": "#384aa3",
    "accent_disabled": "#c2cbea",
    "accent_soft_text": "#3a4cad",
    "pill_bg": "#e9eef9",
    "select_bg": "#dfe6fb",
    "select_fg": "#2f3f96",
    "success": "#1e9e63",
    "success_hover": "#1a8a56",
    "success_pressed": "#16764a",
    "success_disabled": "#b7dfcd",
    "warn": "#9d6703",
    "danger": "#b3261e",
}
FONT_FAMILY = "Microsoft YaHei UI"
FONT_BASE = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_STRONG = (FONT_FAMILY, 10, "bold")
FONT_SMALL_STRONG = (FONT_FAMILY, 9, "bold")
FONT_BRAND = (FONT_FAMILY, 15, "bold")
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_SECTION = (FONT_FAMILY, 12, "bold")
FONT_SECTION_SMALL = (FONT_FAMILY, 9, "bold")
FONT_EDITOR_TITLE = (FONT_FAMILY, 14, "bold")
FONT_DIALOG_TITLE = (FONT_FAMILY, 14, "bold")
FONT_PANEL_TITLE = (FONT_FAMILY, 11, "bold")


def configure_classic_theme(root: tk.Misc) -> ttk.Style:
    """Apply the complete classic theme to one Tk root and return its style handle."""
    root.configure(bg=PALETTE["app_bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    app_bg = PALETTE["app_bg"]
    surface = PALETTE["surface"]
    border = PALETTE["border"]
    border_input = PALETTE["border_input"]
    ink = PALETTE["ink"]
    ink_soft = PALETTE["ink_soft"]
    muted = PALETTE["muted"]
    accent = PALETTE["accent"]

    # Native Tk menus and combobox popups do not inherit ttk styles.
    root.option_add("*Menu.background", surface)
    root.option_add("*Menu.foreground", ink_soft)
    root.option_add("*Menu.activeBackground", accent)
    root.option_add("*Menu.activeForeground", "#ffffff")
    root.option_add("*Menu.disabledForeground", muted)
    root.option_add("*Menu.selectColor", accent)
    root.option_add("*Menu.relief", "flat")
    root.option_add("*Menu.borderWidth", 1)
    root.option_add("*Menu.font", FONT_BASE)
    root.option_add("*TCombobox*Listbox.background", surface)
    root.option_add("*TCombobox*Listbox.foreground", ink)
    root.option_add("*TCombobox*Listbox.selectBackground", accent)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", FONT_BASE)
    root.option_add("*TCombobox*Listbox.relief", "flat")

    style.configure(".", font=FONT_BASE, background=app_bg, foreground=ink_soft)
    style.configure("App.TFrame", background=app_bg)
    style.configure("TFrame", background=app_bg)
    style.configure("TLabel", background=app_bg, foreground=ink_soft)
    style.configure("TCheckbutton", background=app_bg, foreground=ink_soft)
    style.map("TCheckbutton", background=[("active", app_bg)])
    style.configure("TRadiobutton", background=app_bg, foreground=ink_soft)
    style.map("TRadiobutton", background=[("active", app_bg)])

    style.configure("Topbar.TFrame", background=surface)
    style.configure("Sidebar.TFrame", background=surface)
    style.configure("Editor.TFrame", background=surface)
    style.configure("Inspector.TFrame", background=surface)
    style.configure("Panel.TFrame", background=surface, borderwidth=1, relief="solid", bordercolor=border)
    style.configure("PanelTitle.TLabel", background=surface, foreground=ink, font=FONT_PANEL_TITLE)

    style.configure("Title.TLabel", font=FONT_TITLE, background=surface, foreground=ink)
    style.configure("SidebarTitle.TLabel", font=FONT_SECTION, background=surface, foreground=ink)
    style.configure("Brand.TLabel", font=FONT_BRAND, background=surface, foreground=ink)
    style.configure("BrandSub.TLabel", font=FONT_SMALL, background=surface, foreground=muted)
    style.configure("ProjectName.TLabel", font=FONT_STRONG, background=surface, foreground=ink)
    style.configure("EditorTitle.TLabel", font=FONT_EDITOR_TITLE, background=surface, foreground=ink)
    style.configure("InspectorTitle.TLabel", font=FONT_SECTION_SMALL, background=surface, foreground=muted)
    style.configure("InspectorText.TLabel", background=surface, foreground=ink_soft)
    style.configure("Subtle.TLabel", background=surface, foreground=muted)
    style.configure("SidebarLabel.TLabel", background=surface, foreground=muted, font=FONT_SMALL)
    style.configure("Status.TLabel", background=surface, foreground=muted, font=FONT_SMALL)
    style.configure("TopStatus.TLabel", background=surface, foreground=ink_soft, font=FONT_SMALL)
    style.configure(
        "StatusPill.TLabel",
        background=PALETTE["pill_bg"],
        foreground=ink_soft,
        font=FONT_SMALL,
        padding=(10, 4),
    )

    style.configure("DialogHeader.TFrame", background=surface)
    style.configure("DialogFooter.TFrame", background=app_bg)
    style.configure("DialogTitle.TLabel", background=surface, foreground=ink, font=FONT_DIALOG_TITLE)
    style.configure("DialogText.TLabel", background=surface, foreground=ink_soft)
    style.configure("DialogHint.TLabel", background=app_bg, foreground=muted, font=FONT_SMALL)

    style.configure(
        "TButton",
        font=FONT_BASE,
        padding=(14, 8),
        foreground=ink_soft,
        background="#e9edf5",
        bordercolor="#d6dde9",
        darkcolor="#e9edf5",
        lightcolor="#e9edf5",
        borderwidth=1,
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("pressed", "#d8dfec"), ("active", "#dfe5f1"), ("disabled", "#eef1f7")],
        foreground=[("disabled", muted)],
        bordercolor=[("focus", accent)],
    )
    style.configure(
        "Primary.TButton",
        font=FONT_STRONG,
        padding=(16, 9),
        foreground="#ffffff",
        background=accent,
        bordercolor=accent,
        darkcolor=accent,
        lightcolor=accent,
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "Primary.TButton",
        background=[
            ("active", PALETTE["accent_hover"]),
            ("pressed", PALETTE["accent_pressed"]),
            ("disabled", PALETTE["accent_disabled"]),
        ],
        foreground=[("disabled", "#f4f6fd")],
    )
    style.configure(
        "Confirm.TButton",
        font=FONT_STRONG,
        padding=(16, 9),
        foreground="#ffffff",
        background=PALETTE["success"],
        bordercolor=PALETTE["success"],
        darkcolor=PALETTE["success"],
        lightcolor=PALETTE["success"],
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "Confirm.TButton",
        background=[
            ("active", PALETTE["success_hover"]),
            ("pressed", PALETTE["success_pressed"]),
            ("disabled", PALETTE["success_disabled"]),
        ],
        foreground=[("disabled", "#f4fbf7")],
    )
    style.configure(
        "Secondary.TButton",
        font=FONT_BASE,
        padding=(14, 8),
        foreground="#3d4a68",
        background="#e9edf6",
        bordercolor="#d4dbe9",
        darkcolor="#e9edf6",
        lightcolor="#e9edf6",
        borderwidth=1,
        focusthickness=0,
    )
    style.map(
        "Secondary.TButton",
        background=[("active", "#dde4f0"), ("pressed", "#d0d9e9")],
        bordercolor=[("focus", accent)],
    )
    style.configure(
        "Secondary.TMenubutton",
        font=FONT_BASE,
        padding=(14, 8),
        foreground="#3d4a68",
        background="#e9edf6",
        bordercolor="#d4dbe9",
        borderwidth=1,
    )
    style.map("Secondary.TMenubutton", background=[("active", "#dde4f0"), ("pressed", "#d0d9e9")])
    style.configure(
        "Quiet.TButton",
        font=FONT_BASE,
        padding=(10, 7),
        foreground=ink_soft,
        background=surface,
        bordercolor=surface,
        darkcolor=surface,
        lightcolor=surface,
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "Quiet.TButton",
        background=[("active", "#edf0f8"), ("pressed", "#e2e8f4")],
        foreground=[("active", PALETTE["accent_soft_text"])],
    )

    style.configure("StatusOk.TLabel", background=surface, foreground="#177a4c", font=(FONT_FAMILY, 11, "bold"))
    style.configure(
        "StatusWarn.TLabel",
        background=surface,
        foreground=PALETTE["warn"],
        font=(FONT_FAMILY, 11, "bold"),
    )
    style.configure(
        "StatusBlock.TLabel",
        background=surface,
        foreground=PALETTE["danger"],
        font=(FONT_FAMILY, 11, "bold"),
    )

    style.configure(
        "TEntry",
        padding=(8, 6),
        fieldbackground=surface,
        background=surface,
        foreground=ink,
        insertcolor=accent,
        bordercolor=border_input,
        lightcolor="#e8edf6",
        darkcolor="#e8edf6",
        borderwidth=1,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", accent), ("hover", "#b7c2d9")],
        fieldbackground=[("disabled", "#f1f4f9"), ("readonly", PALETTE["surface_sunken"])],
        foreground=[("disabled", muted), ("readonly", ink_soft)],
    )
    style.configure(
        "TCombobox",
        padding=(8, 6),
        fieldbackground=surface,
        background=surface,
        foreground=ink,
        insertcolor=accent,
        bordercolor=border_input,
        arrowcolor="#5f6a84",
        arrowsize=14,
        lightcolor="#e8edf6",
        darkcolor="#e8edf6",
        borderwidth=1,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", accent), ("hover", "#b7c2d9"), ("readonly", border_input)],
        fieldbackground=[("readonly", surface), ("disabled", "#f1f4f9")],
        foreground=[("readonly", ink), ("disabled", muted)],
        arrowcolor=[("disabled", muted)],
    )

    style.configure(
        "Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=ink,
        rowheight=32,
        borderwidth=0,
        font=FONT_BASE,
    )
    style.configure(
        "Treeview.Heading",
        background="#eef1f8",
        foreground="#4b5670",
        font=FONT_SMALL_STRONG,
        padding=(10, 8),
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", PALETTE["select_bg"])],
        foreground=[("selected", PALETTE["select_fg"])],
    )
    style.map("Treeview.Heading", background=[("active", "#e3e9f4")])

    for orientation in ("Vertical", "Horizontal"):
        style.configure(
            f"{orientation}.TScrollbar",
            background="#ccd4e3",
            troughcolor="#f2f4f9",
            bordercolor="#f2f4f9",
            arrowcolor="#ccd4e3",
            darkcolor="#ccd4e3",
            lightcolor="#ccd4e3",
            borderwidth=1,
            arrowsize=12,
        )
        style.map(
            f"{orientation}.TScrollbar",
            background=[("active", "#b4bfd4"), ("pressed", "#a2aecb"), ("disabled", "#e3e8f1")],
            arrowcolor=[("disabled", "#e3e8f1")],
        )

    style.configure("TNotebook", background=app_bg, borderwidth=0, tabmargins=(6, 4, 6, 0))
    style.configure(
        "TNotebook.Tab",
        background="#dfe5f1",
        foreground=ink_soft,
        padding=(16, 8),
        font=FONT_BASE,
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", app_bg), ("active", "#eaeff7")],
        foreground=[("selected", PALETTE["accent_soft_text"])],
    )
    style.configure(
        "TProgressbar",
        troughcolor="#e3e8f2",
        background=accent,
        bordercolor="#e3e8f2",
        lightcolor=accent,
        darkcolor=accent,
        borderwidth=0,
        thickness=8,
    )
    style.configure("TSeparator", background=border)
    style.configure("TSizegrip", background=app_bg)
    return style
