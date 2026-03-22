"""Win32 power management layer.

Provides two backends:
- Modern: PowerCreateRequest / PowerSetRequest / PowerClearRequest (Win7+)
- Legacy: SetThreadExecutionState (fallback)

Each rule gets an independent power request handle (modern) or contributes
to a combined bitmask (legacy). Reference-counted so multiple rules can
overlap safely.
"""

from __future__ import annotations

import atexit
import ctypes
import ctypes.wintypes
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from procawake.constants import (
    ES_CONTINUOUS,
    ES_DISPLAY_REQUIRED,
    ES_SYSTEM_REQUIRED,
    POWER_REQUEST_CONTEXT_SIMPLE_STRING,
    POWER_REQUEST_CONTEXT_VERSION,
    POWER_REQUEST_TYPE,
    REASON_CONTEXT,
    Action,
    PowerBackend,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value


def _action_to_flags(action: Action) -> int:
    """Convert an Action enum to SetThreadExecutionState flags."""
    flags = ES_CONTINUOUS
    if action in (Action.DISPLAY, Action.BOTH):
        flags |= ES_DISPLAY_REQUIRED
    if action in (Action.SYSTEM, Action.BOTH):
        flags |= ES_SYSTEM_REQUIRED
    return flags


def _action_to_request_types(action: Action) -> list[POWER_REQUEST_TYPE]:
    """Convert an Action enum to PowerRequestType values."""
    types: list[POWER_REQUEST_TYPE] = []
    if action in (Action.DISPLAY, Action.BOTH):
        types.append(POWER_REQUEST_TYPE.PowerRequestDisplayRequired)
    if action in (Action.SYSTEM, Action.BOTH):
        types.append(POWER_REQUEST_TYPE.PowerRequestSystemRequired)
    return types


@dataclass
class _ModernHandle:
    """Tracks a modern power request handle and which request types are set."""

    handle: int
    active_types: set[POWER_REQUEST_TYPE] = field(default_factory=set)


class PowerManager:
    """Manages power requests with reference counting.

    Thread-safe: all public methods acquire an internal lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._backend = self._detect_backend()
        self._session_locked = False

        # Modern backend state
        self._modern_handles: dict[str, _ModernHandle] = {}

        # Legacy backend state
        self._legacy_rules: dict[str, Action] = {}

        atexit.register(self.release_all)
        logger.info("PowerManager initialized with %s backend", self._backend)

    @property
    def backend(self) -> PowerBackend:
        return self._backend

    def _detect_backend(self) -> PowerBackend:
        """Try the modern API; fall back to legacy if unavailable."""
        try:
            # Probe PowerCreateRequest availability
            func = kernel32.PowerCreateRequest
            func.restype = ctypes.wintypes.HANDLE
            func.argtypes = [ctypes.POINTER(REASON_CONTEXT)]

            kernel32.PowerSetRequest.restype = ctypes.wintypes.BOOL
            kernel32.PowerSetRequest.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_int]

            kernel32.PowerClearRequest.restype = ctypes.wintypes.BOOL
            kernel32.PowerClearRequest.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_int]

            # Test creation
            ctx = REASON_CONTEXT()
            ctx.Version = POWER_REQUEST_CONTEXT_VERSION
            ctx.Flags = POWER_REQUEST_CONTEXT_SIMPLE_STRING
            ctx.SimpleReasonString = "procawake probe"
            handle = func(ctypes.byref(ctx))
            handle_val = handle if isinstance(handle, int) else handle.value  # type: ignore[union-attr]
            if handle_val == INVALID_HANDLE_VALUE:
                logger.warning("PowerCreateRequest returned INVALID_HANDLE_VALUE, using legacy")
                return PowerBackend.LEGACY
            kernel32.CloseHandle(handle)
            return PowerBackend.MODERN
        except (OSError, AttributeError):
            logger.warning("Modern power API not available, using legacy backend")
            return PowerBackend.LEGACY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_awake(self, rule_name: str, action: Action) -> None:
        """Create or update a power request for a rule. Idempotent."""
        with self._lock:
            if self._session_locked:
                logger.debug("Session locked — deferring request for %s", rule_name)
                # Store intent so we can activate on unlock
                if self._backend == PowerBackend.LEGACY:
                    self._legacy_rules[rule_name] = action
                return

            if self._backend == PowerBackend.MODERN:
                self._modern_request(rule_name, action)
            else:
                self._legacy_request(rule_name, action)

    def release(self, rule_name: str) -> None:
        """Release the power request for a rule. Idempotent."""
        with self._lock:
            if self._backend == PowerBackend.MODERN:
                self._modern_release(rule_name)
            else:
                self._legacy_release(rule_name)

    def release_all(self) -> None:
        """Release everything — called on shutdown."""
        with self._lock:
            if self._backend == PowerBackend.MODERN:
                for name in list(self._modern_handles):
                    self._modern_release(name)
            else:
                self._legacy_rules.clear()
                self._legacy_apply()
            logger.info("All power requests released")

    def get_active_rules(self) -> list[str]:
        """Return names of rules with active power requests."""
        with self._lock:
            if self._backend == PowerBackend.MODERN:
                return [n for n, h in self._modern_handles.items() if h.active_types]
            return list(self._legacy_rules)

    def on_session_lock(self) -> None:
        """Called when the Windows session is locked."""
        with self._lock:
            self._session_locked = True
            logger.info("Session locked — pausing display power requests")
            if self._backend == PowerBackend.MODERN:
                for name, mh in self._modern_handles.items():
                    for rt in list(mh.active_types):
                        if rt == POWER_REQUEST_TYPE.PowerRequestDisplayRequired:
                            kernel32.PowerClearRequest(mh.handle, int(rt))
                            mh.active_types.discard(rt)
                            logger.debug("Paused display request for %s", name)
            else:
                # Legacy: recompute without display flags
                self._legacy_apply(suppress_display=True)

    def on_session_unlock(self) -> None:
        """Called when the Windows session is unlocked."""
        with self._lock:
            self._session_locked = False
            logger.info("Session unlocked — resuming power requests")
            if self._backend == PowerBackend.MODERN:
                # Re-activate display requests for rules that should have them
                # We don't store the original action, so we rely on the caller
                # to re-call request_awake. The monitor loop will handle this
                # on the next tick.
                pass
            else:
                self._legacy_apply()

    # ------------------------------------------------------------------
    # Modern backend internals
    # ------------------------------------------------------------------

    def _modern_request(self, rule_name: str, action: Action) -> None:
        desired_types = set(_action_to_request_types(action))

        if rule_name in self._modern_handles:
            mh = self._modern_handles[rule_name]
            # Clear types no longer needed
            for rt in mh.active_types - desired_types:
                kernel32.PowerClearRequest(mh.handle, int(rt))
            # Set new types
            for rt in desired_types - mh.active_types:
                if not kernel32.PowerSetRequest(mh.handle, int(rt)):
                    logger.error("PowerSetRequest failed for %s type %s", rule_name, rt)
            mh.active_types = desired_types
        else:
            # Create new handle
            ctx = REASON_CONTEXT()
            ctx.Version = POWER_REQUEST_CONTEXT_VERSION
            ctx.Flags = POWER_REQUEST_CONTEXT_SIMPLE_STRING
            ctx.SimpleReasonString = f"procawake: {rule_name}"
            handle = kernel32.PowerCreateRequest(ctypes.byref(ctx))
            handle_val = handle if isinstance(handle, int) else handle.value
            if handle_val == INVALID_HANDLE_VALUE:
                logger.error("PowerCreateRequest failed for %s", rule_name)
                return
            mh = _ModernHandle(handle=handle, active_types=set())
            for rt in desired_types:
                if kernel32.PowerSetRequest(handle, int(rt)):
                    mh.active_types.add(rt)
                else:
                    logger.error("PowerSetRequest failed for %s type %s", rule_name, rt)
            self._modern_handles[rule_name] = mh
            logger.info("Power request created: %s → %s (modern)", rule_name, action)

    def _modern_release(self, rule_name: str) -> None:
        mh = self._modern_handles.pop(rule_name, None)
        if mh is None:
            return
        for rt in mh.active_types:
            kernel32.PowerClearRequest(mh.handle, int(rt))
        kernel32.CloseHandle(mh.handle)
        logger.info("Power request released: %s (modern)", rule_name)

    # ------------------------------------------------------------------
    # Legacy backend internals
    # ------------------------------------------------------------------

    def _legacy_request(self, rule_name: str, action: Action) -> None:
        self._legacy_rules[rule_name] = action
        self._legacy_apply()
        logger.info("Power request created: %s → %s (legacy)", rule_name, action)

    def _legacy_release(self, rule_name: str) -> None:
        if rule_name not in self._legacy_rules:
            return
        del self._legacy_rules[rule_name]
        self._legacy_apply()
        logger.info("Power request released: %s (legacy)", rule_name)

    def _legacy_apply(self, suppress_display: bool = False) -> None:
        """Recompute and set the combined execution state."""
        if not self._legacy_rules:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            return

        combined = ES_CONTINUOUS
        for action in self._legacy_rules.values():
            flags = _action_to_flags(action)
            if suppress_display:
                flags &= ~ES_DISPLAY_REQUIRED
            combined |= flags

        kernel32.SetThreadExecutionState(combined)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def diagnose() -> str:
        """Run powercfg /requests and return the output."""
        try:
            result = subprocess.run(
                ["powercfg", "/requests"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return f"powercfg failed (rc={result.returncode}):\n{result.stderr}"
            return result.stdout
        except FileNotFoundError:
            return "powercfg not found on PATH"
        except subprocess.TimeoutExpired:
            return "powercfg timed out"
        except OSError as e:
            return f"Error running powercfg: {e}"
