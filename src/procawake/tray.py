"""System tray UI using pystray.

Provides a Windows system tray icon with dynamic menu showing active rules,
pause/resume toggle, config access, and exit.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import pystray
from pystray import MenuItem as Item

from procawake import __version__, config as cfg_mod
from procawake.icons import (
    create_active_icon,
    create_idle_icon,
    create_error_icon,
    create_paused_icon,
)

if TYPE_CHECKING:
    from procawake.app import App

logger = logging.getLogger(__name__)


class TrayUI:
    """System tray icon with dynamic context menu."""

    def __init__(self, app: App) -> None:
        self._app = app
        self._icons = {
            "active": create_active_icon(),
            "idle": create_idle_icon(),
            "error": create_error_icon(),
            "paused": create_paused_icon(),
        }
        self._icon = pystray.Icon(
            name="procawake",
            icon=self._icons["idle"],
            title=f"procawake v{__version__} — idle",
            menu=self._build_menu(),
        )
        self._update_lock = threading.Lock()

    def run(self) -> None:
        """Start the tray icon — blocks on the main thread."""
        logger.info("Tray UI starting")
        self._icon.run(setup=self._on_setup)

    def stop(self) -> None:
        """Stop the tray icon."""
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        try:
            self._icon.stop()
        except Exception:
            pass

    def on_rule_change(self, rule_name: str, is_active: bool) -> None:
        """Called by App when a rule transitions. Updates icon + tooltip."""
        self._refresh()
        if is_active:
            self._notify(f"Keeping awake: {rule_name}")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            Item(
                lambda _: self._header_text(),
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            Item(
                "Active Rules",
                pystray.Menu(lambda: self._active_rules_items()),
                visible=lambda _: bool(self._app.get_active_rules()),
            ),
            pystray.Menu.SEPARATOR,
            Item(
                lambda _: "Resume" if self._app.paused else "Pause",
                self._on_toggle_pause,
            ),
            Item(
                "Settings...",
                self._on_settings,
            ),
            pystray.Menu.SEPARATOR,
            Item(
                "Run at Login",
                self._on_toggle_startup,
                checked=lambda _: self._app.config.global_config.run_at_login,
            ),
            pystray.Menu.SEPARATOR,
            Item("Exit", self._on_exit),
        )

    def _header_text(self) -> str:
        active = self._app.get_active_rules()
        if self._app.paused:
            return f"procawake v{__version__} — PAUSED"
        if active:
            return f"procawake v{__version__} — {len(active)} active"
        return f"procawake v{__version__} — idle"

    def _active_rules_items(self) -> list[Item]:
        """Dynamic submenu showing which rules are currently active."""
        active = self._app.get_active_rules()
        if not active:
            return [Item("(none)", None, enabled=False)]
        return [Item(f"  {name}", None, enabled=False) for name in active]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        # Sync icon with current state — the monitor may have already
        # detected active rules before the tray was wired up
        self._refresh()
        # Start a periodic sync so the icon stays accurate even if
        # a callback was missed (e.g. during tray startup race)
        self._start_periodic_refresh()

    def _on_toggle_pause(self, icon: pystray.Icon, item: Item) -> None:
        paused = self._app.toggle_pause()
        self._refresh()
        self._notify("Monitoring paused" if paused else "Monitoring resumed")

    def _on_settings(self, icon: pystray.Icon, item: Item) -> None:
        self._app.open_settings()

    def _on_toggle_startup(self, icon: pystray.Icon, item: Item) -> None:
        cfg = self._app.config
        cfg.global_config.run_at_login = not cfg.global_config.run_at_login
        cfg_mod.save(cfg)
        self._set_startup_registry(cfg.global_config.run_at_login)
        state = "enabled" if cfg.global_config.run_at_login else "disabled"
        self._notify(f"Run at login {state}")

    def _on_exit(self, icon: pystray.Icon, item: Item) -> None:
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        self._app.stop()
        icon.stop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _start_periodic_refresh(self) -> None:
        """Periodically sync the tray icon with actual power state.

        This catches any state changes that were missed due to timing
        (e.g. monitor fired before tray was registered as callback target).
        Runs every 10 seconds in a daemon thread.
        """
        def _loop() -> None:
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=10)
                if not self._stop_event.is_set():
                    try:
                        self._refresh()
                    except Exception:
                        pass
        self._stop_event = threading.Event()
        t = threading.Thread(target=_loop, daemon=True, name="procawake-tray-sync")
        t.start()

    def _refresh(self) -> None:
        """Update icon and tooltip based on current state."""
        with self._update_lock:
            if self._app.paused:
                self._icon.icon = self._icons["paused"]
                self._icon.title = f"procawake — PAUSED"
            elif self._app.get_active_rules():
                self._icon.icon = self._icons["active"]
                count = len(self._app.get_active_rules())
                self._icon.title = f"procawake — {count} rule(s) active"
            else:
                self._icon.icon = self._icons["idle"]
                self._icon.title = f"procawake — idle"

    def _notify(self, message: str) -> None:
        """Show a Windows toast notification."""
        try:
            self._icon.notify(message, title="procawake")
        except Exception:
            logger.debug("Notification failed: %s", message)

    @staticmethod
    def _set_startup_registry(enable: bool) -> None:
        """Add/remove HKCU Run registry entry for auto-start at login."""
        import winreg
        import sys

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                # Use pythonw.exe for no-console launch
                exe = sys.executable
                if exe.endswith("python.exe"):
                    exe = exe.replace("python.exe", "pythonw.exe")
                cmd = f'"{exe}" -m procawake run'
                winreg.SetValueEx(key, "procawake", 0, winreg.REG_SZ, cmd)
                logger.info("Added startup registry entry: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, "procawake")
                    logger.info("Removed startup registry entry")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError:
            logger.exception("Failed to modify startup registry")
