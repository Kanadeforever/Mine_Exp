<p align="center">
  <a href="./README_zh-CN.md">中文</a> | <strong>English</strong>
</p>

<h1 align="center">Mine Exp</h1>

<p align="center">
  <em>Save & restore Windows File Explorer window sessions with one click</em>
</p>
<p align="center">
  <em>Powered by DeepSeek V4</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7" alt="Windows" />
  <img src="https://img.shields.io/badge/GUI-PyQt6-41cd52" alt="PyQt6" />
</p>

---

## Overview

**Mine Exp** is a Windows system tray utility that **saves and restores File Explorer window sessions**. It remembers the path, position, and size of every open Explorer window, so you can pick up exactly where you left off — even after a reboot.

- Save all open Explorer windows as a named session
- Restore any session with a single click
- Quick save/restore via global hotkeys
- Auto-save on a configurable timer
- Multi-language support (lang.ini)

---

## Features

| Feature | Description |
|---------|-------------|
| **System Tray** | Right-click menu for all operations; runs quietly in the background |
| **Global Hotkeys** | Save (`Ctrl+Shift+F3`) and Quick Restore (`Ctrl+Shift+F1`) from anywhere |
| **Session Management** | Name, rename, delete, and browse sessions via a built-in dialog |
| **Auto Save** | Automatically detects window changes and saves periodically (configurable interval) |
| **Multi-language** | Built-in English, Simplified Chinese, and Japanese; hot-switchable at runtime |
| **Async Restore** | Non-blocking restoration with a live progress dialog |
| **Partial Restore** | Restore only selected windows from a session |

---

## Requirements

- **OS**: Windows 10 or Windows 11
- **Python**: 3.10 or later
- **Dependencies** (auto-installed):
  - `PyQt6` — GUI framework (system tray, dialogs)
  - `pywin32` — Windows COM interface (Shell.Application)
  - `ctypes` — Win32 API (global hotkeys, window positioning)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Kanadeforever/Mine_Exp.git
cd Mine_Exp

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

> **Quick start**: Double-click `run.bat` to launch directly (sets up environment automatically).

**\* Recommand** : Use a Python virtual environment.

---

## Usage

### System Tray

Right-click the tray icon to access all features:

| Menu Item | Action |
|-----------|--------|
| **Save Session** | Save current Explorer windows as a new session |
| **Quick Restore** | Restore the most recently saved/manual session |
| **Manage Sessions** | Open the session management dialog |
| **Settings** | Configure hotkeys, auto-save, language, and logging |
| **Exit** | Quit the application |

### Global Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+F3` | Save current session |
| `Ctrl+Shift+F1` | Quick restore last session |

> Hotkeys are fully customizable in Settings.

### Auto Save

When enabled (default), the app checks every **5 minutes** for window changes. If changes are detected, a new snapshot is saved automatically. Older auto-saves are pruned to keep only the latest **20** (both configurable in Settings).

### Console

Start using the `--console` parameter.

---

## Project Structure

```
MineExp/
├── main.py                     # Application entry point
├── config.ini                  # User configuration file
├── requirements.txt            # Python dependencies
├── run.bat                     # Quick-launch script
├── build_onedir.bat            # PyInstaller build (directory mode)
├── build_onefile.bat           # PyInstaller build (single-file mode)
│
├── app/                        # Core application package
│   ├── __init__.py             # Package declaration (v1.0.0)
│   ├── app_core.py             # Core: tray, hotkeys, auto-save, orchestration
│   ├── session_manager.py      # Explorer window enumeration & session I/O
│   ├── manage_dialog.py        # Session management dialog
│   ├── settings_dialog.py      # Settings dialog (3 tabs)
│   ├── hotkey_manager.py       # Win32 global hotkey registration
│   ├── config_manager.py       # INI config reading/writing
│   ├── language_manager.py     # i18n translation manager
│   ├── logger.py               # Logging system (file + console)
│   ├── common.py               # Utility functions
│   ├── constants.py            # Centralized constants
│   └── resources/              # Icons & resources
│
├── language/                   # Translation files
│   ├── en_US.ini               # English
│   ├── zh_CN.ini               # Simplified Chinese
│   └── ja_JP.ini               # Japanese
│
├── tests/                      # Unit tests (pytest)
│   ├── conftest.py             # Shared fixtures
│   ├── test_config_manager.py  # 10 tests
│   ├── test_hotkey_manager.py  # 5 tests
│   ├── test_language_manager.py# 6 tests
│   └── test_session_manager.py # 15 tests
│
├── Session/                    # Saved session JSON files (auto-created)
└── logs/                       # Log files (auto-created)
```

---

## Multi-language Support

Three languages are built in:

| Language | File | Code |
|----------|------|------|
| Simplified Chinese | `language/zh_CN.ini` | zh_CN |
| English | `language/en_US.ini` | en_US |
| Japanese | `language/ja_JP.ini` | ja_JP |

To switch languages, go to **Settings → General** and select your preferred language. No restart required — the change takes effect immediately.

> To add a new language, simply create a `language/<code>.ini` file following the same key format, and it will be automatically detected.

---

## Building from Source

Build a standalone `.exe` with PyInstaller:

```bash
# One directory (faster first launch)
build_onedir.bat

# Single file (easier distribution)
build_onefile.bat
```

Both scripts use:
- `--noconsole` — no terminal window
- `--add-data` — bundles `language/` and `app/resources/`
- Custom icon from `app/resources/icon.ico`

---

## Running Tests

```bash
pytest tests/ -v
```

**36 test cases** covering:
- Config loading/saving (10)
- Hotkey validation (5)
- Language fallback & parameter substitution (6)
- Session create/list/delete/rename (15)

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.10+ | Main language |
| PyQt6 | GUI framework (tray, dialogs) |
| pywin32 | Windows COM (Shell.Application) |
| ctypes / Win32 API | Global hotkeys, window positioning |
| configparser | INI file parsing |
| pythoncom | COM threading initialization |
| PyInstaller | Application packaging |

---

## Acknowledgments

- DeepSeek — The existence that lends people wings
