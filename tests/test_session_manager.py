"""测试 session_manager — 会话 JSON 读写、文件名生成、列表排序、窗口管理"""

import json
from pathlib import Path
from datetime import datetime
import pytest
import app.session_manager as sm
from app.session_manager import (
    generate_session_name,
    session_exists,
    save_session,
    list_sessions,
    delete_session,
    rename_session,
    get_latest_session_name,
    get_session_windows,
    delete_window_from_session,
    update_window_path,
    SessionError,
    session_path,
    SESSION_DIR,
)


class TestSessionName:
    def test_generate_format(self):
        name = generate_session_name()
        # 格式: YYYY-MM-DD_HHMMSS (17 chars: e.g. 2026-05-08_143052)
        assert "_" in name
        parts = name.split("_")
        assert len(parts) == 2
        date_part, time_part = parts
        assert len(date_part) == 10  # YYYY-MM-DD
        assert len(time_part) == 6   # HHMMSS


class TestSessionExists:
    def test_exists_true(self, session_dir: Path):
        session_path("test").write_text("[]", encoding="utf-8")
        assert session_exists("test") is True

    def test_exists_false(self, session_dir):
        assert session_exists("nonexistent") is False


class TestSaveSession:
    def test_save_without_name_creates_file(self, session_dir):
        count = save_session("test_save")
        assert count >= 0
        assert session_path("test_save").exists()

    def test_save_content_is_valid_json(self, session_dir):
        save_session("test_json")
        data = json.loads(session_path("test_json").read_text("utf-8"))
        assert isinstance(data, list)


class TestListSessions:
    def test_list_empty(self, session_dir):
        assert list_sessions() == []

    def test_list_order(self, session_dir):
        sessions = ["aaa", "bbb", "ccc"]
        for s in sessions:
            session_path(s).write_text("[]", encoding="utf-8")
            import time
            time.sleep(0.05)  # 确保 mtime 不同

        listed = list_sessions()
        names = [s["name"] for s in listed]
        # 倒序: ccc, bbb, aaa
        assert names == ["ccc", "bbb", "aaa"]


class TestDeleteSession:
    def test_delete_existing(self, session_dir):
        session_path("delme").write_text("[]", encoding="utf-8")
        assert delete_session("delme") is True
        assert not session_path("delme").exists()

    def test_delete_nonexistent(self, session_dir):
        assert delete_session("nope") is False


class TestRenameSession:
    def test_rename_success(self, session_dir):
        session_path("old").write_text('[{"Path": "C:\\test"}]', encoding="utf-8")
        assert rename_session("old", "new") is True
        assert not session_path("old").exists()
        assert session_path("new").exists()

    def test_rename_same_name(self, session_dir):
        session_path("same").write_text("[]", encoding="utf-8")
        assert rename_session("same", "same") is True

    def test_rename_nonexistent(self, session_dir):
        assert rename_session("nope", "newname") is False

    def test_rename_overwrite_protection(self, session_dir):
        session_path("a").write_text("[]", encoding="utf-8")
        session_path("b").write_text("[]", encoding="utf-8")
        assert rename_session("a", "b") is False


class TestGetLatestSession:
    def test_latest(self, session_dir):
        session_path("first").write_text("[]", encoding="utf-8")
        import time
        time.sleep(0.05)
        session_path("second").write_text("[]", encoding="utf-8")
        time.sleep(0.05)
        session_path("third").write_text("[]", encoding="utf-8")

        assert get_latest_session_name() == "third"

    def test_no_sessions(self, session_dir):
        assert get_latest_session_name() is None


class TestGetSessionWindows:
    def test_get_windows_success(self, session_dir):
        data = [
            {"Path": "C:\\test1", "Left": 0, "Top": 0, "Width": 800, "Height": 600},
            {"Path": "C:\\test2", "Left": 100, "Top": 100, "Width": 1024, "Height": 768},
        ]
        session_path("wintest").write_text(json.dumps(data), encoding="utf-8")
        windows = get_session_windows("wintest")
        assert len(windows) == 2
        assert windows[0]["index"] == 0
        assert windows[0]["Path"] == "C:\\test1"
        assert windows[1]["index"] == 1
        assert windows[1]["Path"] == "C:\\test2"

    def test_get_windows_not_found(self, session_dir):
        with pytest.raises(SessionError):
            get_session_windows("nonexistent")

    def test_get_windows_invalid_json(self, session_dir):
        session_path("bad").write_text("not json", encoding="utf-8")
        with pytest.raises(SessionError):
            get_session_windows("bad")


class TestDeleteWindowFromSession:
    def test_delete_window_success(self, session_dir):
        data = [
            {"Path": "C:\\keep", "Left": 0, "Top": 0, "Width": 800, "Height": 600},
            {"Path": "C:\\remove", "Left": 100, "Top": 100, "Width": 1024, "Height": 768},
        ]
        session_path("delwin").write_text(json.dumps(data), encoding="utf-8")
        assert delete_window_from_session("delwin", 1) is True
        remaining = json.loads(session_path("delwin").read_text("utf-8"))
        assert len(remaining) == 1
        assert remaining[0]["Path"] == "C:\\keep"

    def test_delete_window_out_of_range(self, session_dir):
        session_path("oor").write_text("[]", encoding="utf-8")
        assert delete_window_from_session("oor", 0) is False

    def test_delete_window_not_found(self, session_dir):
        assert delete_window_from_session("nope", 0) is False


class TestUpdateWindowPath:
    def test_update_path_success(self, session_dir):
        data = [{"Path": "C:\\old", "Left": 0, "Top": 0, "Width": 800, "Height": 600}]
        session_path("update").write_text(json.dumps(data), encoding="utf-8")
        assert update_window_path("update", 0, "C:\\new") is True
        updated = json.loads(session_path("update").read_text("utf-8"))
        assert updated[0]["Path"] == "C:\\new"

    def test_update_path_not_found(self, session_dir):
        assert update_window_path("nope", 0, "C:\\new") is False

    def test_update_path_out_of_range(self, session_dir):
        session_path("oor").write_text("[]", encoding="utf-8")
        assert update_window_path("oor", 0, "C:\\new") is False


class _FakeSelf:
    def __init__(self, path: str):
        self.Path = path


class _FakeFolder:
    def __init__(self, path: str):
        self.Self = _FakeSelf(path)


class _FakeDocument:
    def __init__(self, path: str):
        self.Folder = _FakeFolder(path)


class _FakeBrowser:
    def __init__(self, hwnd: int, path: str, url: str | None = None):
        self.HWND = hwnd
        self.Document = _FakeDocument(path)
        self.LocationURL = url if url is not None else path
        self.Busy = False
        self.navigated_to = None

    def Navigate2(self, target):
        self.navigated_to = target
        path = str(target)
        self.Document = _FakeDocument(path)
        self.LocationURL = path


class _FakeShell:
    def __init__(self, windows: list[_FakeBrowser]):
        self.windows = windows
        self.opened = []

    def Windows(self):
        return list(self.windows)

    def Open(self, path: str):
        self.opened.append(path)

    def NameSpace(self, _path: str):
        return None


class TestAccurateRestore:
    def test_minimized_placeholder_size_uses_normal_fallback(self):
        assert sm._fallback_window_size(160, 28) == (1200, 800)
        assert sm._fallback_window_size(900, 700) == (900, 700)

    def test_wait_for_new_window_ignores_existing_same_path(self, monkeypatch):
        old = _FakeBrowser(100, "C:\\same")
        new = _FakeBrowser(200, "C:\\same")
        shell = _FakeShell([old, new])
        monkeypatch.setattr(sm, "_is_valid_window", lambda _hwnd: True)

        hwnd = sm._wait_for_window_hwnd(
            "C:\\same", timeout=0.1, shell=shell, existing_hwnds={100})

        assert hwnd == 200

    def test_new_tab_is_selected_only_from_target_window(self, monkeypatch):
        target_old = _FakeBrowser(200, "C:\\first")
        other_old = _FakeBrowser(300, "C:\\other")
        shell = _FakeShell([target_old, other_old])
        wrong_new = _FakeBrowser(300, "Home", "new-other")
        target_new = _FakeBrowser(200, "Home", "new-target")

        class FakeUser32:
            def PostMessageW(self, _hwnd, _message, command, _param):
                if command == sm._NEW_TAB_COMMAND:
                    shell.windows.extend([wrong_new, target_new])
                return 1

        monkeypatch.setattr(sm, "_USER32", FakeUser32())
        monkeypatch.setattr(sm, "_wait_for_tab_host", lambda _hwnd, timeout: 500)
        monkeypatch.setattr(sm.time, "sleep", lambda _seconds: None)

        assert sm._try_open_as_tab("C:\\target", 200, shell) is True
        assert target_new.navigated_to == "C:\\target"
        assert wrong_new.navigated_to is None

    def test_failed_tab_is_not_restored_as_separate_window(self, monkeypatch):
        shell = _FakeShell([])
        items = [
            {"Path": "C:\\first", "GroupId": 1},
            {"Path": "C:\\second", "GroupId": 1},
        ]
        observed = {}
        monkeypatch.setattr(sm, "_path_accessible", lambda _path: True)
        monkeypatch.setattr(sm, "_capture_explorer_hwnds", lambda _shell: {100})

        def wait_for_new(path, timeout=sm.WAIT_TIMEOUT, shell=None, existing_hwnds=None):
            observed["existing"] = existing_hwnds
            return 200

        monkeypatch.setattr(sm, "_wait_for_window_hwnd", wait_for_new)
        monkeypatch.setattr(sm, "_apply_window_geometry", lambda _hwnd, _item: None)
        monkeypatch.setattr(sm, "_wait_for_first_window_ready", lambda *_args: True)
        monkeypatch.setattr(sm, "_try_open_as_tab", lambda *_args: False)

        success, failed = sm._restore_group_items(items, shell)

        assert shell.opened == ["C:\\first"]
        assert observed["existing"] == {100}
        assert success == [0]
        assert failed == [1]

    def test_geometry_is_captured_once_for_all_tabs_in_group(self, monkeypatch):
        shell = _FakeShell([
            _FakeBrowser(200, "C:\\first"),
            _FakeBrowser(200, "C:\\second"),
        ])
        calls = []
        geometry = {
            "Left": 10, "Top": 20, "Width": 900, "Height": 700,
            "ShowCmd": 3, "GeometryReliable": True,
        }
        monkeypatch.setattr(sm, "_init_com", lambda: False)
        monkeypatch.setattr(sm, "_get_shell", lambda: shell)
        monkeypatch.setattr(
            sm, "_capture_window_geometry",
            lambda hwnd, _browser: calls.append(hwnd) or geometry,
        )

        windows = sm.get_open_windows()

        assert calls == [200]
        assert [item["Path"] for item in windows] == ["C:\\first", "C:\\second"]
        assert all(item["ShowCmd"] == 3 for item in windows)
        assert windows[0]["GroupId"] == windows[1]["GroupId"]
