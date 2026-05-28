"""
app_core.py
核心逻辑：系统托盘 + 全局热键 + 会话管理 + 自动保存，无主窗口。
"""

import atexit
import json

from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu,
    QMessageBox, QWidget, QStyle, QProgressDialog,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QIcon

from app.language_manager import LanguageManager
from app import session_manager as sm
from app.settings_dialog import SettingsDialog
from app.manage_dialog import ManageDialog
from app.config_manager import load_config, save_config, BASE_DIR, LANGUAGE_DIR, SESSION_DIR
from app.logger import get_logger, set_language_manager, configure_logging
from app.hotkey_manager import HotkeyManager, WinHotkeyFilter
from app.constants import (
    NOTIFY_DURATION_NORMAL, NOTIFY_DURATION_ERROR,
    STARTUP_NOTIFICATION_DELAY,
    AUTOSAVE_SESSION_PREFIX,
)

logger = get_logger(__name__)


class RestoreWorker(QThread):
    """异步恢复工作线程（恢复整个会话）"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, list)
    error = pyqtSignal(str)

    def __init__(self, session_name: str):
        super().__init__()
        self._name = session_name

    def run(self):
        try:
            succ, fail, failed_paths = sm.restore_session(
                self._name,
                progress_callback=lambda s, f, p: self.progress.emit(s, f, p),
                cancel_check=self.isInterruptionRequested,
            )
            self.finished.emit(succ, fail, failed_paths)
        except sm.SessionError as e:
            self.error.emit(str(e))
        except Exception as e:
            logger.exception("Restore worker error: %s", e)
            self.error.emit(str(e))


class RestorePartialWorker(QThread):
    """异步恢复工作线程（恢复会话中部分窗口）"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int, list)
    error = pyqtSignal(str)

    def __init__(self, session_name: str, indices: list[int]):
        super().__init__()
        self._name = session_name
        self._indices = indices

    def run(self):
        try:
            succ, fail, failed_paths = sm.restore_windows_from_session(
                self._name,
                self._indices,
                progress_callback=lambda s, f, p: self.progress.emit(s, f, p),
                cancel_check=self.isInterruptionRequested,
            )
            self.finished.emit(succ, fail, failed_paths)
        except sm.SessionError as e:
            self.error.emit(str(e))
        except Exception as e:
            logger.exception("Restore partial worker error: %s", e)
            self.error.emit(str(e))


class AppCore(QObject):
    """应用程序核心：托盘 + 热键 + 自动保存 + 逻辑，无主窗口显示。"""

    def __init__(self):
        super().__init__()
        # ── 配置和语言 ──
        self._cfg = load_config()
        self._lang_mgr = LanguageManager(LANGUAGE_DIR, self._cfg["Language"])
        set_language_manager(self._lang_mgr)

        # ── 日志系统初始化 ──
        log_enabled = self._cfg.get("LogEnabled", "true").lower() == "true"
        log_max_entries = int(self._cfg.get("LogMaxEntries", "20"))
        configure_logging(log_enabled, log_max_entries)

        # ── 隐藏窗口（仅提供 HWND 给 HotkeyManager） ──
        self._dummy = QWidget()
        self._dummy.setWindowTitle("ExplorerSessionSaver")
        self._dummy.resize(1, 1)  # 极小尺寸

        # ── 自动保存 ──
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._last_snapshot = None
        self._worker = None
        self._start_auto_save_timer()

        # ── 系统托盘（不连接 activated 信号，完全由原生 setContextMenu 处理右键）──
        self._setup_tray()

        # ── 全局热键 ──
        self._hk_manager = HotkeyManager(int(self._dummy.winId()))
        self._hk_filter = WinHotkeyFilter(self._hk_manager)
        self._hook_hotkeys()

        # ── 安装原生事件过滤器 ──
        self._native_filter_installed = False
        QTimer.singleShot(0, self._install_native_filter)

        # ── 启动通知 ──
        QTimer.singleShot(STARTUP_NOTIFICATION_DELAY, self._show_startup_notification)

    # ── 自动保存 ───────────────────────────────────────

    def _start_auto_save_timer(self):
        """根据配置启动/重启自动保存定时器"""
        self._auto_save_timer.stop()
        enabled = self._cfg.get("AutoSaveEnabled", "true").lower() == "true"
        if not enabled:
            logger.info("Auto save disabled")
            return
        interval_min = int(self._cfg.get("AutoSaveInterval", "5"))
        interval_ms = max(60000, interval_min * 60000)  # 最少 1 分钟
        self._auto_save_timer.start(interval_ms)
        # 首次快照：避免启动时立即触发保存
        self._last_snapshot = self._take_snapshot()
        logger.info("Auto save started: interval=%dmin", interval_min)

    def _stop_auto_save_timer(self):
        """停止自动保存定时器"""
        self._auto_save_timer.stop()
        logger.info("Auto save stopped")

    def _take_snapshot(self) -> str:
        """获取当前窗口状态的 JSON 快照（用于比较变化）"""
        try:
            windows = sm.get_open_windows()
            return json.dumps(windows, ensure_ascii=False, sort_keys=True)
        except Exception as e:
            logger.warning("Failed to take auto-save snapshot: %s", e)
            return ""

    def _auto_save(self):
        """自动保存定时回调：检测窗口变化，如有变化则自动保存"""
        try:
            snapshot = self._take_snapshot()
            if not snapshot:
                return

            # 与上次快照比较
            if snapshot == self._last_snapshot:
                return

            # 窗口有变化 → 保存
            name = AUTOSAVE_SESSION_PREFIX + sm.generate_session_name()
            count = sm.save_session(name)

            # 更新快照
            self._last_snapshot = snapshot

            # 日志记录（不弹通知）
            logger.info("Auto saved: %s (%d windows)", name, count)

            # 清理旧自动保存会话
            self._cleanup_old_autosaves()
        except Exception as e:
            logger.exception("Auto_save_error: %s", e)

    def _cleanup_old_autosaves(self):
        """清理超出 MaxCount 的旧自动保存文件"""
        max_count = int(self._cfg.get("AutoSaveMaxCount", "20"))
        try:
            # 获取所有 auto_ 前缀的会话文件，按修改时间排序（旧 → 新）
            auto_files = sorted(
                [f for f in SESSION_DIR.glob(f"{AUTOSAVE_SESSION_PREFIX}*.json")],
                key=lambda p: p.stat().st_mtime
            )
            if len(auto_files) <= max_count:
                return
            # 删除最旧的
            to_delete = auto_files[:len(auto_files) - max_count]
            for f in to_delete:
                try:
                    f.unlink()
                    logger.info("Auto_save_cleaned: %s", f.stem)
                except OSError as e:
                    logger.warning("Failed to delete old auto-save %s: %s", f.stem, e)
        except Exception as e:
            logger.warning("Auto_save_cleanup_error: %s", e)

    # ── 系统托盘 ───────────────────────────────────────

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        icon_path = BASE_DIR / "app" / "resources" / "icon.png"
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self.tray_icon.setIcon(
                QApplication.instance().style().standardIcon(
                    QStyle.StandardPixmap.SP_ComputerIcon)
            )
        self.tray_icon.setToolTip(
            self._lang_mgr.t("Tray", "Tooltip") or "ExplorerSessionSaver")

        menu = QMenu()
        self._save_action = menu.addAction(self._lang_mgr.t("Tray", "Save"))
        self._save_action.triggered.connect(self.save_session)
        self._restore_action = menu.addAction(self._lang_mgr.t("Tray", "Restore"))
        self._restore_action.triggered.connect(self._restore_latest)
        self._manage_action = menu.addAction(self._lang_mgr.t("Tray", "Manage"))
        self._manage_action.triggered.connect(self.manage_sessions)
        self._settings_action = menu.addAction(self._lang_mgr.t("Tray", "Settings"))
        self._settings_action.triggered.connect(self.open_settings)
        menu.addSeparator()
        self._quit_action = menu.addAction(self._lang_mgr.t("Tray", "Quit"))
        self._quit_action.triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(menu)
        # 不连接 activated 信号，避免与原生右键菜单冲突 → 根治双菜单问题
        self.tray_icon.show()

    # ── 全局热键 ───────────────────────────────────────

    def _hook_hotkeys(self):
        hotkeys = [
            ("SaveSession", self._cfg["SaveSession"], self.save_session),
            ("QuickRestore", self._cfg["QuickRestore"], self._restore_latest),
        ]
        errors = []
        for name, combo, callback in hotkeys:
            try:
                self._hk_manager.register(combo, callback)
                logger.info("Hotkey registered: %s = %s", name, combo)
            except Exception as e:
                errors.append(f"{name} ({combo}): {e}")
                logger.warning("Failed to register hotkey %s: %s", combo, e)

        if errors:
            msg = "; ".join(errors)
            self.tray_icon.showMessage(
                self._lang_mgr.t("General", "Error"),
                msg,
                QSystemTrayIcon.MessageIcon.Critical,
                NOTIFY_DURATION_ERROR)

    def _install_native_filter(self):
        if not self._native_filter_installed:
            try:
                QApplication.instance().installNativeEventFilter(self._hk_filter)
                self._native_filter_installed = True
                logger.info("Native event filter installed")
            except Exception as e:
                logger.warning("Failed to install native filter: %s", e)
            else:
                atexit.register(self._cleanup)

    def _cleanup(self):
        """atexit 注册的清理函数，确保热键被注销"""
        self._hk_manager.unregister_all()

    # ── 操作 ──────────────────────────────────────────

    def save_session(self):
        try:
            name = sm.generate_session_name()
            count = sm.save_session(name)
            msg = self._lang_mgr.t("Main", "Saved", name, str(count))
            self.tray_icon.showMessage(
                self._lang_mgr.t("General", "Success"),
                msg,
                QSystemTrayIcon.MessageIcon.Information,
                NOTIFY_DURATION_NORMAL)
            logger.info("Session saved: %s (%d windows)", name, count)
        except sm.SessionError as e:
            logger.error("Save session failed: %s", e)
            self.tray_icon.showMessage(
                self._lang_mgr.t("General", "Error"),
                str(e),
                QSystemTrayIcon.MessageIcon.Critical,
                NOTIFY_DURATION_ERROR)
        except Exception as e:
            logger.exception("Unexpected error saving session: %s", e)
            self.tray_icon.showMessage(
                self._lang_mgr.t("General", "Error"),
                str(e),
                QSystemTrayIcon.MessageIcon.Critical,
                NOTIFY_DURATION_ERROR)

    def _restore_latest(self):
        """快速恢复（最新会话）"""
        name = sm.get_latest_session_name()
        if name is None:
            msg = self._lang_mgr.t("Main", "NoSessions")
            self.tray_icon.showMessage(
                self._lang_mgr.t("General", "Info"),
                msg,
                QSystemTrayIcon.MessageIcon.Information,
                NOTIFY_DURATION_NORMAL)
            # 增加弹窗提示，让用户明确感知
            QMessageBox.information(
                None,
                self._lang_mgr.t("General", "Info") or "Info",
                msg)
            return
        logger.info("Restoring session: %s", name)
        self._restore(name)

    def _restore(self, name: str):
        """使用 QThread 异步恢复 + 进度对话框"""
        if self._worker is not None and self._worker.isRunning():
            logger.warning("Restore already in progress, ignoring request")
            return

        progress = QProgressDialog(
            self._lang_mgr.t("Main", "RestoringProgress", name),
            self._lang_mgr.t("General", "Cancel"),
            0, 100, None)  # parent=None → 独立浮动对话框
        progress.setWindowTitle(self._lang_mgr.t("Main", "Restoring"))
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        self._worker = RestoreWorker(name)
        self._worker.progress.connect(
            lambda s, f, p: self._on_restore_progress(progress, s, f, p))
        self._worker.finished.connect(
            lambda s, f, fps: self._on_restore_done(progress, name, s, f, fps))
        self._worker.error.connect(
            lambda e: self._on_restore_error(progress, name, e))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        progress.canceled.connect(self._on_restore_cancel)
        self._worker.start()

    def _restore_partial(self, name: str, indices: list[int]):
        """使用 QThread 异步恢复部分窗口 + 进度对话框"""
        if self._worker is not None and self._worker.isRunning():
            logger.warning("Restore already in progress, ignoring request")
            return

        progress = QProgressDialog(
            self._lang_mgr.t("Main", "RestoringProgress", name),
            self._lang_mgr.t("General", "Cancel"),
            0, 100, None)
        progress.setWindowTitle(self._lang_mgr.t("Main", "Restoring"))
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        self._worker = RestorePartialWorker(name, indices)
        self._worker.progress.connect(
            lambda s, f, p: self._on_restore_progress(progress, s, f, p))
        self._worker.finished.connect(
            lambda s, f, fps: self._on_restore_done(progress, name, s, f, fps))
        self._worker.error.connect(
            lambda e: self._on_restore_error(progress, name, e))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        progress.canceled.connect(self._on_restore_cancel)
        self._worker.start()

    def _on_restore_progress(self, progress: QProgressDialog, success: int, failed: int, status: str):
        progress.setLabelText(status)
        progress.setValue(success + failed)

    def _on_restore_cancel(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            logger.info("Restore cancellation requested")

    def _on_restore_done(self, progress: QProgressDialog, name: str, success: int, failed: int, failed_paths: list[str]):
        progress.close()
        msg = self._lang_mgr.t("Main", "Restored", str(success), str(failed))
        self.tray_icon.showMessage(
            self._lang_mgr.t("General", "Success"),
            msg,
            QSystemTrayIcon.MessageIcon.Information,
            NOTIFY_DURATION_NORMAL)
        logger.info("Session restored: %s (%d/%d)", name, success, failed)
        if failed_paths:
            self._show_failed_paths_dialog(failed_paths)
        self._worker = None

    def _show_failed_paths_dialog(self, failed_paths: list[str]):
        title = self._lang_mgr.t("Main", "SkippedPathsTitle")
        header = self._lang_mgr.t("Main", "SkippedPathsHeader", str(len(failed_paths)))
        display = failed_paths[:20]
        detail = "\n".join(display)
        if len(failed_paths) > 20:
            detail += "\n" + self._lang_mgr.t("Main", "MoreLabel", str(len(failed_paths) - 20))
        QMessageBox.warning(None, title, f"{header}\n\n{detail}")

    def _on_restore_error(self, progress: QProgressDialog, name: str, error_msg: str):
        progress.close()
        logger.error("Restore failed: %s: %s", name, error_msg)
        self.tray_icon.showMessage(
            self._lang_mgr.t("General", "Error"),
            error_msg,
            QSystemTrayIcon.MessageIcon.Critical,
            NOTIFY_DURATION_ERROR)
        self._worker = None

    def manage_sessions(self):
        dlg = ManageDialog(
            self._lang_mgr,
            on_restore_session=self._restore,
            on_restore_windows=self._restore_partial,
        )
        dlg.exec()

    # ── 设置 ──────────────────────────────────────────

    def open_settings(self):
        logger.info("Opening settings dialog")

        # 临时注销全局热键，避免干扰设置中的热键捕获
        self._hk_manager.unregister_all()
        # 临时移除原生事件过滤器
        native_filter_was_installed = self._native_filter_installed
        if native_filter_was_installed:
            try:
                QApplication.instance().removeNativeEventFilter(self._hk_filter)
                self._native_filter_installed = False
            except Exception as e:
                logger.warning("Failed to remove native event filter: %s", e)

        # 清空事件队列
        QApplication.processEvents()
        try:
            dlg = SettingsDialog(self._cfg, self._lang_mgr, LANGUAGE_DIR)
            result = dlg.exec()

            if result == SettingsDialog.DialogCode.Accepted:
                new_cfg = dlg.get_config()
                if new_cfg != self._cfg:
                    old_lang = self._cfg["Language"]
                    old_auto_enabled = self._cfg.get("AutoSaveEnabled", "true")
                    old_auto_interval = self._cfg.get("AutoSaveInterval", "5")
                    old_log_enabled = self._cfg.get("LogEnabled", "true")
                    old_log_max = self._cfg.get("LogMaxEntries", "20")
                    self._cfg = new_cfg
                    save_config(self._cfg)

                    # 语言热切换
                    if new_cfg["Language"] != old_lang:
                        self._reload_language()

                    # 日志配置变更
                    new_log_enabled = new_cfg.get("LogEnabled", "true")
                    new_log_max = new_cfg.get("LogMaxEntries", "20")
                    if new_log_enabled != old_log_enabled or new_log_max != old_log_max:
                        configure_logging(
                            new_log_enabled.lower() == "true",
                            int(new_log_max),
                        )

                    # 自动保存配置变更 → 重启定时器
                    new_auto_enabled = self._cfg.get("AutoSaveEnabled", "true")
                    new_auto_interval = self._cfg.get("AutoSaveInterval", "5")
                    if new_auto_enabled != old_auto_enabled or new_auto_interval != old_auto_interval:
                        self._start_auto_save_timer()

                    self.tray_icon.showMessage(
                        self._lang_mgr.t("General", "Success"),
                        self._lang_mgr.t("Settings", "SavedMsg"),
                        QSystemTrayIcon.MessageIcon.Information,
                        NOTIFY_DURATION_NORMAL)
        except Exception as e:
            logger.exception("Settings dialog crashed: %s", e)
            try:
                self.tray_icon.showMessage(
                    self._lang_mgr.t("General", "Error"),
                    str(e),
                    QSystemTrayIcon.MessageIcon.Critical,
                    NOTIFY_DURATION_ERROR)
            except Exception:
                pass
        finally:
            if native_filter_was_installed:
                try:
                    QApplication.instance().installNativeEventFilter(self._hk_filter)
                    self._native_filter_installed = True
                except Exception as e:
                    logger.warning("Failed to reinstall native event filter: %s", e)
            self._reload_hotkeys()
            logger.info("Settings dialog closed, hotkeys reloaded")

    # ── 语言 / 热键热切换 ─────────────────────────────

    def _reload_language(self):
        """运行时热切换语言"""
        new_lang = self._cfg["Language"]
        self._lang_mgr = LanguageManager(LANGUAGE_DIR, new_lang)

        self.tray_icon.setToolTip(
            self._lang_mgr.t("Tray", "Tooltip") or "ExplorerSessionSaver")
        self._save_action.setText(self._lang_mgr.t("Tray", "Save"))
        self._restore_action.setText(self._lang_mgr.t("Tray", "Restore"))
        self._manage_action.setText(self._lang_mgr.t("Tray", "Manage"))
        self._settings_action.setText(self._lang_mgr.t("Tray", "Settings"))
        self._quit_action.setText(self._lang_mgr.t("Tray", "Quit"))

        set_language_manager(self._lang_mgr)
        logger.info("Language switched: %s", new_lang)

    def _reload_hotkeys(self):
        """运行时重新注册全局热键"""
        self._hk_manager.unregister_all()
        self._hook_hotkeys()
        logger.info("Hotkeys reloaded")

    def _show_startup_notification(self):
        """首次启动托盘通知"""
        self.tray_icon.showMessage(
            self._lang_mgr.t("General", "Info"),
            self._lang_mgr.t("Tray", "Tooltip") or "ExplorerSessionSaver is running",
            QSystemTrayIcon.MessageIcon.Information,
            NOTIFY_DURATION_NORMAL)

    def quit_app(self):
        logger.info("Application quitting")
        self._auto_save_timer.stop()
        self._hk_manager.unregister_all()
        QApplication.instance().quit()