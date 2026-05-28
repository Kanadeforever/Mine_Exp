"""
settings_dialog.py
设置对话框（语言、热键配置、自动保存）
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QLabel, QComboBox, QPushButton,
    QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit

from app.language_manager import LanguageManager
from app.logger import get_logger
from app.constants import (
    AUTOSAVE_INTERVAL_MIN, AUTOSAVE_INTERVAL_MAX,
    AUTOSAVE_MAX_COUNT_MIN, AUTOSAVE_MAX_COUNT_MAX,
    LOG_MAX_ENTRIES_MIN, LOG_MAX_ENTRIES_MAX,
)

logger = get_logger(__name__)

# ─── 热键捕获输入框 ──────────────────────────────────

# Qt key 值：F1=0x70, F2=0x71, ..., F12=0x7B
_F_KEY_MAP = {
    Qt.Key.Key_F1: "F1",   Qt.Key.Key_F2: "F2",
    Qt.Key.Key_F3: "F3",   Qt.Key.Key_F4: "F4",
    Qt.Key.Key_F5: "F5",   Qt.Key.Key_F6: "F6",
    Qt.Key.Key_F7: "F7",   Qt.Key.Key_F8: "F8",
    Qt.Key.Key_F9: "F9",   Qt.Key.Key_F10: "F10",
    Qt.Key.Key_F11: "F11", Qt.Key.Key_F12: "F12",
}

_SPECIAL_KEY_MAP = {
    Qt.Key.Key_Space: "Space",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Backspace: "Backspace",
    Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Return: "Enter",
    Qt.Key.Key_Enter: "Enter",
}

MOD_QT_MAP = {
    Qt.KeyboardModifier.ControlModifier: "Ctrl",
    Qt.KeyboardModifier.ShiftModifier: "Shift",
    Qt.KeyboardModifier.AltModifier: "Alt",
    Qt.KeyboardModifier.MetaModifier: "Win",
}


class HotkeyLineEdit(QLineEdit):
    """点击后捕获按键组合，显示为人读字符串如 Ctrl+Shift+S"""

    def __init__(self, lang_mgr: LanguageManager, parent=None):
        super().__init__(parent)
        self._lm = lang_mgr
        self.setReadOnly(True)
        self.setPlaceholderText(self._lm.t("Settings", "HKPlaceholder"))
        self._capturing = False
        # 安装自身的事件过滤器来捕获按键
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self and self._capturing and event.type() == event.Type.KeyPress:
            self._on_key_press(event)
            return True  # 事件已消费，阻止进一步传播
        return super().eventFilter(obj, event)

    def focusInEvent(self, event):
        if event.reason() == Qt.FocusReason.MouseFocusReason:
            self._capturing = True
            self.setText("...")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._capturing = False
        # 如果内容仍然是占位 "..." 则清空
        if self.text() == "...":
            self.clear()
        super().focusOutEvent(event)

    def _on_key_press(self, event):
        """内部按键处理，通过 eventFilter 拦截"""
        key = event.key()

        # 忽略纯修饰键
        if key in (
            Qt.Key.Key_Control, Qt.Key.Key_Shift,
            Qt.Key.Key_Alt, Qt.Key.Key_Meta,
        ):
            return

        # 提取修饰键名
        mods = event.modifiers()
        parts = []
        for qmod, name in MOD_QT_MAP.items():
            if mods & qmod:
                parts.append(name)

        # 映射按键名
        if key in _F_KEY_MAP:
            display = _F_KEY_MAP[key]
        elif key in _SPECIAL_KEY_MAP:
            display = _SPECIAL_KEY_MAP[key]
        elif 0x20 <= key <= 0x7E:  # 可打印 ASCII
            display = chr(key)
        else:
            # 无法识别的键 → 忽略
            return

        if not parts:
            return  # 至少需要一个修饰键
        parts.append(display)
        combo = "+".join(parts)
        self.setText(combo)
        # 捕获后立即退出捕获模式
        self._capturing = False
        self.clearFocus()


# ─── 设置对话框 ──────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, current_cfg: dict, lang_mgr: LanguageManager, lang_dir, parent=None):
        super().__init__(parent)
        self._cfg = dict(current_cfg)
        self._lm = lang_mgr
        self._lang_dir = lang_dir
        self.setWindowTitle(self._lm.t("Settings", "Title"))
        self.setMinimumWidth(420)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── General 标签 ──
        gen = QWidget()
        gl = QVBoxLayout(gen)
        fl = QFormLayout()
        gl.addLayout(fl)

        try:
            lang_files = sorted([f.stem for f in self._lang_dir.glob("*.ini")])
        except Exception as e:
            logger.warning("Failed to list language files from %s: %s", self._lang_dir, e)
            lang_files = ["zh_CN", "en_US"]
        if "zh_CN" not in lang_files:
            lang_files.insert(0, "zh_CN")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(lang_files)
        idx = lang_files.index(self._cfg["Language"]) if self._cfg["Language"] in lang_files else 0
        self.lang_combo.setCurrentIndex(idx)
        fl.addRow(self._lm.t("Settings", "LangLabel") + ":", self.lang_combo)

        # ── 自动保存组 ──
        gl.addSpacing(16)

        self.auto_save_cb = QCheckBox(self._lm.t("AutoSave", "Enabled"))
        self.auto_save_cb.setChecked(self._cfg.get("AutoSaveEnabled", "true").lower() == "true")
        self.auto_save_cb.toggled.connect(self._on_auto_save_toggled)
        gl.addWidget(self.auto_save_cb)

        as_form = QFormLayout()
        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(AUTOSAVE_INTERVAL_MIN, AUTOSAVE_INTERVAL_MAX)
        self.auto_save_interval.setValue(int(self._cfg.get("AutoSaveInterval", "5")))
        self.auto_save_interval.setSuffix(" " + self._lm.t("AutoSave", "IntervalUnit"))
        as_form.addRow(self._lm.t("AutoSave", "Interval") + ":", self.auto_save_interval)

        self.auto_save_max_count = QSpinBox()
        self.auto_save_max_count.setRange(AUTOSAVE_MAX_COUNT_MIN, AUTOSAVE_MAX_COUNT_MAX)
        self.auto_save_max_count.setValue(int(self._cfg.get("AutoSaveMaxCount", "20")))
        self.auto_save_max_count.setSuffix(" " + self._lm.t("AutoSave", "MaxCountUnit"))
        as_form.addRow(self._lm.t("AutoSave", "MaxCount") + ":", self.auto_save_max_count)

        gl.addLayout(as_form)
        self._update_auto_save_enabled()

        gl.addStretch()
        tabs.addTab(gen, self._lm.t("Settings", "TabGeneral"))

        # ── Hotkeys 标签 ──
        try:
            hk = QWidget()
            hl = QVBoxLayout(hk)
            hf = QFormLayout()
            hl.addLayout(hf)

            self.hk_save = HotkeyLineEdit(self._lm)
            self.hk_save.setText(self._cfg["SaveSession"])
            hf.addRow(self._lm.t("Settings", "HKSaveLabel") + ":", self.hk_save)

            self.hk_quick = HotkeyLineEdit(self._lm)
            self.hk_quick.setText(self._cfg["QuickRestore"])
            hf.addRow(self._lm.t("Settings", "HKQuickRestore") + ":", self.hk_quick)

            hl.addWidget(QLabel(self._lm.t("Settings", "NoRestartHint")))
            hl.addStretch()
            tabs.addTab(hk, self._lm.t("Settings", "TabHotkeys"))
        except Exception as e:
            logger.exception("Exception building Hotkeys tab: %s", e)
            raise

        # ── Logging 标签 ──
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        self.log_enabled_cb = QCheckBox(self._lm.t("Settings", "LogEnabled"))
        self.log_enabled_cb.setChecked(self._cfg.get("LogEnabled", "true").lower() == "true")
        log_layout.addWidget(self.log_enabled_cb)

        log_form = QFormLayout()
        self.log_max_entries = QSpinBox()
        self.log_max_entries.setRange(LOG_MAX_ENTRIES_MIN, LOG_MAX_ENTRIES_MAX)
        self.log_max_entries.setValue(int(self._cfg.get("LogMaxEntries", "20")))
        self.log_max_entries.setSuffix(" " + self._lm.t("Settings", "LogMaxEntriesUnit"))
        log_form.addRow(self._lm.t("Settings", "LogMaxEntries") + ":", self.log_max_entries)

        log_layout.addLayout(log_form)
        log_layout.addStretch()
        tabs.addTab(log_tab, self._lm.t("Settings", "TabLogging"))

        # ── 按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton(self._lm.t("Settings", "SaveBtn"))
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)
        close_btn = QPushButton(self._lm.t("ManageSessions", "CloseBtn"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_auto_save_toggled(self, checked: bool):
        self._update_auto_save_enabled()

    def _update_auto_save_enabled(self):
        enabled = self.auto_save_cb.isChecked()
        self.auto_save_interval.setEnabled(enabled)
        self.auto_save_max_count.setEnabled(enabled)

    def get_config(self) -> dict:
        return {
            "Language": self.lang_combo.currentText(),
            "SaveSession": self.hk_save.text(),
            "QuickRestore": self.hk_quick.text(),
            "AutoSaveEnabled": "true" if self.auto_save_cb.isChecked() else "false",
            "AutoSaveInterval": str(self.auto_save_interval.value()),
            "AutoSaveMaxCount": str(self.auto_save_max_count.value()),
            "LogEnabled": "true" if self.log_enabled_cb.isChecked() else "false",
            "LogMaxEntries": str(self.log_max_entries.value()),
        }
