"""
Mine Exp
主入口：启动 AppCore（系统托盘 + 全局热键，无主窗口）
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from app.logger import get_logger
from app.config_manager import BASE_DIR
from app.app_core import AppCore

# ── 启动 ──

def main():
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