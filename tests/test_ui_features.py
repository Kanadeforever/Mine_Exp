"""测试恢复菜单与托盘的便捷功能。"""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QListWidgetItem, QSystemTrayIcon

from app.app_core import AppCore
from app.manage_dialog import ManageDialog


class _FakeLanguageManager:
    def t(self, section, key, *args):
        return key


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _select_session(dialog: ManageDialog, name: str):
    item = QListWidgetItem(name)
    item.setData(Qt.ItemDataRole.UserRole, name)
    dialog.list_widget.addItem(item)
    item.setSelected(True)


def test_restore_menu_stays_open_when_configured(qapp, monkeypatch):
    monkeypatch.setattr("app.manage_dialog.sm.list_sessions", lambda: [])
    restored = []
    dialog = ManageDialog(
        _FakeLanguageManager(),
        on_restore_session=restored.append,
        close_after_restore=False,
    )
    _select_session(dialog, "session-1")

    dialog.restore_selected()

    assert restored == ["session-1"]
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_restore_menu_closes_by_default(qapp, monkeypatch):
    monkeypatch.setattr("app.manage_dialog.sm.list_sessions", lambda: [])
    restored = []
    dialog = ManageDialog(
        _FakeLanguageManager(),
        on_restore_session=restored.append,
    )
    _select_session(dialog, "session-1")

    dialog.restore_selected()

    assert restored == ["session-1"]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_tray_double_click_opens_restore_menu_only_for_double_click():
    calls = []
    core = SimpleNamespace(manage_sessions=lambda: calls.append("opened"))

    AppCore._on_tray_activated(core, QSystemTrayIcon.ActivationReason.Context)
    assert calls == []

    AppCore._on_tray_activated(core, QSystemTrayIcon.ActivationReason.DoubleClick)
    assert calls == ["opened"]
