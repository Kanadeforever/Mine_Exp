# Mine Exp — 项目分析报告

**生成日期：** 2026-05-28

---

## 1. 项目概述

Mine Exp 是一个 Windows 桌面工具，用于保存和恢复文件资源管理器（Explorer）窗口的状态。通过系统托盘常驻运行，支持全局热键快速操作。

| 属性 | 值 |
|------|-----|
| 语言 | Python 3.10+ |
| GUI | PyQt6 |
| Windows COM | pywin32（Shell.Application） |
| 打包 | PyInstaller（单文件 exe，~40MB） |
| 测试 | pytest（45 项用例） |
| 许可 | 无 |

---

## 2. 架构

```
main.py                          # 入口点
app/
  app_core.py                    # 核心控制器（托盘 + 热键 + 自动保存）
  session_manager.py             # Explorer 会话 CRUD 引擎
  hotkey_manager.py              # Win32 全局热键注册
  config_manager.py              # config.ini 读写
  language_manager.py            # i18n 多语言
  settings_dialog.py             # 设置 UI
  manage_dialog.py               # 会话管理 UI
  logger.py                      # 日志系统
  constants.py                   # 常量定义
  common.py                      # 共享工具
  resources/icon.ico, icon.png   # 应用图标
language/
  zh_CN.ini, en_US.ini, ja_JP.ini   # 翻译文件（69 键/文件）
tests/                           # 45 项 pytest 用例
dist/MineExp.exe                 # 编译产物
```

**数据流：**

```
用户操作/热键 → AppCore → SessionManager → Shell.Application COM
                                    ↓
                              Session/*.json
```

---

## 3. 功能清单

| 功能 | 说明 |
|------|------|
| 保存会话 | 扫描所有 Explorer 窗口，保存路径+位置+尺寸到 JSON |
| 恢复会话 | 重新打开窗口并恢复位置/尺寸 |
| 快速恢复 | 热键 Ctrl+Shift+R 恢复最近会话 |
| 部分恢复 | 从管理对话框多选窗口恢复 |
| 自动保存 | 定期检测窗口变化，自动快照（默认 5 分钟间隔） |
| 管理会话 | 两级对话框：会话列表 → 窗口列表，支持重命名/删除/编辑路径 |
| 全局热键 | Ctrl+Shift+S 保存、Ctrl+Shift+R 恢复 |
| 多语言 | 中文/English/日本語，运行时切换 |
| 日志系统 | 时间戳日志文件，自动清理 |

---

## 4. 代码统计

| 模块 | 行数 | 说明 |
|------|------|------|
| `app/app_core.py` | 538 | 核心控制器 |
| `app/session_manager.py` | 532 | COM 会话引擎 |
| `app/manage_dialog.py` | 572 | 管理对话框 |
| `app/settings_dialog.py` | 257 | 设置对话框 |
| `app/logger.py` | 157 | 日志系统 |
| `app/config_manager.py` | 151 | 配置管理 |
| `app/hotkey_manager.py` | 140 | 热键管理 |
| `app/common.py` | 46 | 共享工具 |
| `app/constants.py` | 39 | 常量 |
| `app/__init__.py` | 1 | 包标记 |
| `main.py` | 52 | 入口点 |
| **源码合计** | **2,517** | |
| **测试合计** | **365** | 45 用例 |
| **语言文件** | **240** | 3 文件 × 80 行 |
| **总计** | **3,248** | |

---

## 5. 测试覆盖

| 模块 | 测试项 | 覆盖状态 |
|------|--------|---------|
| config_manager + common | 10 | 编码检测 / INI 读取 / 配置存取闭环 |
| hotkey_manager | 5 | 热键字符串验证 / 键码映射 |
| language_manager | 6 | 加载 / 回退 / 参数替换 |
| session_manager | 24 | 会话 CRUD / 窗口 CRUD / 文件操作 |
| app_core | 0 | 未测试（需 GUI + COM 环境） |
| settings_dialog | 0 | 未测试（需 GUI 环境） |
| manage_dialog | 0 | 未测试（需 GUI 环境） |
| logger | 0 | 未测试 |

**测试结果：** 45 passed, 0 failed

---

## 6. 构建

```bat
# 单文件 exe
pyinstaller --onefile --noconsole --name "MineExp" --clean ^
    --icon "app/resources/icon.ico" ^
    --add-data "language;language" ^
    --add-data "app/resources;app/resources" ^
    main.py
```

产物：`dist/MineExp.exe`（~40MB，已嵌入图标）

---

## 7. 已知限制

- **仅限 Windows** — 依赖 `pywin32`、`Shell.Application` COM、`RegisterHotKey` 等 Win32 API
- **不存在的路径** — 恢复时自动跳过并弹窗提示
- **网络路径** — UNC 路径可能恢复缓慢（`Path.exists()` 可能阻塞）
- **同名窗口** — 如果已有同路径 Explorer 窗口打开，`SetWindowPos` 可能作用于已有窗口而非新窗口

---

## 8. 修复记录（本轮审计）

经过 9 轮提交，共修复/改进 18 个问题：

| 类别 | 问题数 | 关键修复 |
|------|--------|---------|
| 严重 | 3 | 日志句柄泄漏、并发恢复竞态、COM 引用泄漏 |
| 高危 | 7 | 配置非原子写入、配置无验证、热键验证、取消无效、tooltip 崩溃等 |
| 中危 | 5 | 语言切换菜单索引、硬编码中文、GUI 阻塞等 |
| 功能 | 1 | 不存在的路径跳过 + 恢复完成弹窗 |
| 工程 | 5 | .gitignore、pyproject.toml、未使用导入、类型注解、README |

---

## 9. 项目的原则

- **思考先于编码** — 每次改动前进行了 3-agent 并行审计
- **简单优先** — 所有修复均最小化，无新增抽象
- **精准修改** — 仅修改问题相关行，不触碰相邻代码
- **目标驱动** — 每次修改后 pytest 验证，45 项测试持续通过
