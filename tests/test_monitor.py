"""Tests for the process monitor."""

from unittest.mock import MagicMock, patch

from procawake.config import Config, GlobalConfig, Rule
from procawake.constants import Action, RuleState
from procawake.monitor import ProcessMonitor


def _make_config(*rules: Rule) -> Config:
    return Config(
        global_config=GlobalConfig(poll_interval=1, cooldown=0),
        rules=list(rules),
    )


def _make_proc_info(name: str, pid: int = 1000, cpu: float = 0.0) -> MagicMock:
    proc = MagicMock()
    proc.pid = pid
    proc.info = {"name": name, "pid": pid, "cpu_percent": cpu}
    return proc


def test_rule_activates_when_process_found():
    """Rule should fire on_change(name, True) when process appears."""
    changes: list[tuple[str, bool]] = []
    rule = Rule(name="Test", process="test.exe", action=Action.BOTH, enabled=True)
    cfg = _make_config(rule)
    monitor = ProcessMonitor(config=cfg, on_change=lambda n, a: changes.append((n, a)))

    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = [_make_proc_info("test.exe")]
        monitor._poll_once()

    assert ("Test", True) in changes


def test_rule_deactivates_when_process_gone():
    """Rule should fire on_change(name, False) after process exits and cooldown."""
    changes: list[tuple[str, bool]] = []
    rule = Rule(name="Test", process="test.exe", action=Action.BOTH, enabled=True)
    cfg = _make_config(rule)
    monitor = ProcessMonitor(config=cfg, on_change=lambda n, a: changes.append((n, a)))

    # First tick: process present
    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = [_make_proc_info("test.exe")]
        monitor._poll_once()

    assert ("Test", True) in changes
    changes.clear()

    # Second tick: process gone (cooldown=0 so immediate deactivation)
    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = []
        monitor._poll_once()  # enters cooldown
        # Advance time past cooldown (it's 0 in our config)
        for tracker in monitor._trackers.values():
            tracker.cooldown_until = 0
        monitor._poll_once()  # should deactivate

    assert ("Test", False) in changes


def test_disabled_rule_ignored():
    """Disabled rules should not be evaluated."""
    changes: list[tuple[str, bool]] = []
    rule = Rule(name="Disabled", process="test.exe", action=Action.BOTH, enabled=False)
    cfg = _make_config(rule)
    monitor = ProcessMonitor(config=cfg, on_change=lambda n, a: changes.append((n, a)))

    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = [_make_proc_info("test.exe")]
        monitor._poll_once()

    assert len(changes) == 0


def test_cpu_threshold_filters():
    """Rule with cpu_above should only trigger when CPU exceeds threshold."""
    changes: list[tuple[str, bool]] = []
    rule = Rule(name="CPU", process="build.exe", action=Action.SYSTEM, enabled=True, cpu_above=10.0)
    cfg = _make_config(rule)
    monitor = ProcessMonitor(config=cfg, on_change=lambda n, a: changes.append((n, a)))

    # Process running but CPU too low
    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = [_make_proc_info("build.exe", cpu=2.0)]
        monitor._poll_once()
    assert len(changes) == 0

    # CPU exceeds threshold
    with patch("psutil.process_iter") as mock_iter:
        mock_iter.return_value = [_make_proc_info("build.exe", cpu=25.0)]
        monitor._poll_once()
    assert ("CPU", True) in changes
