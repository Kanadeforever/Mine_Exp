"""
manage_dialog.py
会话管理对话框（两级层级：会话组列表 → 会话组内窗口条目）

第一层（默认）：
  - 显示所有 JSON 会话组
  - 单击选中，双击进入
  - 恢复按钮：只允许单选恢复（恢复整个会话组）
  - "打开选中的会话组"按钮：进入该会话组
  - 编辑名称按钮：启用

第二层（进入会话组后）：
  - 第一行显示 ".." 用于返回上一级
  - 其余行显示窗口路径
  - 恢复按钮：支持多选恢复（恢复选中的窗口条目）
  - "返回上一级"按钮：返回会话组列表
  - 编辑路径按钮：选中单个条目时启用，弹出编辑对话框
  - 删除按钮：从 JSON 中移除选中的窗口条目
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QMessageBox, QInputDialog,
    QAbstractItemView, QListWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

import json
import re
import subprocess

from app.language_manager import LanguageManager
from app import session_manager as sm
from app.logger import get_logger

logger = get_logger(__name__)

# ─── 特殊角色常量 ─────────────────────────────────────
_ROLE_BACK = "__BACK__"   # 用于标识".."返回项


class ManageDialog(QDialog):
    def __init__(
        self,
        lang_mgr: LanguageManager,
        on_restore_session=None,
        on_restore_windows=None,
        parent=None,
    ):
        super().__init__(parent)
        self._lm = lang_mgr
        self._on_restore_session = on_restore_session      # callable(name) -> None
        self._on_restore_windows = on_restore_windows      # callable(name, indices) -> None
        self._sessions = []

        # ── 层级状态 ──
        self._level = 0              # 0 = 会话组列表, 1 = 会话组内部
        self._current_session_name = None   # 进入第二层时记录会话组名

        self.setWindowTitle(self._lm.t("ManageSessions", "Title"))
        self.setMinimumSize(700, 500)   # 改动 E：放大窗口
        self.setup_ui()
        self.setup_shortcuts()
        self.refresh()

    # ───────────────────────── UI 构建 ────────────────────

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 提示标签
        self.hint_label = QLabel(self._lm.t("ManageSessions", "SelectHint"))
        layout.addWidget(self.hint_label)

        # 会话列表（支持多选）
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        # 按钮行
        btn_row = QHBoxLayout()

        self.restore_btn = QPushButton(self._lm.t("ManageSessions", "RestoreSelected"))
        self.restore_btn.clicked.connect(self.restore_selected)
        btn_row.addWidget(self.restore_btn)

        # 改动 C：新增"打开选中会话组 / 返回上一级"按钮
        self.enter_group_btn = QPushButton(self._lm.t("ManageSessions", "EnterGroupBtn"))
        self.enter_group_btn.clicked.connect(self._on_enter_group_clicked)
        btn_row.addWidget(self.enter_group_btn)

        self.delete_btn = QPushButton(self._lm.t("ManageSessions", "DeleteBtn"))
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(self.delete_btn)

        self.rename_btn = QPushButton(self._lm.t("ManageSessions", "RenameBtn"))
        self.rename_btn.clicked.connect(self.rename_selected)
        btn_row.addWidget(self.rename_btn)

        open_folder_btn = QPushButton(self._lm.t("ManageSessions", "OpenFolderBtn"))
        open_folder_btn.clicked.connect(self.open_folder)
        btn_row.addWidget(open_folder_btn)

        btn_row.addStretch()

        refresh_btn = QPushButton(self._lm.t("ManageSessions", "RefreshBtn"))
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        close_btn = QPushButton(self._lm.t("ManageSessions", "CloseBtn"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        # 初始状态
        self._update_button_states()

    def _update_button_states(self):
        """根据当前层级更新按钮的启用/禁用状态和文本"""
        if self._level == 0:
            # 第一层
            self.rename_btn.setText(self._lm.t("ManageSessions", "RenameBtn"))
            self.rename_btn.setEnabled(True)
            self.enter_group_btn.setText(self._lm.t("ManageSessions", "EnterGroupBtn"))
            self.enter_group_btn.setEnabled(True)
        else:
            # 第二层：编辑名称 → 编辑路径
            self.rename_btn.setText(self._lm.t("ManageSessions", "EditPathBtn"))
            self.enter_group_btn.setText(self._lm.t("ManageSessions", "BackBtn"))
            self.enter_group_btn.setEnabled(True)
            # 编辑路径按钮：单选且不是 ".." 时启用
            self._update_rename_state_level1()

    def _update_rename_state_level1(self):
        """第二层：根据选中项更新编辑路径按钮状态"""
        selected = self.list_widget.selectedItems()
        if len(selected) == 1:
            data = selected[0].data(Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                self.rename_btn.setEnabled(True)
                return
        self.rename_btn.setEnabled(False)

    def _on_enter_group_clicked(self):
        """"打开选中会话组 / 返回上一级"按钮逻辑"""
        if self._level == 0:
            # 第一层：进入选中的会话组
            name = self._get_single_selected_name()
            if not name:
                QMessageBox.information(
                    self, self._lm.t("ManageSessions", "RestoreTitle"),
                    self._lm.t("ManageSessions", "NoSelection"))
                return
            self._enter_session_group(name)
        else:
            # 第二层：返回第一层
            self._leave_session_group()

    def setup_shortcuts(self):
        # Delete 键删除
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(
            self.delete_selected)
        # Enter / Return 恢复
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(
            self.restore_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(
            self.restore_selected)
        # F2 重命名 / 编辑路径（根据层级自动适配）
        QShortcut(QKeySequence(Qt.Key.Key_F2), self).activated.connect(
            self.rename_selected)
        # Ctrl+A 全选
        QShortcut(QKeySequence.StandardKey.SelectAll, self).activated.connect(
            self.list_widget.selectAll)
        # 双击
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        # 选中变化时更新按钮状态（第二层编辑路径按钮）
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        """选中项变化时更新按钮状态"""
        if self._level == 1:
            self._update_rename_state_level1()

    # ───────────────────────── 数据加载 ────────────────────

    def _get_session_window_paths(self, name: str) -> list[str]:
        """获取会话内的窗口路径列表"""
        paths = []
        path = sm.session_path(name)
        if path.exists():
            try:
                data = json.loads(path.read_text("utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        p = item.get("Path", "")
                        if p:
                            paths.append(p)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read session %s for tooltip: %s", name, e)
        return paths

    def _build_tooltip(self, name: str, count: int) -> str:
        """构建会话列表项的 tooltip（显示前 5 条窗口路径）"""
        paths = self._get_session_window_paths(name)
        lines = [
            f"{self._lm.t('ManageSessions', 'SessionLabel')}: {name}",
            f"{self._lm.t('ManageSessions', 'WindowCountLabel')}: {count}",
            ""
        ]
        display = paths[:5]
        for p in display:
            lines.append(p)
        if len(paths) > 5:
            lines.append(self._lm.t("ManageSessions", "MoreLabel", str(len(paths) - 5)))
        return "\n".join(lines)

    def refresh(self):
        """刷新列表（根据当前层级显示不同内容）"""
        self.list_widget.clear()

        if self._level == 0:
            # ── 第一层：显示会话组列表 ──
            self.setWindowTitle(self._lm.t("ManageSessions", "Title"))
            self.hint_label.setText(self._lm.t("ManageSessions", "SelectHint"))
            try:
                self._sessions = sm.list_sessions()
            except Exception as e:
                logger.error("Failed to list sessions: %s", e)
                self._sessions = []
            for s in self._sessions:
                name = s['name']
                win_label = self._lm.t("ManageSessions", "WindowsLabel", str(s['count']))
                item = QListWidgetItem(f"{s['name']} | {win_label} | {s['time_str']}")
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setToolTip(self._build_tooltip(name, s['count']))
                self.list_widget.addItem(item)
        else:
            # ── 第二层：显示会话组内的窗口条目 ──
            session_name = self._current_session_name or ""
            self.setWindowTitle(
                self._lm.t("ManageSessions", "Title") + f" — {session_name}")
            self.hint_label.setText(
                f"{self._lm.t('ManageSessions', 'SelectHint')} ({session_name})")

            # 添加 ".." 返回项
            back_item = QListWidgetItem("..")
            back_item.setData(Qt.ItemDataRole.UserRole, _ROLE_BACK)
            self.list_widget.addItem(back_item)

            # 添加窗口条目
            try:
                windows = sm.get_session_windows(session_name)
                for win in windows:
                    path_str = win.get("Path", "")
                    item = QListWidgetItem(path_str)
                    item.setData(Qt.ItemDataRole.UserRole, win["index"])
                    item.setToolTip(path_str)
                    self.list_widget.addItem(item)
            except sm.SessionError as e:
                logger.warning("Failed to load windows for session %s: %s", session_name, e)
            except Exception as e:
                logger.error("Unexpected error loading windows for session %s: %s", session_name, e)
                QMessageBox.warning(
                    self, self._lm.t("General", "Error"),
                    self._lm.t("ManageSessions", "LoadError", session_name))

        self._update_button_states()

    # ───────────────────────── 选中项工具 ────────────────────

    def _get_selected_names(self) -> list[str]:
        """获取当前选中项的会话名列表（从 Qt.UserRole 读取，仅在 first level 有效）"""
        names = []
        for item in self.list_widget.selectedItems():
            name = item.data(Qt.ItemDataRole.UserRole)
            if name and isinstance(name, str) and name != _ROLE_BACK:
                names.append(name)
        return names

    def _get_selected_indices(self) -> list[int]:
        """获取当前选中项的窗口索引列表（仅在 second level 有效）"""
        indices = []
        for item in self.list_widget.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                indices.append(data)
        return indices

    def _get_single_selected_name(self) -> str | None:
        """获取单选会话名；若未选或选多个返回 None"""
        names = self._get_selected_names()
        if len(names) == 1:
            return names[0]
        return None

    def _get_single_selected_index(self) -> int | None:
        """获取第二层的单选窗口索引；若未选或选多个或选中返回项返回 None"""
        items = self.list_widget.selectedItems()
        if len(items) != 1:
            return None
        data = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            return data
        return None

    # ───────────────────────── 双击 ────────────────────

    def _on_double_click(self, item):
        """双击行为根据当前层级不同"""
        data = item.data(Qt.ItemDataRole.UserRole)

        if self._level == 0:
            # 第一层双击会话组 → 进入该会话组
            name = data if isinstance(data, str) and data != _ROLE_BACK else None
            if name:
                self._enter_session_group(name)
        else:
            # 第二层
            if data == _ROLE_BACK:
                # 双击 ".." → 返回第一层
                self._leave_session_group()
            elif isinstance(data, int):
                # 双击窗口条目 → 恢复该单个窗口
                self._restore_single_window(data)

    def _enter_session_group(self, name: str):
        """进入会话组"""
        self._level = 1
        self._current_session_name = name
        self.refresh()

    def _leave_session_group(self):
        """返回会话组列表"""
        self._level = 0
        self._current_session_name = None
        self.refresh()

    def _restore_single_window(self, index: int):
        """恢复单个窗口并关闭对话框"""
        name = self._current_session_name
        if not name:
            return
        self.accept()
        if self._on_restore_windows:
            self._on_restore_windows(name, [index])

    # ───────────────────────── 恢复 ────────────────────

    def restore_selected(self):
        """恢复选中项（不同层级行为不同）"""
        if self._level == 0:
            # ── 第一层：仅允许单选恢复整个会话组 ──
            names = self._get_selected_names()
            if not names:
                QMessageBox.information(
                    self, self._lm.t("ManageSessions", "RestoreTitle"),
                    self._lm.t("ManageSessions", "NoSelection"))
                return
            if len(names) > 1:
                QMessageBox.information(
                    self, self._lm.t("ManageSessions", "RestoreTitle"),
                    self._lm.t("ManageSessions", "SelectSingleSession"))
                return
            self.accept()
            if self._on_restore_session:
                self._on_restore_session(names[0])
            else:
                sm.restore_session(names[0])
        else:
            # ── 第二层：支持多选恢复窗口条目 ──
            indices = self._get_selected_indices()
            if not indices:
                QMessageBox.information(
                    self, self._lm.t("ManageSessions", "RestoreTitle"),
                    self._lm.t("ManageSessions", "NoSelection"))
                return
            name = self._current_session_name
            if not name:
                return
            self.accept()
            if self._on_restore_windows:
                self._on_restore_windows(name, indices)

    # ───────────────────────── 删除 ────────────────────

    def delete_selected(self):
        if self._level == 0:
            self._delete_selected_sessions()
        else:
            self._delete_selected_windows()

    def _delete_selected_sessions(self):
        """删除选中的会话文件"""
        names = self._get_selected_names()
        if not names:
            QMessageBox.information(
                self, self._lm.t("ManageSessions", "DeleteTitle"),
                self._lm.t("ManageSessions", "NoSelection"))
            return

        msg = self._lm.t("ManageSessions", "Confirm", names[0])
        if len(names) > 1:
            msg += self._lm.t("ManageSessions", "MultiSelectHint", str(len(names)))
        ret = QMessageBox.question(
            self, self._lm.t("ManageSessions", "ConfirmTitle"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        ok_count = 0
        for name in names:
            try:
                if sm.delete_session(name):
                    ok_count += 1
            except Exception as e:
                logger.error("Failed to delete session %s: %s", name, e)
        logger.info("Deleted %d/%d sessions", ok_count, len(names))
        self.refresh()

    def _delete_selected_windows(self):
        """从当前会话组中移除选中的窗口条目"""
        indices = self._get_selected_indices()
        if not indices:
            QMessageBox.information(
                self, self._lm.t("ManageSessions", "DeleteTitle"),
                self._lm.t("ManageSessions", "NoSelection"))
            return

        session_name = self._current_session_name
        if not session_name:
            return

        msg = self._lm.t("ManageSessions", "ConfirmDeleteWindow", str(len(indices)))
        ret = QMessageBox.question(
            self, self._lm.t("ManageSessions", "ConfirmTitle"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        # 从大到小排序以确保索引在删除过程中不变
        sorted_indices = sorted(indices, reverse=True)
        ok_count = 0
        for idx in sorted_indices:
            try:
                if sm.delete_window_from_session(session_name, idx):
                    ok_count += 1
            except Exception as e:
                logger.error("Failed to delete window %d from session %s: %s", idx, session_name, e)
        logger.info("Removed %d/%d windows from session %s", ok_count, len(indices), session_name)
        self.refresh()

    # ───────────────────────── 重命名 / 编辑路径 ────────────

    def rename_selected(self):
        """根据当前层级执行重命名或编辑路径"""
        if self._level == 0:
            self._rename_session()
        else:
            self._edit_path()

    def _rename_session(self):
        """第一层：重命名会话组"""
        name = self._get_single_selected_name()
        if not name:
            QMessageBox.information(
                self, self._lm.t("ManageSessions", "RenameTitle"),
                self._lm.t("ManageSessions", "NoSelection"))
            return

        new_name, ok = QInputDialog.getText(
            self,
            self._lm.t("ManageSessions", "RenameTitle"),
            self._lm.t("ManageSessions", "RenameHint"),
            text=name,
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == name:
            return

        # 校验名称：禁止 Windows 文件名非法字符
        if not re.match(r'^[^/\\:*?"<>|]+$', new_name):
            QMessageBox.warning(
                self, self._lm.t("General", "Error"),
                self._lm.t("ManageSessions", "InvalidName"))
            return

        if sm.rename_session(name, new_name):
            logger.info("Session renamed: %s -> %s", name, new_name)
            self.refresh()
        else:
            QMessageBox.warning(
                self, self._lm.t("General", "Error"),
                self._lm.t("ManageSessions", "RenameFailExists", new_name))

    def _edit_path(self):
        """第二层：编辑选中窗口的路径"""
        index = self._get_single_selected_index()
        if index is None:
            QMessageBox.information(
                self, self._lm.t("ManageSessions", "EditPathTitle"),
                self._lm.t("ManageSessions", "NoSelection"))
            return

        session_name = self._current_session_name
        if not session_name:
            return

        # 获取当前路径
        try:
            windows = sm.get_session_windows(session_name)
            current_path = ""
            for w in windows:
                if w["index"] == index:
                    current_path = w.get("Path", "")
                    break
        except sm.SessionError as e:
            logger.warning("Failed to get windows for session %s: %s", session_name, e)
            current_path = ""
        except Exception as e:
            logger.error("Unexpected error reading session %s: %s", session_name, e)
            current_path = ""

        new_path, ok = QInputDialog.getText(
            self,
            self._lm.t("ManageSessions", "EditPathTitle"),
            self._lm.t("ManageSessions", "EditPathHint"),
            text=current_path,
        )
        if not ok or not new_path.strip():
            return
        new_path = new_path.strip()

        # 校验路径中不能包含 Windows 路径非法字符（< > " | ? *）
        if re.search(r'[<>"|?*]', new_path):
            QMessageBox.warning(
                self, self._lm.t("General", "Error"),
                self._lm.t("ManageSessions", "InvalidName"))
            return

        if sm.update_window_path(session_name, index, new_path):
            logger.info("Window path updated in session %s at index %d", session_name, index)
            self.refresh()
        else:
            QMessageBox.warning(
                self, self._lm.t("General", "Error"),
                self._lm.t("ManageSessions", "PathEditFail"))

    # ───────────────────────── 打开路径 ────────────────────

    def open_folder(self):
        """在资源管理器中打开会话存储目录"""
        folder = sm.SESSION_DIR
        if not folder.exists():
            logger.warning("Session folder does not exist: %s", folder)
            QMessageBox.warning(
                self, self._lm.t("General", "Error"),
                self._lm.t("ManageSessions", "FolderNotFound"))
            return
        try:
            subprocess.Popen(["explorer", str(folder)])
            logger.info("Opened session folder: %s", folder)
        except Exception as e:
            logger.error("Failed to open folder: %s", e)
            QMessageBox.warning(
                self, self._lm.t("General", "Error"), str(e))