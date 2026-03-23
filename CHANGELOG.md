# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-23

### Added

- Per-app monitoring rules with display, system, or both actions
- Settings GUI for scanning and selecting running applications
- System tray with color-coded coffee cup icon (idle / active / paused)
- Native Win32 power API (`PowerCreateRequest`) — visible in `powercfg /requests`
- Session-aware monitoring — pauses on screen lock
- 30-second cooldown to prevent rapid on/off during app restarts
- Auto-detect for 35+ common applications (IDEs, media players, meeting tools)
- Window title matching with regex support
- CPU threshold triggering
- Foreground-only option
- Full CLI: `run`, `status`, `scan`, `list`, `add`, `remove`, `enable`, `disable`, `diagnose`, `config`
- Standalone `.exe` build via PyInstaller
- Windows installer build via Inno Setup

### Fixed

- Tray icon stuck on idle when monitored apps are already running at launch

[0.1.0]: https://github.com/Ublaze/Caffeinator/releases/tag/v0.1.0
