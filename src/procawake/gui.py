"""GUI settings window — tkinter-based, no extra dependencies.

Shows scanned applications with checkboxes, action selectors, and
global settings. Replaces manual TOML editing for end users.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, Callable

import psutil

from procawake import __version__, config as cfg_mod
from procawake.config import Config, Rule
from procawake.constants import Action
from procawake.scanner import AppScanner, KNOWN_APPS

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ── Colours & Style ─────────────────────────────────────────────────
BG = "#1e1e2e"           # Dark background
BG_CARD = "#2a2a3c"      # Card/frame background
BG_INPUT = "#363649"     # Input field background
FG = "#cdd6f4"           # Primary text
FG_DIM = "#7f849c"       # Dimmed text
ACCENT = "#89b4fa"       # Blue accent
GREEN = "#a6e3a1"        # Active/running indicator
BORDER = "#45475a"       # Border colour


def _apply_theme(root: tk.Tk) -> ttk.Style:
    """Apply a modern dark theme using ttk styles."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, fieldbackground=BG_INPUT,
                     borderwidth=0, font=("Segoe UI", 10))
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=BG_CARD)
    style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=BG, foreground=FG, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG, foreground=FG_DIM, font=("Segoe UI", 9))
    style.configure("Card.TLabel", background=BG_CARD, foreground=FG, font=("Segoe UI", 10))
    style.configure("CardDim.TLabel", background=BG_CARD, foreground=FG_DIM, font=("Segoe UI", 9))
    style.configure("CardGreen.TLabel", background=BG_CARD, foreground=GREEN, font=("Segoe UI", 9))

    style.configure("TCheckbutton", background=BG_CARD, foreground=FG, font=("Segoe UI", 10),
                     indicatorcolor=BG_INPUT, indicatorrelief="flat")
    style.map("TCheckbutton",
              background=[("active", BG_CARD)],
              indicatorcolor=[("selected", ACCENT)])

    style.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_INPUT,
                     foreground=FG, arrowcolor=FG, borderwidth=1)
    style.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)],
              selectbackground=[("readonly", BG_INPUT)],
              selectforeground=[("readonly", FG)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#1e1e2e",
                     font=("Segoe UI", 11, "bold"), padding=(20, 10))
    style.map("Accent.TButton", background=[("active", "#74c7ec")])

    style.configure("TButton", background=BG_CARD, foreground=FG, padding=(12, 6))
    style.map("TButton", background=[("active", BORDER)])

    style.configure("TSpinbox", fieldbackground=BG_INPUT, foreground=FG,
                     arrowcolor=FG, borderwidth=1)

    style.configure("Horizontal.TScale", background=BG, troughcolor=BG_INPUT)

    return style


class _AppRow:
    """One row in the app list — checkbox + name + process + action dropdown."""

    def __init__(
        self,
        parent: ttk.Frame,
        row: int,
        name: str,
        process: str,
        action: Action,
        is_running: bool,
        enabled: bool = False,
    ) -> None:
        self.name = name
        self.process = process

        self.enabled_var = tk.BooleanVar(value=enabled)
        self.action_var = tk.StringVar(value=str(action))

        # Checkbox
        cb = ttk.Checkbutton(parent, variable=self.enabled_var, style="TCheckbutton")
        cb.grid(row=row, column=0, padx=(12, 4), pady=6, sticky="w")

        # App name
        ttk.Label(parent, text=name, style="Card.TLabel").grid(
            row=row, column=1, padx=(0, 8), pady=6, sticky="w"
        )

        # Process name
        ttk.Label(parent, text=process, style="CardDim.TLabel").grid(
            row=row, column=2, padx=(0, 8), pady=6, sticky="w"
        )

        # Running indicator
        status_text = "running" if is_running else ""
        status_style = "CardGreen.TLabel" if is_running else "CardDim.TLabel"
        ttk.Label(parent, text=status_text, style=status_style).grid(
            row=row, column=3, padx=(0, 8), pady=6, sticky="w"
        )

        # Action dropdown
        combo = ttk.Combobox(
            parent,
            textvariable=self.action_var,
            values=["display", "system", "both"],
            state="readonly",
            width=8,
        )
        combo.grid(row=row, column=4, padx=(0, 12), pady=6, sticky="e")

    def to_rule(self) -> Rule:
        return Rule(
            name=self.name,
            process=self.process,
            action=Action(self.action_var.get()),
            enabled=self.enabled_var.get(),
        )


class SettingsWindow:
    """Main settings GUI window."""

    def __init__(
        self,
        config: Config | None = None,
        on_save: Callable[[Config], None] | None = None,
        standalone: bool = False,
    ) -> None:
        self._config = config or cfg_mod.load()
        self._on_save = on_save
        self._standalone = standalone
        self._app_rows: list[_AppRow] = []
        self._root: tk.Tk | None = None

    def show(self) -> None:
        """Create and display the settings window."""
        self._root = tk.Tk()
        self._root.title(f"procawake v{__version__}")
        self._root.geometry("720x650")
        self._root.minsize(600, 500)
        self._root.configure(bg=BG)

        # Try to set icon
        try:
            from procawake.icons import create_active_icon
            import tempfile, os
            icon_img = create_active_icon(32)
            tmp = os.path.join(tempfile.gettempdir(), "procawake_icon.ico")
            icon_img.save(tmp, format="ICO")
            self._root.iconbitmap(tmp)
        except Exception:
            pass

        _apply_theme(self._root)
        self._build_ui()

        if self._standalone:
            self._root.protocol("WM_DELETE_WINDOW", self._on_close_standalone)
        else:
            self._root.protocol("WM_DELETE_WINDOW", self._root.destroy)

        self._root.mainloop()

    def _build_ui(self) -> None:
        root = self._root
        assert root is not None

        # ── Main container with padding ──
        main = ttk.Frame(root, style="TFrame")
        main.pack(fill="both", expand=True, padx=20, pady=16)

        # ── Header ──
        ttk.Label(main, text="procawake", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            main,
            text="Select applications that should prevent your screen from sleeping",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        # ── App list (scrollable) ──
        list_frame = ttk.Frame(main, style="TFrame")
        list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, bg=BG_CARD, highlightthickness=1,
                           highlightbackground=BORDER)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self._inner = ttk.Frame(canvas, style="Card.TFrame")

        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Column headers ──
        headers = [("", 3), ("Application", 18), ("Process", 16), ("Status", 7), ("Action", 8)]
        for col, (text, width) in enumerate(headers):
            lbl = ttk.Label(self._inner, text=text, style="CardDim.TLabel",
                            width=width, anchor="w")
            lbl.grid(row=0, column=col, padx=(12 if col == 0 else 0, 4), pady=(8, 4), sticky="w")

        ttk.Separator(self._inner, orient="horizontal").grid(
            row=1, column=0, columnspan=5, sticky="ew", padx=8
        )

        # ── Populate apps ──
        self._populate_apps()

        # ── Global settings ──
        settings_frame = ttk.Frame(main, style="TFrame")
        settings_frame.pack(fill="x", pady=(12, 0))

        ttk.Label(settings_frame, text="Poll interval (sec):", style="TLabel").pack(side="left")
        self._poll_var = tk.IntVar(value=self._config.global_config.poll_interval)
        poll_spin = ttk.Spinbox(settings_frame, from_=1, to=60,
                                textvariable=self._poll_var, width=5)
        poll_spin.pack(side="left", padx=(4, 20))

        ttk.Label(settings_frame, text="Cooldown (sec):", style="TLabel").pack(side="left")
        self._cooldown_var = tk.IntVar(value=self._config.global_config.cooldown)
        cool_spin = ttk.Spinbox(settings_frame, from_=0, to=300,
                                textvariable=self._cooldown_var, width=5)
        cool_spin.pack(side="left", padx=(4, 20))

        # ── Buttons ──
        btn_frame = ttk.Frame(main, style="TFrame")
        btn_frame.pack(fill="x", pady=(16, 0))

        ttk.Button(btn_frame, text="Rescan", command=self._rescan,
                   style="TButton").pack(side="left")
        ttk.Button(btn_frame, text="Select All", command=self._select_all,
                   style="TButton").pack(side="left", padx=(8, 0))
        ttk.Button(btn_frame, text="Deselect All", command=self._deselect_all,
                   style="TButton").pack(side="left", padx=(8, 0))

        save_text = "Save & Start Monitoring" if self._standalone else "Save"
        ttk.Button(btn_frame, text=save_text, command=self._save,
                   style="Accent.TButton").pack(side="right")

    def _populate_apps(self) -> None:
        """Scan and populate the app list."""
        # Get currently running process names
        running: set[str] = set()
        try:
            for proc in psutil.process_iter(["name"]):
                name = proc.info.get("name")  # type: ignore[union-attr]
                if name:
                    running.add(name.lower())
        except Exception:
            pass

        # Build existing rules lookup
        existing: dict[str, Rule] = {}
        for rule in self._config.rules:
            existing[rule.process.lower()] = rule

        # Merge KNOWN_APPS with existing rules
        seen: set[str] = set()
        apps: list[tuple[str, str, Action, bool, bool]] = []  # name, proc, action, running, enabled

        # Existing rules first (user has already configured these)
        for rule in self._config.rules:
            key = rule.process.lower()
            if key not in seen:
                seen.add(key)
                apps.append((
                    rule.name,
                    rule.process,
                    rule.action,
                    key in running,
                    rule.enabled,
                ))

        # Then KNOWN_APPS that are running but not yet configured
        for proc_name, display_name, default_action in KNOWN_APPS:
            key = proc_name.lower()
            if key not in seen and key in running:
                seen.add(key)
                apps.append((display_name, proc_name, default_action, True, False))

        # Sort: enabled first, then running, then alphabetical
        apps.sort(key=lambda x: (not x[4], not x[3], x[0].lower()))

        # Clear existing rows
        for widget in list(self._inner.winfo_children()):
            info = widget.grid_info()
            if info and int(info.get("row", 0)) >= 2:
                widget.destroy()
        self._app_rows.clear()

        # Create rows
        for i, (name, process, action, is_running, enabled) in enumerate(apps):
            row = _AppRow(
                parent=self._inner,
                row=i + 2,  # +2 for header and separator
                name=name,
                process=process,
                action=action,
                is_running=is_running,
                enabled=enabled,
            )
            self._app_rows.append(row)

        if not apps:
            ttk.Label(
                self._inner,
                text="No applications detected. Try running some apps and click Rescan.",
                style="CardDim.TLabel",
            ).grid(row=2, column=0, columnspan=5, pady=20)

    def _rescan(self) -> None:
        """Re-scan running processes and refresh the list."""
        self._populate_apps()

    def _select_all(self) -> None:
        for row in self._app_rows:
            row.enabled_var.set(True)

    def _deselect_all(self) -> None:
        for row in self._app_rows:
            row.enabled_var.set(False)

    def _save(self) -> None:
        """Save configuration and optionally start monitoring."""
        rules = [row.to_rule() for row in self._app_rows]

        self._config.rules = rules
        self._config.global_config.poll_interval = self._poll_var.get()
        self._config.global_config.cooldown = self._cooldown_var.get()

        path = cfg_mod.save(self._config)
        enabled_count = sum(1 for r in rules if r.enabled)
        logger.info("Saved %d rules (%d enabled) to %s", len(rules), enabled_count, path)

        if self._on_save:
            self._on_save(self._config)

        if self._root:
            self._root.destroy()
            self._root = None

    def _on_close_standalone(self) -> None:
        """Handle window close in standalone mode — ask to save first."""
        if self._app_rows and any(r.enabled_var.get() for r in self._app_rows):
            if messagebox.askyesno("procawake", "Save settings before closing?"):
                self._save()
                return
        if self._root:
            self._root.destroy()
            self._root = None


def show_settings(config: Config | None = None, on_save: Callable[[Config], None] | None = None) -> None:
    """Show the settings window (blocking call)."""
    win = SettingsWindow(config=config, on_save=on_save, standalone=False)
    win.show()


def show_first_run(on_save: Callable[[Config], None] | None = None) -> None:
    """Show the first-run setup window (blocking, standalone mode)."""
    win = SettingsWindow(on_save=on_save, standalone=True)
    win.show()
