"""First-run application auto-detection.

Scans running processes and common install locations against a curated
list of apps that users commonly want to keep their screen alive for.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import psutil

from procawake.config import Rule
from procawake.constants import Action

logger = logging.getLogger(__name__)

# (process_name, display_name, default_action)
KNOWN_APPS: list[tuple[str, str, Action]] = [
    # IDEs & Editors
    ("code.exe", "VS Code", Action.SYSTEM),
    ("devenv.exe", "Visual Studio", Action.SYSTEM),
    ("idea64.exe", "IntelliJ IDEA", Action.SYSTEM),
    ("pycharm64.exe", "PyCharm", Action.SYSTEM),
    ("webstorm64.exe", "WebStorm", Action.SYSTEM),
    ("rider64.exe", "JetBrains Rider", Action.SYSTEM),
    ("sublime_text.exe", "Sublime Text", Action.SYSTEM),
    ("notepad++.exe", "Notepad++", Action.SYSTEM),

    # Build Tools & Terminals
    ("WindowsTerminal.exe", "Windows Terminal", Action.SYSTEM),
    ("pwsh.exe", "PowerShell 7", Action.SYSTEM),
    ("cargo.exe", "Rust Cargo", Action.SYSTEM),
    ("node.exe", "Node.js", Action.SYSTEM),
    ("python.exe", "Python", Action.SYSTEM),
    ("claude.exe", "Claude Code", Action.BOTH),

    # Video & Media
    ("vlc.exe", "VLC Media Player", Action.DISPLAY),
    ("mpv.exe", "mpv", Action.DISPLAY),
    ("mpc-hc64.exe", "MPC-HC", Action.DISPLAY),
    ("PotPlayerMini64.exe", "PotPlayer", Action.DISPLAY),
    ("spotify.exe", "Spotify", Action.SYSTEM),

    # Video Conferencing
    ("ms-teams.exe", "Microsoft Teams", Action.DISPLAY),
    ("Teams.exe", "Microsoft Teams (Classic)", Action.DISPLAY),
    ("Zoom.exe", "Zoom", Action.DISPLAY),
    ("slack.exe", "Slack", Action.DISPLAY),
    ("Discord.exe", "Discord", Action.DISPLAY),

    # Streaming & Recording
    ("obs64.exe", "OBS Studio", Action.DISPLAY),
    ("streamlabs.exe", "Streamlabs", Action.DISPLAY),

    # Remote Desktop
    ("mstsc.exe", "Remote Desktop", Action.DISPLAY),
    ("AnyDesk.exe", "AnyDesk", Action.DISPLAY),
    ("TeamViewer.exe", "TeamViewer", Action.DISPLAY),

    # Browsers (commonly used for video/presentations)
    ("chrome.exe", "Google Chrome", Action.DISPLAY),
    ("msedge.exe", "Microsoft Edge", Action.DISPLAY),
    ("firefox.exe", "Mozilla Firefox", Action.DISPLAY),
    ("brave.exe", "Brave Browser", Action.DISPLAY),

    # Productivity
    ("POWERPNT.EXE", "PowerPoint", Action.DISPLAY),
    ("Acrobat.exe", "Adobe Acrobat", Action.DISPLAY),

    # Gaming & GPU
    ("steam.exe", "Steam", Action.SYSTEM),
]


class AppScanner:
    """Detects commonly-monitored applications."""

    def scan_running(self) -> list[Rule]:
        """Check currently running processes against KNOWN_APPS."""
        running: set[str] = set()
        try:
            for proc in psutil.process_iter(["name"]):
                name = proc.info.get("name")  # type: ignore[union-attr]
                if name:
                    running.add(name.lower())
        except Exception:
            logger.exception("Error scanning processes")

        rules: list[Rule] = []
        for proc_name, display_name, action in KNOWN_APPS:
            if proc_name.lower() in running:
                rules.append(Rule(
                    name=display_name,
                    process=proc_name,
                    action=action,
                    enabled=False,  # User must opt-in
                ))
        return rules

    def scan_installed(self) -> list[Rule]:
        """Check common install locations for known apps."""
        search_dirs: list[Path] = []

        # Program Files directories
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            val = os.environ.get(env_var)
            if val:
                search_dirs.append(Path(val))

        # Start Menu
        appdata = os.environ.get("APPDATA")
        if appdata:
            search_dirs.append(
                Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )

        installed_exes: set[str] = set()
        for d in search_dirs:
            if not d.exists():
                continue
            try:
                # Only scan top 2 levels to avoid slow traversal
                for child in d.iterdir():
                    if child.is_file() and child.suffix.lower() == ".exe":
                        installed_exes.add(child.name.lower())
                    elif child.is_dir():
                        try:
                            for grandchild in child.iterdir():
                                if grandchild.is_file() and grandchild.suffix.lower() == ".exe":
                                    installed_exes.add(grandchild.name.lower())
                        except PermissionError:
                            continue
            except PermissionError:
                continue

        rules: list[Rule] = []
        for proc_name, display_name, action in KNOWN_APPS:
            if proc_name.lower() in installed_exes:
                rules.append(Rule(
                    name=display_name,
                    process=proc_name,
                    action=action,
                    enabled=False,
                ))
        return rules

    def suggest_rules(self) -> list[Rule]:
        """Combine running + installed, deduplicate, return suggestions."""
        running = self.scan_running()
        installed = self.scan_installed()

        seen: set[str] = set()
        combined: list[Rule] = []

        # Running apps first (higher priority)
        for rule in running:
            key = rule.process.lower()
            if key not in seen:
                seen.add(key)
                combined.append(rule)

        for rule in installed:
            key = rule.process.lower()
            if key not in seen:
                seen.add(key)
                combined.append(rule)

        logger.info("Scanner found %d suggestions (%d running, %d installed)",
                     len(combined), len(running), len(installed))
        return combined
