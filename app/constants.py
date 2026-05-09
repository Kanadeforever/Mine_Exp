"""
constants.py
应用程序全局常量定义（魔术数字统一管理）
"""

# ── Win32 虚拟桌面边界（GetSystemMetrics 索引） ──────
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# ── 窗口恢复 ─────────────────────────────────────────
WAIT_TIMEOUT = 5.0          # 等待窗口创建超时（秒）
WAIT_INTERVAL = 0.05        # 轮询间隔（秒）
MIN_VISIBLE_WIDTH = 200     # 窗口可见最小宽度（像素）
MIN_VISIBLE_HEIGHT = 150    # 窗口可见最小高度（像素）

# ── 托盘通知持续时间（毫秒） ─────────────────────────
NOTIFY_DURATION_NORMAL = 3000    # 普通通知
NOTIFY_DURATION_ERROR = 5000     # 错误通知

# ── 启动 ────────────────────────────────────────────
STARTUP_NOTIFICATION_DELAY = 1500   # 启动通知延迟（毫秒）

# ── 线程 ────────────────────────────────────────────
WORKER_TERMINATE_WAIT = 3000  # 强制终止工作线程等待超时（毫秒）

# ── 自动保存 ────────────────────────────────────────
AUTOSAVE_DEFAULT_INTERVAL = 5       # 默认自动保存间隔（分钟）
AUTOSAVE_DEFAULT_MAX_COUNT = 20     # 默认最多保留的自动保存会话数
AUTOSAVE_SESSION_PREFIX = "auto_"   # 自动保存会话文件前缀
AUTOSAVE_INTERVAL_MIN = 1           # 自动保存间隔最小值（分钟）
AUTOSAVE_INTERVAL_MAX = 120         # 自动保存间隔最大值（分钟）
AUTOSAVE_MAX_COUNT_MIN = 1          # 保留会话数最小值
AUTOSAVE_MAX_COUNT_MAX = 999        # 保留会话数最大值

# ── 日志 ────────────────────────────────────────────
LOG_DEFAULT_MAX_ENTRIES = 20        # 默认最多保留的日志文件数
LOG_MAX_ENTRIES_MIN = 5             # 日志文件数最小值
LOG_MAX_ENTRIES_MAX = 200           # 日志文件数最大值