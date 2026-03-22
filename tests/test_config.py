"""Tests for config loading, saving, and manipulation."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from procawake.config import Config, GlobalConfig, Rule, add_rule, remove_rule, save, load
from procawake.constants import Action


def test_rule_roundtrip():
    """Rule should survive dict serialization."""
    rule = Rule(
        name="Test",
        process="test.exe",
        action=Action.DISPLAY,
        window_title=".*foo.*",
        cpu_above=5.0,
        require_foreground=True,
    )
    d = rule.to_dict()
    restored = Rule.from_dict(d)
    assert restored.name == rule.name
    assert restored.process == rule.process
    assert restored.action == rule.action
    assert restored.window_title == rule.window_title
    assert restored.cpu_above == rule.cpu_above
    assert restored.require_foreground == rule.require_foreground


def test_config_roundtrip():
    """Config should survive dict serialization."""
    cfg = Config(
        global_config=GlobalConfig(poll_interval=10, cooldown=60),
        rules=[
            Rule(name="App1", process="app1.exe", action=Action.BOTH),
            Rule(name="App2", process="app2.exe", action=Action.SYSTEM, enabled=False),
        ],
    )
    d = cfg.to_dict()
    restored = Config.from_dict(d)
    assert restored.version == cfg.version
    assert restored.global_config.poll_interval == 10
    assert restored.global_config.cooldown == 60
    assert len(restored.rules) == 2
    assert restored.rules[0].name == "App1"
    assert restored.rules[1].enabled is False


def test_save_and_load(tmp_path):
    """Config should save to TOML and load back identically."""
    cfg = Config(
        global_config=GlobalConfig(poll_interval=3),
        rules=[Rule(name="VLC", process="vlc.exe", action=Action.DISPLAY)],
    )
    config_file = tmp_path / "config.toml"
    with patch("procawake.config.config_path", return_value=config_file):
        save(cfg)
        loaded = load()
    assert loaded.global_config.poll_interval == 3
    assert len(loaded.rules) == 1
    assert loaded.rules[0].name == "VLC"


def test_add_rule_replaces_existing():
    """Adding a rule with the same name should replace it."""
    cfg = Config(rules=[Rule(name="App", process="old.exe")])
    new_rule = Rule(name="App", process="new.exe", action=Action.DISPLAY)
    cfg = add_rule(cfg, new_rule)
    assert len(cfg.rules) == 1
    assert cfg.rules[0].process == "new.exe"


def test_remove_rule():
    """Removing a rule by name should work."""
    cfg = Config(rules=[
        Rule(name="Keep", process="keep.exe"),
        Rule(name="Remove", process="remove.exe"),
    ])
    cfg = remove_rule(cfg, "Remove")
    assert len(cfg.rules) == 1
    assert cfg.rules[0].name == "Keep"


def test_get_rule_cooldown_uses_global():
    """Rule without per-rule cooldown should use global."""
    cfg = Config(global_config=GlobalConfig(cooldown=45))
    rule = Rule(name="Test", process="t.exe")
    assert cfg.get_rule_cooldown(rule) == 45


def test_get_rule_cooldown_uses_per_rule():
    """Rule with per-rule cooldown should override global."""
    cfg = Config(global_config=GlobalConfig(cooldown=45))
    rule = Rule(name="Test", process="t.exe", cooldown=10)
    assert cfg.get_rule_cooldown(rule) == 10


def test_load_missing_file(tmp_path):
    """Loading from a missing file should return defaults."""
    missing = tmp_path / "nonexistent.toml"
    with patch("procawake.config.config_path", return_value=missing):
        cfg = load()
    assert cfg.version == 1
    assert len(cfg.rules) == 0
