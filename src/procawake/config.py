"""Configuration loading, saving, and validation.

Config file: %APPDATA%/procawake/config.toml
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from procawake.constants import (
    APP_NAME,
    CONFIG_VERSION,
    DEFAULT_COOLDOWN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_POLL_INTERVAL,
    Action,
)

logger = logging.getLogger(__name__)


def config_dir() -> Path:
    """Return the config directory: %APPDATA%/procawake/."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def config_path() -> Path:
    return config_dir() / "config.toml"


def log_path() -> Path:
    return config_dir() / "procawake.log"


@dataclass
class Rule:
    """A single process-watch rule."""

    name: str
    process: str
    action: Action = Action.BOTH
    enabled: bool = True
    window_title: str = ""
    cpu_above: float = 0.0
    cooldown: int | None = None  # None = use global default
    require_foreground: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "process": self.process,
            "action": str(self.action),
            "enabled": self.enabled,
        }
        if self.window_title:
            d["window_title"] = self.window_title
        if self.cpu_above > 0:
            d["cpu_above"] = self.cpu_above
        if self.cooldown is not None:
            d["cooldown"] = self.cooldown
        if self.require_foreground:
            d["require_foreground"] = self.require_foreground
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Rule:
        return cls(
            name=d["name"],
            process=d["process"],
            action=Action(d.get("action", "both")),
            enabled=d.get("enabled", True),
            window_title=d.get("window_title", ""),
            cpu_above=float(d.get("cpu_above", 0.0)),
            cooldown=d.get("cooldown"),
            require_foreground=d.get("require_foreground", False),
        )


@dataclass
class GlobalConfig:
    """Global settings."""

    poll_interval: int = DEFAULT_POLL_INTERVAL
    cooldown: int = DEFAULT_COOLDOWN
    start_minimized: bool = True
    run_at_login: bool = False
    log_level: str = DEFAULT_LOG_LEVEL
    log_file: str = ""


@dataclass
class Config:
    """Full application config."""

    version: int = CONFIG_VERSION
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    rules: list[Rule] = field(default_factory=list)

    def get_rule_cooldown(self, rule: Rule) -> int:
        """Return per-rule cooldown, falling back to global."""
        if rule.cooldown is not None:
            return rule.cooldown
        return self.global_config.cooldown

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "global": {
                "poll_interval": self.global_config.poll_interval,
                "cooldown": self.global_config.cooldown,
                "start_minimized": self.global_config.start_minimized,
                "run_at_login": self.global_config.run_at_login,
                "log_level": self.global_config.log_level,
                "log_file": self.global_config.log_file,
            },
            "rules": [r.to_dict() for r in self.rules],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Config:
        g = d.get("global", {})
        return cls(
            version=d.get("version", CONFIG_VERSION),
            global_config=GlobalConfig(
                poll_interval=g.get("poll_interval", DEFAULT_POLL_INTERVAL),
                cooldown=g.get("cooldown", DEFAULT_COOLDOWN),
                start_minimized=g.get("start_minimized", True),
                run_at_login=g.get("run_at_login", False),
                log_level=g.get("log_level", DEFAULT_LOG_LEVEL),
                log_file=g.get("log_file", ""),
            ),
            rules=[Rule.from_dict(r) for r in d.get("rules", [])],
        )


def load() -> Config:
    """Load config from disk. Returns default config if file doesn't exist."""
    path = config_path()
    if not path.exists():
        logger.info("No config found at %s, using defaults", path)
        return Config()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        cfg = Config.from_dict(data)
        logger.info("Loaded config from %s (%d rules)", path, len(cfg.rules))
        return cfg
    except Exception:
        logger.exception("Failed to load config from %s", path)
        return Config()


def save(cfg: Config) -> Path:
    """Save config to disk. Creates parent dirs if needed. Returns path."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(cfg.to_dict(), f)
    logger.info("Saved config to %s", path)
    return path


def add_rule(cfg: Config, rule: Rule) -> Config:
    """Add a rule (replaces existing with same name)."""
    cfg.rules = [r for r in cfg.rules if r.name != rule.name]
    cfg.rules.append(rule)
    return cfg


def remove_rule(cfg: Config, name: str) -> Config:
    """Remove a rule by name."""
    cfg.rules = [r for r in cfg.rules if r.name != name]
    return cfg
