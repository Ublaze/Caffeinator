"""Build script — generates icon, PyInstaller exe, and optionally the Inno Setup installer.

Usage:
    python scripts/build.py              # Build exe only
    python scripts/build.py --installer  # Build exe + Inno Setup installer
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str], **kwargs) -> None:
    print(f"\n> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT), **kwargs)


def step_icon() -> None:
    print("\n=== Step 1: Generate icon ===")
    run([sys.executable, "scripts/generate_ico.py"])


def step_pyinstaller() -> None:
    print("\n=== Step 2: Build with PyInstaller ===")
    ico = ROOT / "assets" / "procawake.ico"

    # Update spec to include icon if it exists
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "procawake",
        "--clean",
    ]
    if ico.exists():
        cmd.extend(["--icon", str(ico)])

    # Add hidden imports
    for mod in [
        "procawake", "procawake.app", "procawake.cli", "procawake.config",
        "procawake.constants", "procawake.gui", "procawake.icons",
        "procawake.monitor", "procawake.power", "procawake.scanner",
        "procawake.tray", "pystray._win32",
    ]:
        cmd.extend(["--hidden-import", mod])

    cmd.append("src/procawake/__main__.py")
    run(cmd)

    exe = ROOT / "dist" / "procawake.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\nBuilt: {exe} ({size_mb:.1f} MB)")
    else:
        print("ERROR: procawake.exe not found in dist/")
        sys.exit(1)


def step_inno_setup() -> None:
    print("\n=== Step 3: Build installer with Inno Setup ===")

    # Find Inno Setup compiler
    iscc_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc = None
    for p in iscc_paths:
        if p.exists():
            iscc = p
            break

    # Also check PATH
    if iscc is None:
        iscc_which = shutil.which("ISCC")
        if iscc_which:
            iscc = Path(iscc_which)

    if iscc is None:
        print("WARNING: Inno Setup not found. Install from https://jrsoftware.org/issetup.php")
        print("Skipping installer build. The standalone exe is available at dist/procawake.exe")
        return

    run([str(iscc), "installer.iss"])

    output = ROOT / "installer_output"
    if output.exists():
        for f in output.glob("*.exe"):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"\nInstaller built: {f} ({size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build procawake distribution")
    parser.add_argument("--installer", action="store_true", help="Also build Inno Setup installer")
    parser.add_argument("--skip-icon", action="store_true", help="Skip icon generation")
    args = parser.parse_args()

    if not args.skip_icon:
        step_icon()

    step_pyinstaller()

    if args.installer:
        step_inno_setup()

    print("\n=== Build complete ===")
    print(f"  Standalone exe: dist/procawake.exe")
    if args.installer:
        print(f"  Installer:      installer_output/procawake-0.1.0-setup.exe")


if __name__ == "__main__":
    main()
