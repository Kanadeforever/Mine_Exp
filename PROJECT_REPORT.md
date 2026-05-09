# Mine Exp — 项目分析报告

> 生成日期：2026-05-09  
> 最近更新：2026-05-10（修正行数、语言、测试、配置等多项统计）
> 报告中排除了 `legacy/` 目录下的所有内容。

---

## 一、项目概述

**Mine Exp** 是一个 Windows 系统托盘应用程序，用于**保存和恢复文件资源管理器（Explorer）窗口的会话状态**。它允许用户记录当前所有打开的资源管理器窗口（路径、位置、大小），并在后续任意时刻一键恢复。

- **版本**：1.0.0
- **许可证**：未明确指定
- **语言**：Python 3.10+
- **UI 框架**：PyQt6
- **平台**：Windows（依赖 Win32 API 和 COM 接口）

---

## 二、项目结构

```
explorerStorage/
├── main.py                  # 应用入口
├── requirements.txt         # Python 依赖
├── requirements-dev.txt     # 开发依赖（pytest 等）
├── build_onedir.bat         # PyInstaller 打包（onedir 模式）
├── build_onefile.bat        # PyInstaller 打包（onefile 模式）
├── run.bat                  # 开发/调试启动脚本
│
├── app/                     # 核心应用包
│   ├── __init__.py          # 包声明，版本号 1.0.0
│   ├── app_core.py          # 【核心】托盘 + 热键 + 自动保存 + 会话调度（519 行）
│   ├── session_manager.py   # 【核心】Explorer 窗口枚举/保存/恢复（499 行）
│   ├── manage_dialog.py     # 会话管理对话框（556 行）
│   ├── settings_dialog.py   # 设置对话框（255 行）
│   ├── hotkey_manager.py    # Win32 全局热键管理器（139 行）
│   ├── config_manager.py    # INI 配置读写 + 打包资源释放（109 行）
│   ├── language_manager.py  # 多语言翻译管理器（33 行）
│   ├── logger.py            # 日志系统（156 行）
│   ├── common.py            # 公共工具函数（46 行）
│   ├── constants.py         # 全局常量（40 行）
│   └── resources/           # 图标等资源文件
│
├── language/                # 多语言翻译文件
│   ├── en_US.ini            # 英文（6 个模块，72 行）
│   ├── zh_CN.ini            # 中文简体（6 个模块，72 行）
│   └── ja_JP.ini            # 日文（6 个模块，72 行）
│
├── tests/                   # 单元测试（pytest）
│   ├── README.md            # 测试文档
│   ├── __init__.py
│   ├── conftest.py          # 共享 fixture
│   ├── test_config_manager.py   # 10 项
│   ├── test_hotkey_manager.py   # 5 项
│   ├── test_language_manager.py # 6 项
│   └── test_session_manager.py  # 24 项
│
└── legacy/                  # 【已排除】历史文档
```

> 注：`config.ini` 不随仓库提交，首次运行由程序自动生成。

---

## 三、技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| PyQt6 6.11.0 | GUI 框架（系统托盘、对话框） |
| pywin32 311 | Windows COM 接口（Shell.Application） |
| ctypes / Win32 API | 全局热键注册（RegisterHotKey）、窗口操作（SetWindowPos） |
| configparser | INI 文件解析 |
| pythoncom | COM 多线程初始化 |
| PyInstaller | 应用打包分发 |

### 外部依赖（requirements.txt）

```
pywin32==311
PyQt6==6.11.0
```

---

## 四、架构与模块详解

### 4.1 入口：`main.py`（35 行）

- 创建 `QApplication`，设置 `setQuitOnLastWindowClosed(False)` 实现无主窗口运行
- 尝试加载 `app/resources/icon.png` 作为应用图标
- 实例化 `AppCore` 启动系统托盘和所有功能

### 4.2 核心：`app/app_core.py`（519 行）

**职责**：应用的心脏，负责所有功能的协调。

| 子系统 | 说明 |
|--------|------|
| **系统托盘** | 右键菜单：保存会话 / 恢复最新 / 管理会话 / 设置 / 退出 |
| **全局热键** | 默认 `Ctrl+Shift+F3`（保存）、`Ctrl+Shift+F1`（快速恢复） |
| **异步恢复** | `RestoreWorker` / `RestorePartialWorker`（QThread）实现恢复不阻塞 UI |
| **自动保存** | 定时检测窗口变化，自动保存并清理旧数据（可配置间隔和保留数） |
| **设置热切换** | 临时注销热键 → 打开设置对话框 → 重新注册热键 + 语言热切换 |

**关键流程**：
1. 启动 → 加载配置 → 初始化语言管理器 → 创建隐藏 QWidget → 安装托盘 → 注册热键 → 安装原生事件过滤器 → 显示启动通知
2. 保存会话：`get_open_windows()` → 写入 JSON 文件
3. 恢复会话：QThread 异步 → `restore_session()` → 进度对话框 → 轮询等待 HWND → `SetWindowPos` 恢复位置

### 4.3 会话管理：`app/session_manager.py`（499 行）

**职责**：与 Windows Explorer 直接交互，替代了原有的 5 个 PowerShell 脚本。

**核心 API**：

| 函数 | 对应旧脚本 | 说明 |
|------|-----------|------|
| `get_open_windows()` | Get-ExplorerSessions.ps1 | 枚举所有 Explorer 窗口（路径、位置、大小） |
| `save_session()` | Save-Session.ps1 | 保存当前窗口状态到 JSON 文件 |
| `restore_session()` | Restore-Session.ps1 | 恢复整个会话（轮询等待 HWND，坐标 clamp） |
| `list_sessions()` | List-Sessions.ps1 | 列出所有已保存会话 |
| `delete_session()` | Delete-Session.ps1 | 删除指定会话 |
| `get_session_windows()` | — | 获取会话内的窗口列表 |
| `restore_windows_from_session()` | — | 恢复会话中的部分窗口 |
| `rename_session()` | — | 重命名会话 |
| `delete_window_from_session()` | — | 从会话中移除指定窗口 |
| `update_window_path()` | — | 更新会话中某个窗口的路径 |

**关键技术细节**：
- 使用 `win32com.client.Dispatch("Shell.Application")` 获取 Shell COM 对象
- 恢复时通过 `_wait_for_window_hwnd()` 轮询等待窗口 HWND 创建完成（超时 5 秒）
- 坐标 clamp 到虚拟桌面范围，确保窗口至少有 200×150 像素可见
- 所有线程访问 COM 前需调用 `pythoncom.CoInitialize()`

### 4.4 会话管理对话框：`app/manage_dialog.py`（556 行）

**两级层级设计**：

| 层级 | 内容 | 操作 |
|------|------|------|
| **第一层**（会话组列表） | 所有 JSON 会话组 | 恢复（单选）、进入（双击/按钮）、重命名、删除、打开文件夹 |
| **第二层**（窗口条目） | 会话内的窗口路径列表 | 恢复（多选）、返回上级、编辑路径、删除窗口 |

**快捷键支持**：Delete（删除）、F2（重命名/编辑路径）、Enter（恢复）、Ctrl+A（全选）、双击进入/返回/恢复。

### 4.5 设置对话框：`app/settings_dialog.py`（255 行）

**三个标签页结构**：

| 标签 | 功能 |
|------|------|
| **常规（General）** | 语言选择（自动扫描 language/ 目录的 .ini 文件）、自动保存配置（启用/关闭、间隔、最大保留数） |
| **热键（Hotkeys）** | 保存会话热键、快速恢复热键的捕获设置（`HotkeyLineEdit` 组件） |
| **日志（Logging）** | 启用/禁用日志文件输出、最大历史日志条目数配置 |

**热键捕获**：自定义 `HotkeyLineEdit`（继承 QLineEdit），点击进入捕获模式，拦截按键事件，生成人读字符串（如 `Ctrl+Shift+S`）。

### 4.6 全局热键管理器：`app/hotkey_manager.py`（139 行）

- 封装 `RegisterHotKey` / `UnregisterHotKey` Win32 API
- 支持 `Ctrl` / `Shift` / `Alt` / `Win` 修饰键组合
- `MOD_NOREPEAT = 0x4000` 防止重复触发
- `WinHotkeyFilter` 继承 `QAbstractNativeEventFilter` 捕获 `WM_HOTKEY` 消息并分发回调
- 热键字符串解析：`"Ctrl+Shift+S"` → 修饰位掩码 `0x0002 | 0x0004` + 虚拟键码 `0x53`

### 4.7 配置管理器：`app/config_manager.py`（109 行）

- 默认配置：`zh_CN` 语言，`Ctrl+Shift+S` 保存，`Ctrl+Shift+R` 恢复，自动保存启用，间隔 5 分钟，最多保留 20 个，日志启用，日志最大 20 条
- 支持 PyInstaller 打包环境：`init_resources()` 在首次运行时将 `language/` 和 `app/resources/` 释放到程序目录
- `save_config()` 使用继承自 `configparser.ConfigParser` 的自定义 `_IniParser` 类进行写入，保留 key 原始大小写
- `load_config()` 支持 [General]、[Hotkeys]、[AutoSave]、[Logging] 四个节的读取

### 4.8 多语言管理：`app/language_manager.py`（33 行）

- 从 INI 文件按模块加载翻译键值对
- `t(module, key, *args)` 方法支持 `%1`、`%2` 参数替换
- 语言文件不存在时自动回退到 `zh_CN.ini`
- 翻译键缺失时返回原始 key

### 4.9 日志系统：`app/logger.py`（156 行）

- 日志文件路径：`BASE_DIR/logs/explorerStorage-{timestamp}.log`（按启动时间戳生成文件名）
- 格式：`时间 | 级别 | 模块 | 消息`
- **运行时配置**：`configure_logging()` 可动态启用/禁用文件输出并调整最大保留日志数
- **自动清理**：模块初始化时和配置更新时均会清理超出最大保留数的旧日志文件
- 仅在非打包模式（`sys.frozen` 为 False）输出到控制台
- 使用标准 `logger.info()` / `logger.warning()` / `logger.error()`，部分路径仍保留 `logger.debug()` 调用用于调试

### 4.10 公共工具：`app/common.py`（46 行）

| 函数 | 说明 |
|------|------|
| `get_base_dir()` | 获取程序所在目录（脚本模式为项目根目录，打包模式为 exe 所在目录） |
| `read_ini()` | 读取 INI 文件，自动检测 BOM（UTF-8 / UTF-8-SIG / UTF-16 LE / UTF-16 BE），保留 key 原始大小写 |

### 4.11 常量：`app/constants.py`（40 行）

集中管理所有魔术数字，包括：
- 虚拟桌面边界（GetSystemMetrics 索引）
- 窗口恢复参数（超时 5s、轮询间隔 50ms、最小可见尺寸 200×150）
- 通知持续时间（普通 3s、错误 5s）
- 自动保存参数（默认间隔 5 分钟、最多 20 个、范围限制 1-120 分钟 / 1-999 个）
- 日志参数（默认最大 20 条、范围 5-200 条）

---

## 五、配置说明

### config.ini 结构

```ini
[General]
Language=zh_CN

[Hotkeys]
SaveSession=Ctrl+Shift+F3
QuickRestore=Ctrl+Shift+F1

[AutoSave]
Enabled=true
IntervalMinutes=5
MaxCount=20

[Logging]
Enabled=true
MaxEntries=20
```

### 配置默认值（当文件不存在时）

| 键 | 默认值 | 说明 |
|----|--------|------|
| Language | zh_CN | 界面语言 |
| SaveSession | Ctrl+Shift+S | 保存会话全局热键 |
| QuickRestore | Ctrl+Shift+R | 快速恢复全局热键 |
| AutoSaveEnabled | true | 是否启用自动保存 |
| AutoSaveInterval | 5 | 自动保存间隔（分钟） |
| AutoSaveMaxCount | 20 | 最多保留的自动保存会话数 |
| LogEnabled | true | 是否启用日志文件输出 |
| LogMaxEntries | 20 | 最多保留的日志文件数 |

> 注：`config.ini` 中的实际值可能与默认值不同（例如热键已改为 `Ctrl+Shift+F3/F1`），具体以文件内容为准。

---

## 六、多语言系统

三种语言文件各有 **6 个模块**，分布在 `en_US.ini`、`zh_CN.ini` 和 `ja_JP.ini` 中（各 **72 行**）：

| 模块 | 用途 |
|------|------|
| `[Main]` | 主操作消息（保存/恢复提示） |
| `[Tray]` | 系统托盘菜单文本 |
| `[General]` | 通用 UI 文本（成功/错误/信息/取消） |
| `[Settings]` | 设置对话框文本 |
| `[ManageSessions]` | 会话管理对话框文本 |
| `[AutoSave]` | 自动保存相关文本 |

翻译查找机制：`LanguageManager.t(module, key, *args)` → 在 `[module]` 节查找 `key` → 替换 `%1` `%2` 等参数 → 未找到则返回 key 原文。

---

## 七、测试体系

**框架**：pytest

**总数**：45 项测试用例

| 测试文件 | 用例数 | 测试内容 |
|----------|--------|----------|
| `test_config_manager.py` | 10 | 编码检测（4）、INI 读取（4）、配置保存/加载闭环（2） |
| `test_hotkey_manager.py` | 5 | 热键验证：合法组合（5）、单键拒绝（5）、非法键（3）、修饰符映射表完整性（1）、虚拟键码表完整性（1） |
| `test_language_manager.py` | 6 | 翻译加载/回退/参数替换（6） |
| `test_session_manager.py` | 24 | 会话名格式（1）、存在判断（2）、保存（2）、列表（2）、删除（2）、重命名（4）、获取最新（2）、获取窗口列表（3）、从会话中删除窗口（3）、更新窗口路径（3） |

**隔离机制**：
- 所有测试使用 `tmp_path` 临时目录
- `conftest.py` 通过 `monkeypatch` 重定向 `SESSION_DIR`、`CONFIG_FILE`
- 测试完成后自动清理

---

## 八、构建与部署

### 构建方式

| 脚本 | 模式 | 说明 |
|------|------|------|
| `build_onedir.bat` | `--onedir` | 生成文件夹结构，首次启动速度较快 |
| `build_onefile.bat` | `--onefile` | 生成单个 exe，便于分发 |

### PyInstaller 配置

```
--noconsole              # 隐藏控制台窗口
--add-data "language;language"
--add-data "app/resources;app/resources"
--icon "app/resources/icon.ico"
```

### 首次运行初始化

- 打包模式：`config_manager.init_resources()` 自动释放 `language/` 和 `app/resources/` 到程序目录
- `Session/` 目录和 `logs/` 目录在首次使用时自动创建

---

## 九、数据流与关键流程

### 会话保存流程

```
用户触发（托盘菜单/全局热键）
       │
       ▼
app_core.save_session()
       │
       ▼
session_manager.get_open_windows()
       │
       ├── Init COM
       ├── Shell.Application → shell.Windows()
       ├── 过滤非 Explorer 窗口
       └── 返回 [{Path, Left, Top, Width, Height}, ...]
       │
       ▼
session_manager.save_session(name)
       │
       ├── 序列化为 JSON
       ├── 写入 Session/{name}.json
       └── 返回窗口数
       │
       ▼
托盘通知 + 日志
```

### 会话恢复流程

```
用户触发（托盘菜单/全局热键）
       │
       ▼
app_core._restore(name)
       │
       ├── 创建 QProgressDialog（进度对话框）
       ├── 启动 RestoreWorker（QThread）
       │
       ▼
RestoreWorker.run()
       │
       ▼
session_manager.restore_session(name)
       │
       ├── 读取 JSON 文件
       ├── Init COM
       ├── 对每个窗口：
       │   ├── shell.Open(path)      # 打开文件夹
       │   ├── _wait_for_window_hwnd()  # 轮询等待 HWND
       │   └── SetWindowPos(Left, Top, Width, Height)  # 恢复位置
       └── 返回 (成功数, 失败数)
       │
       ▼
app_core._on_restore_done()
       │
       ├── 关闭进度对话框
       ├── 托盘通知结果
       └── 日志记录
```

### 自动保存流程

```
QTimer 定时触发（默认 5 分钟）
       │
       ▼
app_core._auto_save()
       │
       ├── 获取当前窗口快照（JSON）
       ├── 与上次快照比较
       │   ├── 无变化 → 跳过
       │   └── 有变化 → 自动保存
       │
       ├── 保存为 auto_{timestamp}.json
       └── 清理旧自动保存文件（保留最新 MaxCount 个）
```

---

## 十、代码质量评价

### 优点

1. **架构清晰**：模块职责分明，依赖方向单一（common.py 无应用内依赖，避免循环导入）
2. **错误处理完善**：几乎所有异常路径都做了 try/except + 日志记录
3. **多线程安全**：使用 QThread 进行异步恢复，COM 在线程内正确初始化
4. **配置热切换**：语言和热键可在运行时立即生效，无需重启
5. **测试覆盖充分**：45 项单元测试覆盖核心逻辑，使用 tmp_path 隔离
6. **多语言支持**：key-based 翻译 + 参数替换
7. **代码文档齐全**：每个文件包含模块级别 docstring，关键逻辑有注释
8. **常量集中管理**：魔术数字统一在 constants.py 中定义

### 潜在改进点

1. **自动保存快照占用内存**：每次快照全量序列化所有窗口信息到 JSON 字符串，窗口较多时可能占用较多内存
2. **热键冲突检测**：注册热键失败时仅打印警告，未能提供可视化引导用户修改
3. **COM 资源释放**：`_init_com()` 未配对调用 `CoUninitialize()`（但 PythonCOM 会自动管理）
4. **配置文件格式**：`save_config()` 使用自定义 `_IniParser`（继承 configparser），可考虑保留注释
5. **进度对话框取消**：取消恢复时调用 `requestInterruption()`，但工作线程内的循环未检查 `isInterruptionRequested()`
6. **manage_dialog.py 的 556 行**：该类作为 QDialog 偏大，可考虑拆分为两个视图类（会话组视图 + 窗口条目视图）

---

## 十一、项目总览统计

| 指标 | 数值 |
|------|------|
| 源码文件（app/） | 11 个 |
| 总代码行数（app/） | ~2,354 行 |
| 测试文件 | 4 个 + conftest.py |
| 测试用例 | 45 项（配置 10 + 热键 5 + 语言 6 + 会话 24） |
| 翻译文件 | 3 种语言（各 6 个模块 / 72 行） |
| 外部依赖 | 2 个（PyQt6==6.11.0, pywin32==311） |
| 构建脚本 | 2 个（onedir + onefile） |
| 启动脚本 | 1 个（run.bat） |
| 排除目录 | legacy/（3 个历史文档文件） |