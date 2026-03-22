"""Application orchestrator — wires config, monitor, power, and tray together."""

from __future__ import annotations

import logging
import signal
import sys
import threading

from procawake import config as cfg_mod
from procawake.config import Config
from procawake.constants import Action
from procawake.monitor import ProcessMonitor
from procawake.power import PowerManager
from procawake.scanner import AppScanner

logger = logging.getLogger(__name__)


class App:
    """Central coordinator for procawake."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or cfg_mod.load()
        self._power = PowerManager()
        self._monitor = ProcessMonitor(
            config=self._config,
            on_change=self._on_rule_change,
        )
        self._rule_actions: dict[str, Action] = {}
        self._paused = False
        self._lock = threading.Lock()
        self._tray: object | None = None  # Set by tray.py if running with UI

        # Build rule action lookup
        for rule in self._config.rules:
            self._rule_actions[rule.name] = rule.action

    @property
    def config(self) -> Config:
        return self._config

    @property
    def power(self) -> PowerManager:
        return self._power

    @property
    def monitor(self) -> ProcessMonitor:
        return self._monitor

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        """Start the monitor. Does NOT start the tray (caller handles that)."""
        # First-run: if no rules, offer to scan
        if not self._config.rules:
            self._first_run()

        self._monitor.start()
        logger.info(
            "procawake started (backend=%s, rules=%d, interval=%ds)",
            self._power.backend,
            len(self._config.rules),
            self._config.global_config.poll_interval,
        )

    def stop(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down procawake...")
        self._monitor.stop()
        self._power.release_all()

    def toggle_pause(self) -> bool:
        """Toggle pause state. Returns new paused state."""
        with self._lock:
            self._paused = not self._paused
            if self._paused:
                self._power.release_all()
                logger.info("Monitoring paused")
            else:
                logger.info("Monitoring resumed")
            return self._paused

    def reload_config(self) -> None:
        """Reload config from disk."""
        self._config = cfg_mod.load()
        self._monitor.config = self._config
        self._rule_actions.clear()
        for rule in self._config.rules:
            self._rule_actions[rule.name] = rule.action
        logger.info("Config reloaded (%d rules)", len(self._config.rules))

    def get_active_rules(self) -> list[str]:
        """Return names of rules with active power requests."""
        return self._power.get_active_rules()

    def on_session_lock(self) -> None:
        self._power.on_session_lock()

    def on_session_unlock(self) -> None:
        self._power.on_session_unlock()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_rule_change(self, rule_name: str, is_active: bool) -> None:
        """Callback from ProcessMonitor when a rule's state changes."""
        with self._lock:
            if self._paused:
                return

            if is_active:
                action = self._rule_actions.get(rule_name, Action.BOTH)
                self._power.request_awake(rule_name, action)
            else:
                self._power.release(rule_name)

            # Notify tray if available
            if self._tray and hasattr(self._tray, "on_rule_change"):
                try:
                    self._tray.on_rule_change(rule_name, is_active)  # type: ignore[union-attr]
                except Exception:
                    logger.debug("Failed to notify tray", exc_info=True)

    def open_settings(self) -> None:
        """Open the settings GUI in a background thread."""
        def _run_gui() -> None:
            from procawake.gui import show_settings
            show_settings(config=self._config, on_save=self._on_settings_saved)
        threading.Thread(target=_run_gui, daemon=True, name="procawake-settings").start()

    def _on_settings_saved(self, new_config: Config) -> None:
        """Called when the GUI saves a new config."""
        self._config = new_config
        self._monitor.config = new_config
        self._rule_actions.clear()
        for rule in new_config.rules:
            self._rule_actions[rule.name] = rule.action
        logger.info("Settings saved via GUI (%d rules)", len(new_config.rules))
        # Notify tray to refresh
        if self._tray and hasattr(self._tray, "_refresh"):
            try:
                self._tray._refresh()  # type: ignore[union-attr]
            except Exception:
                pass

    def _first_run(self) -> None:
        """Show the setup GUI on first run so the user can select apps."""
        logger.info("First run detected — showing setup GUI...")
        from procawake.gui import SettingsWindow
        saved = False

        def _on_save(cfg: Config) -> None:
            nonlocal saved
            saved = True
            self._config = cfg
            self._monitor.config = cfg
            self._rule_actions.clear()
            for rule in cfg.rules:
                self._rule_actions[rule.name] = rule.action

        win = SettingsWindow(on_save=_on_save, standalone=True)
        win.show()  # Blocks until window is closed

        if not saved:
            # User closed without saving — write empty config so we don't ask again
            cfg_mod.save(self._config)


def main() -> None:
    """Entry point for the GUI application (procawake-tray)."""
    from procawake.config import load as load_config

    config = load_config()

    # Set up logging
    log_level = getattr(logging, config.global_config.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []

    if config.global_config.log_file:
        handlers.append(logging.FileHandler(config.global_config.log_file))
    else:
        # Log to default location
        log_file = cfg_mod.log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_file)))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    app = App(config=config)

    # Handle signals
    def _signal_handler(sig: int, frame: object) -> None:
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Create tray BEFORE starting monitor so callbacks can reach it
    try:
        from procawake.tray import TrayUI
        tray = TrayUI(app)
        app._tray = tray
    except ImportError:
        tray = None
        logger.warning("pystray not available — running headless")

    app.start()

    # Run tray UI on main thread (blocks) or wait headless
    try:
        if tray:
            tray.run()  # Blocks on main thread
        else:
            # Headless — block on stop event
            stop_event = threading.Event()
            try:
                stop_event.wait()
            except KeyboardInterrupt:
                pass
    finally:
        app.stop()
