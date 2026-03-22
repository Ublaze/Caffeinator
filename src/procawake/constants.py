"""Win32 constants and enums for power management."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from enum import IntEnum, StrEnum

# ---------------------------------------------------------------------------
# SetThreadExecutionState flags (kernel32)
# ---------------------------------------------------------------------------
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

# ---------------------------------------------------------------------------
# PowerCreateRequest / PowerSetRequest enums (kernel32)
# ---------------------------------------------------------------------------

class POWER_REQUEST_TYPE(IntEnum):
    PowerRequestDisplayRequired = 0
    PowerRequestSystemRequired = 1
    PowerRequestAwayModeRequired = 2
    PowerRequestExecutionRequired = 3  # Windows 8+


# REASON_CONTEXT for PowerCreateRequest
POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x1


class REASON_CONTEXT(ctypes.Structure):
    """REASON_CONTEXT structure for PowerCreateRequest.

    Simplified: we only use the SimpleReasonString variant.
    """

    _fields_ = [
        ("Version", ctypes.wintypes.ULONG),
        ("Flags", ctypes.wintypes.DWORD),
        ("SimpleReasonString", ctypes.wintypes.LPWSTR),
    ]


# ---------------------------------------------------------------------------
# Window session change messages (user32 / wtsapi32)
# ---------------------------------------------------------------------------
WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218

WTS_SESSION_LOCK = 7
WTS_SESSION_UNLOCK = 8

NOTIFY_FOR_THIS_SESSION = 0

# ---------------------------------------------------------------------------
# Application enums
# ---------------------------------------------------------------------------

class Action(StrEnum):
    """What to keep alive when a rule triggers."""

    DISPLAY = "display"
    SYSTEM = "system"
    BOTH = "both"


class RuleState(StrEnum):
    """State machine for a monitored rule."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    COOLDOWN = "cooldown"


class PowerBackend(StrEnum):
    """Which Win32 API backend is in use."""

    MODERN = "modern"       # PowerCreateRequest / PowerSetRequest
    LEGACY = "legacy"       # SetThreadExecutionState


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_POLL_INTERVAL = 5       # seconds
DEFAULT_COOLDOWN = 30           # seconds
DEFAULT_LOG_LEVEL = "INFO"
CONFIG_VERSION = 1
APP_NAME = "procawake"
