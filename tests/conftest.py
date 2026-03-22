"""Shared test fixtures for procawake."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_kernel32(monkeypatch):
    """Mock kernel32 Win32 API calls."""
    mock = MagicMock()
    mock.PowerCreateRequest.return_value = 12345  # Fake handle
    mock.PowerSetRequest.return_value = True
    mock.PowerClearRequest.return_value = True
    mock.CloseHandle.return_value = True
    mock.SetThreadExecutionState.return_value = 0
    return mock


@pytest.fixture
def sample_config():
    """Return a sample Config for testing."""
    from procawake.config import Config, GlobalConfig, Rule
    from procawake.constants import Action

    return Config(
        global_config=GlobalConfig(poll_interval=1, cooldown=2),
        rules=[
            Rule(name="Test App", process="test.exe", action=Action.BOTH, enabled=True),
            Rule(name="Disabled App", process="disabled.exe", action=Action.DISPLAY, enabled=False),
            Rule(name="CPU App", process="cpu.exe", action=Action.SYSTEM, enabled=True, cpu_above=10.0),
        ],
    )
