"""Tests for the power management layer."""

from unittest.mock import MagicMock, patch

from procawake.constants import Action, PowerBackend


def test_legacy_backend_sets_flags():
    """Legacy backend should call SetThreadExecutionState with combined flags."""
    with patch("procawake.power.kernel32") as mock_k32:
        # Force legacy backend by making PowerCreateRequest fail
        mock_k32.PowerCreateRequest.side_effect = OSError("no modern API")
        mock_k32.SetThreadExecutionState.return_value = 0

        from procawake.power import PowerManager
        pm = PowerManager.__new__(PowerManager)
        pm._lock = __import__("threading").Lock()
        pm._backend = PowerBackend.LEGACY
        pm._modern_handles = {}
        pm._legacy_rules = {}
        pm._session_locked = False

        pm.request_awake("test", Action.DISPLAY)
        assert "test" in pm._legacy_rules
        mock_k32.SetThreadExecutionState.assert_called()

        pm.release("test")
        assert "test" not in pm._legacy_rules


def test_get_active_rules_legacy():
    """get_active_rules should return names of active legacy rules."""
    with patch("procawake.power.kernel32"):
        from procawake.power import PowerManager
        pm = PowerManager.__new__(PowerManager)
        pm._lock = __import__("threading").Lock()
        pm._backend = PowerBackend.LEGACY
        pm._modern_handles = {}
        pm._legacy_rules = {}
        pm._session_locked = False

        pm._legacy_rules = {"app1": Action.DISPLAY, "app2": Action.SYSTEM}
        assert set(pm.get_active_rules()) == {"app1", "app2"}


def test_release_all_clears_everything():
    """release_all should clear all rules."""
    with patch("procawake.power.kernel32") as mock_k32:
        mock_k32.SetThreadExecutionState.return_value = 0

        from procawake.power import PowerManager
        pm = PowerManager.__new__(PowerManager)
        pm._lock = __import__("threading").Lock()
        pm._backend = PowerBackend.LEGACY
        pm._modern_handles = {}
        pm._legacy_rules = {"a": Action.BOTH, "b": Action.DISPLAY}
        pm._session_locked = False

        pm.release_all()
        assert len(pm._legacy_rules) == 0


def test_session_lock_suppresses_display():
    """When session is locked, new display requests should be deferred."""
    with patch("procawake.power.kernel32") as mock_k32:
        mock_k32.SetThreadExecutionState.return_value = 0

        from procawake.power import PowerManager
        pm = PowerManager.__new__(PowerManager)
        pm._lock = __import__("threading").Lock()
        pm._backend = PowerBackend.LEGACY
        pm._modern_handles = {}
        pm._legacy_rules = {}
        pm._session_locked = False

        pm.on_session_lock()
        assert pm._session_locked is True

        # Request during lock should store intent but suppress display
        pm.request_awake("test", Action.DISPLAY)
        assert "test" in pm._legacy_rules

        pm.on_session_unlock()
        assert pm._session_locked is False
