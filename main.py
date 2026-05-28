"""
Mine Exp
主入口：启动 AppCore（系统托盘 + 全局热键，无主窗口）
"""

import sys
import ctypes

# ── 控制台分配 ─────────────────────────────────
# 如果命令行包含 --console，则为进程分配一个控制台窗口，
# 并将 stdout/stderr 重定向到该控制台（主要用于打包 exe 后调试）。
if "--console" in sys.argv:
    kernel32 = ctypes.windll.kernel32
    if not kernel32.AllocConsole():
        # 如果分配失败（例如已有控制台），让程序继续运行
        pass
    else:
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys._console_allocated = True
    sys.argv.remove("--console")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from app.logger import get_logger
from app.config_manager import BASE_DIR, init_resources
from app.app_core import AppCore

# ── 启动 ──

def main():
    init_resources()

    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("Application starting...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 设置应用窗口图标（所有弹窗自动继承）
    icon_path = BASE_DIR / "app" / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    core = AppCore()

    logger.info("Application started, running event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()