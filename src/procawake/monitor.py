"""Process monitor — polls running processes and evaluates rules.

Uses psutil for process scanning and ctypes for Win32 window enumeration.
Fires callbacks only on state changes (diff-based).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

import psutil

from procawake.constants import RuleState

if TYPE_CHECKING:
    from procawake.config import Config, Rule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Win32 window enumeration (pure ctypes, no pywin32)
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32  # type: ignore[attr-defined]

EnumWindows = user32.EnumWindows
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
IsWindowVisible = user32.IsWindowVisible
GetForegroundWindow = user32.GetForegroundWindow

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _get_window_titles_for_pid(pid: int) -> list[str]:
    """Return visible window titles belonging to a given PID."""
    titles: list[str] = []

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if not IsWindowVisible(hwnd):
            return True
        tid_pid = ctypes.wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(tid_pid))
        if tid_pid.value != pid:
            return True
        length = GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            if buf.value:
                titles.append(buf.value)
        return True

    try:
        EnumWindows(callback, 0)
    except OSError:
        pass
    return titles


def _get_foreground_pid() -> int | None:
    """Return the PID of the foreground window, or None."""
    hwnd = GetForegroundWindow()
    if not hwnd:
        return None
    pid = ctypes.wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value if pid.value else None


# ---------------------------------------------------------------------------
# Rule state tracker
# ---------------------------------------------------------------------------

@dataclass
class _RuleTracker:
    """Tracks the state machine for a single rule."""

    rule_name: str
    state: RuleState = RuleState.INACTIVE
    cooldown_until: float = 0.0


# ---------------------------------------------------------------------------
# ProcessMonitor
# ---------------------------------------------------------------------------

class ProcessMonitor:
    """Polls running processes and evaluates rules against them.

    Calls `on_change(rule_name, is_active)` only when a rule transitions
    between active and inactive (after cooldown expires).
    """

    def __init__(
        self,
        config: Config,
        on_change: Callable[[str, bool], None],
    ) -> None:
        self._config = config
        self._on_change = on_change
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._trackers: dict[str, _RuleTracker] = {}
        self._cpu_primed: set[int] = set()  # PIDs we've called cpu_percent on

    @property
    def config(self) -> Config:
        return self._config

    @config.setter
    def config(self, value: Config) -> None:
        self._config = value

    def start(self) -> None:
        """Start polling in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="procawake-monitor")
        self._thread.start()
        logger.info("Monitor started (interval=%ds)", self._config.global_config.poll_interval)

    def stop(self) -> None:
        """Signal the polling thread to stop and wait."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Monitor stopped")

    def get_states(self) -> dict[str, RuleState]:
        """Return current state of all tracked rules."""
        return {name: t.state for name, t in self._trackers.items()}

    def _poll_loop(self) -> None:
        """Main polling loop — runs in background thread."""
        # Prime CPU percentages on first tick
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    proc.cpu_percent()
                    self._cpu_primed.add(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            logger.debug("CPU priming pass failed (non-fatal)")

        while not self._stop_event.wait(timeout=self._config.global_config.poll_interval):
            try:
                self._poll_once()
            except Exception:
                logger.exception("Error in poll cycle")

    def _poll_once(self) -> None:
        """Single poll: snapshot processes, evaluate rules, fire callbacks."""
        now = time.monotonic()
        enabled_rules = [r for r in self._config.rules if r.enabled]

        if not enabled_rules:
            return

        # Build process name → list[Process] mapping (single pass)
        proc_map: dict[str, list[psutil.Process]] = {}
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                name = proc.info.get("name")  # type: ignore[union-attr]
                if name:
                    proc_map.setdefault(name.lower(), []).append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Evaluate each rule
        for rule in enabled_rules:
            tracker = self._trackers.setdefault(
                rule.name, _RuleTracker(rule_name=rule.name)
            )
            matches = self._evaluate_rule(rule, proc_map)
            self._update_tracker(tracker, rule, matches, now)

        # Clean up trackers for removed rules
        active_names = {r.name for r in enabled_rules}
        for name in list(self._trackers):
            if name not in active_names:
                tracker = self._trackers.pop(name)
                if tracker.state in (RuleState.ACTIVE, RuleState.COOLDOWN):
                    self._on_change(name, False)

    def _evaluate_rule(
        self,
        rule: Rule,
        proc_map: dict[str, list[psutil.Process]],
    ) -> bool:
        """Check if a rule's criteria are met."""
        procs = proc_map.get(rule.process.lower(), [])
        if not procs:
            return False

        for proc in procs:
            try:
                # CPU threshold check
                if rule.cpu_above > 0:
                    cpu = proc.info.get("cpu_percent", 0.0)  # type: ignore[union-attr]
                    if cpu is None or cpu < rule.cpu_above:
                        continue

                # Window title regex check
                if rule.window_title:
                    titles = _get_window_titles_for_pid(proc.pid)
                    if not any(re.search(rule.window_title, t, re.IGNORECASE) for t in titles):
                        continue

                # Foreground check
                if rule.require_foreground:
                    fg_pid = _get_foreground_pid()
                    if fg_pid != proc.pid:
                        continue

                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def _update_tracker(
        self,
        tracker: _RuleTracker,
        rule: Rule,
        matches: bool,
        now: float,
    ) -> None:
        """Update state machine and fire callbacks on transitions."""
        cooldown_secs = self._config.get_rule_cooldown(rule)

        if tracker.state == RuleState.INACTIVE:
            if matches:
                tracker.state = RuleState.ACTIVE
                logger.info("Rule activated: %s", rule.name)
                self._on_change(rule.name, True)

        elif tracker.state == RuleState.ACTIVE:
            if not matches:
                tracker.state = RuleState.COOLDOWN
                tracker.cooldown_until = now + cooldown_secs
                logger.debug("Rule entering cooldown: %s (%.0fs)", rule.name, cooldown_secs)

        elif tracker.state == RuleState.COOLDOWN:
            if matches:
                # App came back during cooldown
                tracker.state = RuleState.ACTIVE
                logger.debug("Rule re-activated during cooldown: %s", rule.name)
            elif now >= tracker.cooldown_until:
                # Cooldown expired, truly inactive
                tracker.state = RuleState.INACTIVE
                logger.info("Rule deactivated: %s", rule.name)
                self._on_change(rule.name, False)
