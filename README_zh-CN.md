<p align="center">
  <strong>中文</strong>
  &nbsp;|&nbsp;
  <a href="./README.md">English</a>
</p>

<h1 align="center">Mine Exp</h1>

<p align="center">
  <em>快捷键保存与恢复 Windows 资源管理器窗口会话</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7" alt="Windows" />
  <img src="https://img.shields.io/badge/GUI-PyQt6-41cd52" alt="PyQt6" />
</p>

---

## 概述

**Mine Exp** 是一款 Windows 系统托盘工具，用于**保存和恢复文件资源管理器窗口的会话状态**。它会记住每个打开的资源管理器窗口的路径、位置和大小，让你可以随时回到之前的工作状态——即使重启电脑后也能一键恢复。

- 将当前所有资源管理器窗口保存为一个命名会话
- 一键恢复任意已保存会话
- 全局热键快速保存/恢复
- 可配置的自动保存定时器
- 多语言支持（语言文件ini）

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **系统托盘** | 右键菜单执行所有操作，静默运行于后台 |
| **全局热键** | 随时随地保存（`Ctrl+Shift+F3`）和恢复（`Ctrl+Shift+F1`） |
| **会话管理** | 内置对话框：命名、重命名、删除、浏览会话 |
| **自动保存** | 自动检测窗口变化并定期保存（可配置间隔和保留数量） |
| **多语言** | 内置简体中文、英文、日文，运行时即时切换 |
| **异步恢复** | 非阻塞恢复 + 实时进度对话框 |
| **部分恢复** | 仅恢复会话中的部分窗口 |

---

## 系统要求

- **操作系统**：Windows 10 或 Windows 11
- **Python**：3.10 或更高版本
- **依赖库**（自动安装）：
  - `PyQt6` — GUI 框架（系统托盘、对话框）
  - `pywin32` — Windows COM 接口（Shell.Application）
  - `ctypes` — Win32 API（全局热键、窗口定位）

---

## 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Kanadeforever/Mine_Exp.git
cd Mine_Exp

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

> **快速启动**：直接双击 `run.bat` 即可运行（自动配置环境）。

---

## 使用指南

### 系统托盘

右键点击托盘图标访问所有功能：

| 菜单项 | 功能 |
|--------|------|
| **保存会话** | 将当前资源管理器窗口保存为新会话 |
| **快速恢复** | 恢复最近一次手动/自动保存的会话 |
| **管理会话** | 打开会话管理对话框 |
| **设置** | 配置热键、自动保存、语言和日志 |
| **退出** | 退出应用 |

### 全局热键

| 热键 | 功能 |
|------|------|
| `Ctrl+Shift+F3` | 保存当前会话 |
| `Ctrl+Shift+F1` | 快速恢复上次会话 |

> 热键可在设置中完全自定义。

### 自动保存

启用后（默认开启），应用每 **5 分钟** 检测一次窗口变化。检测到变化时自动保存快照。旧快照会自动清理，仅保留最近 **20 条**（两者均可设置中配置）。

### 控制台

使用 `--console` 参数启动。

---

## 项目结构

```
MineExp/
├── main.py                     # 应用入口
├── config.ini                  # 用户配置文件
├── requirements.txt            # Python 依赖
├── run.bat                     # 快速启动脚本
├── build_onedir.bat            # PyInstaller 打包（目录模式）
├── build_onefile.bat           # PyInstaller 打包（单文件模式）
│
├── app/                        # 核心应用包
│   ├── __init__.py             # 包声明（v1.0.0）
│   ├── app_core.py             # 核心：托盘、热键、自动保存、调度
│   ├── session_manager.py      # 窗口枚举与会话读写
│   ├── manage_dialog.py        # 会话管理对话框
│   ├── settings_dialog.py      # 设置对话框（3 个标签页）
│   ├── hotkey_manager.py       # Win32 全局热键注册
│   ├── config_manager.py       # INI 配置读写
│   ├── language_manager.py     # i18n 翻译管理器
│   ├── logger.py               # 日志系统（文件 + 控制台）
│   ├── common.py               # 公共工具函数
│   ├── constants.py            # 全局常量
│   └── resources/              # 图标资源
│
├── language/                   # 翻译文件
│   ├── en_US.ini               # 英文
│   ├── zh_CN.ini               # 简体中文
│   └── ja_JP.ini               # 日文
│
├── tests/                      # 单元测试（pytest）
│   ├── conftest.py             # 共享 fixture
│   ├── test_config_manager.py  # 10 项测试
│   ├── test_hotkey_manager.py  # 5 项测试
│   ├── test_language_manager.py# 6 项测试
│   └── test_session_manager.py # 15 项测试
│
├── Session/                    # 保存的会话 JSON 文件（自动创建）
└── logs/                       # 日志文件（自动创建）
```

---

## 多语言支持

内置三种语言：

| 语言 | 文件 | 代码 |
|------|------|------|
| 简体中文 | `language/zh_CN.ini` | zh_CN |
| English | `language/en_US.ini` | en_US |
| 日本語 | `language/ja_JP.ini` | ja_JP |

切换语言：进入 **设置 → 常规** 选择所需语言。无需重启，更改立即生效。

> 如需添加新语言，只需按照相同格式创建 `language/<代码>.ini` 文件，应用会自动识别。

---

## 构建打包

使用 PyInstaller 打包为独立 `.exe`：

```bash
# 目录模式（首次启动更快）
build_onedir.bat

# 单文件模式（便于分发）
build_onefile.bat
```

两个脚本均包含：
- `--noconsole` — 隐藏控制台窗口
- `--add-data` — 打包 `language/` 和 `app/resources/`
- 自定义图标 `app/resources/icon.ico`

---

## 运行测试

```bash
pytest tests/ -v
```

共 **36 项测试用例**，覆盖：
- 配置加载/保存（10 项）
- 热键验证（5 项）
- 语言回退与参数替换（6 项）
- 会话创建/列表/删除/重命名（15 项）

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| PyQt6 | GUI 框架（托盘、对话框） |
| pywin32 | Windows COM（Shell.Application） |
| ctypes / Win32 API | 全局热键、窗口定位 |
| configparser | INI 文件解析 |
| pythoncom | COM 多线程初始化 |
| PyInstaller | 应用打包分发 |
