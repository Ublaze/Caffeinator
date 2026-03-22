"""Command-line interface for procawake."""

from __future__ import annotations

import argparse
import os
import sys
import logging

from procawake import __version__
from procawake.constants import Action


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> None:
    """Start the tray application."""
    from procawake.app import main as app_main

    _setup_logging(args.log_level)
    app_main()


def cmd_status(args: argparse.Namespace) -> None:
    """Show current power request status."""
    from procawake.power import PowerManager
    from procawake import config as cfg_mod

    _setup_logging("WARNING")
    cfg = cfg_mod.load()
    pm = PowerManager()

    print(f"procawake v{__version__}")
    print(f"Backend: {pm.backend}")
    print(f"Config:  {cfg_mod.config_path()}")
    print(f"Rules:   {len(cfg.rules)} ({sum(1 for r in cfg.rules if r.enabled)} enabled)")
    print()
    print("--- powercfg /requests ---")
    print(pm.diagnose())


def cmd_scan(args: argparse.Namespace) -> None:
    """Auto-detect apps and suggest rules."""
    from procawake.scanner import AppScanner

    _setup_logging("WARNING")
    scanner = AppScanner()
    suggestions = scanner.suggest_rules()

    if not suggestions:
        print("No known applications detected.")
        return

    print(f"Found {len(suggestions)} application(s):\n")
    for rule in suggestions:
        status = "running" if _is_running(rule.process) else "installed"
        print(f"  [{status:>9}] {rule.name} ({rule.process}) -> {rule.action}")

    print(f"\nTo add a rule: procawake add <process.exe> --name \"App Name\"")


def _is_running(process_name: str) -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                return True
    except Exception:
        pass
    return False


def cmd_list(args: argparse.Namespace) -> None:
    """List all configured rules."""
    from procawake import config as cfg_mod

    cfg = cfg_mod.load()
    if not cfg.rules:
        print("No rules configured. Run 'procawake scan' to detect apps.")
        return

    print(f"{'Name':<25} {'Process':<20} {'Action':<10} {'Enabled'}")
    print("-" * 65)
    for r in cfg.rules:
        enabled = "yes" if r.enabled else "no"
        extras = []
        if r.window_title:
            extras.append(f"title=/{r.window_title}/")
        if r.cpu_above > 0:
            extras.append(f"cpu>{r.cpu_above}%")
        if r.require_foreground:
            extras.append("foreground")
        suffix = f"  ({', '.join(extras)})" if extras else ""
        print(f"  {r.name:<23} {r.process:<20} {r.action:<10} {enabled}{suffix}")


def cmd_add(args: argparse.Namespace) -> None:
    """Add a new rule."""
    from procawake import config as cfg_mod
    from procawake.config import Rule

    cfg = cfg_mod.load()
    name = args.name or args.process.replace(".exe", "").title()
    rule = Rule(
        name=name,
        process=args.process,
        action=Action(args.action),
        enabled=True,
        window_title=args.window_title or "",
        cpu_above=args.cpu_above or 0.0,
        require_foreground=args.foreground or False,
    )
    cfg = cfg_mod.add_rule(cfg, rule)
    path = cfg_mod.save(cfg)
    print(f"Added rule '{rule.name}' -> {rule.process} ({rule.action})")
    print(f"Config saved to {path}")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a rule by name."""
    from procawake import config as cfg_mod

    cfg = cfg_mod.load()
    before = len(cfg.rules)
    cfg = cfg_mod.remove_rule(cfg, args.name)
    if len(cfg.rules) == before:
        print(f"No rule named '{args.name}' found.")
        return
    cfg_mod.save(cfg)
    print(f"Removed rule '{args.name}'")


def cmd_enable(args: argparse.Namespace) -> None:
    """Enable a rule."""
    _toggle_rule(args.name, enabled=True)


def cmd_disable(args: argparse.Namespace) -> None:
    """Disable a rule."""
    _toggle_rule(args.name, enabled=False)


def _toggle_rule(name: str, enabled: bool) -> None:
    from procawake import config as cfg_mod

    cfg = cfg_mod.load()
    found = False
    for r in cfg.rules:
        if r.name == name:
            r.enabled = enabled
            found = True
            break
    if not found:
        print(f"No rule named '{name}' found.")
        return
    cfg_mod.save(cfg)
    state = "enabled" if enabled else "disabled"
    print(f"Rule '{name}' {state}")


def cmd_diagnose(args: argparse.Namespace) -> None:
    """Show power diagnostics."""
    from procawake.power import PowerManager

    print(f"procawake v{__version__}")
    pm = PowerManager()
    print(f"Power backend: {pm.backend}\n")
    print("--- powercfg /requests ---")
    print(pm.diagnose())


def cmd_config(args: argparse.Namespace) -> None:
    """Show or edit config."""
    from procawake import config as cfg_mod

    path = cfg_mod.config_path()
    if args.edit:
        if not path.exists():
            cfg_mod.save(cfg_mod.Config())
            print(f"Created default config at {path}")
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        print(f"Config path: {path}")
        if path.exists():
            print(f"File size:   {path.stat().st_size} bytes")
        else:
            print("(not yet created — run 'procawake scan' or 'procawake add' first)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procawake",
        description="Process-aware Windows sleep prevention",
    )
    parser.add_argument("-V", "--version", action="version", version=f"procawake {__version__}")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")

    sub = parser.add_subparsers(dest="command")

    # run
    sub.add_parser("run", help="Start the tray application")

    # status
    sub.add_parser("status", help="Show current status")

    # scan
    sub.add_parser("scan", help="Auto-detect applications")

    # list
    sub.add_parser("list", help="List configured rules")

    # add
    p_add = sub.add_parser("add", help="Add a monitoring rule")
    p_add.add_argument("process", help="Process name (e.g., code.exe)")
    p_add.add_argument("--name", help="Display name for the rule")
    p_add.add_argument("--action", default="both", choices=["display", "system", "both"])
    p_add.add_argument("--window-title", help="Regex to match window title")
    p_add.add_argument("--cpu-above", type=float, help="CPU%% threshold")
    p_add.add_argument("--foreground", action="store_true", help="Only when app has focus")

    # remove
    p_rm = sub.add_parser("remove", help="Remove a rule by name")
    p_rm.add_argument("name", help="Rule name to remove")

    # enable / disable
    p_en = sub.add_parser("enable", help="Enable a rule")
    p_en.add_argument("name", help="Rule name")
    p_dis = sub.add_parser("disable", help="Disable a rule")
    p_dis.add_argument("name", help="Rule name")

    # diagnose
    sub.add_parser("diagnose", help="Show power diagnostics")

    # config
    p_cfg = sub.add_parser("config", help="Show or edit config file")
    p_cfg.add_argument("--edit", action="store_true", help="Open config in default editor")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "status": cmd_status,
        "scan": cmd_scan,
        "list": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "diagnose": cmd_diagnose,
        "config": cmd_config,
    }

    if args.command is None:
        # Default to run
        args.command = "run"
        cmd_run(args)
    elif args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
