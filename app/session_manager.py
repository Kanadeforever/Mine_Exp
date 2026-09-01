"""
session_manager.py
替换所有 PowerShell 脚本，通过 win32com 直接操作 Shell.Application COM 接口。

替代脚本：
  - Save-Session.ps1
  - Restore-Session.ps1
  - List-Sessions.ps1
  - Delete-Session.ps1
  - Get-ExplorerSessions.ps1
"""

import json
import ctypes
import ctypes.wintypes
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Callable

import pythoncom
import win32com.client

from app.config_manager import SESSION_DIR
from app.logger import get_logger
from app.constants import (
    WAIT_TIMEOUT, WAIT_INTERVAL,
    MIN_VISIBLE_WIDTH, MIN_VISIBLE_HEIGHT,
    MAX_WINDOW_SIZE_RATIO,
)

logger = get_logger(__name__)

# ─── Win32 ─────────────────────────────────────────────
_USER32 = ctypes.windll.user32
_USER32.FindWindowExW.restype = ctypes.wintypes.HWND
_USER32.MonitorFromRect.restype = ctypes.wintypes.HANDLE
_USER32.GetForegroundWindow.restype = ctypes.wintypes.HWND
_MONITOR_DEFAULTTONULL = 0x00000000
_SW_SHOWNORMAL = 1
_SW_SHOWMAXIMIZED = 3
_SW_RESTORE = 9
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_WM_COMMAND = 0x0111
_NEW_TAB_COMMAND = 0xA21B
_CLOSE_TAB_COMMAND = 0xA021
_FIRST_WINDOW_READY_TIMEOUT = 10.0
_FIRST_WINDOW_STABLE_DURATION = 1.2
_TAB_CREATE_TIMEOUT = 3.0
_TAB_NAVIGATE_TIMEOUT = 3.5
_GEOMETRY_REAPPLY_DELAY = 0.65
_MIN_RELIABLE_WINDOW_WIDTH = 480
_MIN_RELIABLE_WINDOW_HEIGHT = 320
_MIN_VISIBLE_INTERSECTION_WIDTH = 120
_MIN_VISIBLE_INTERSECTION_HEIGHT = 80
_DEFAULT_WINDOW_WIDTH = 1200
_DEFAULT_WINDOW_HEIGHT = 800


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("showCmd", ctypes.c_uint),
        ("ptMinPosition", _POINT),
        ("ptMaxPosition", _POINT),
        ("rcNormalPosition", _RECT),
        ("rcDevice", _RECT),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


class SessionError(Exception):
    """会话操作异常基类"""
    pass


# ─── 工具函数 ──────────────────────────────────────────

def _get_shell():
    """获取 Shell.Application COM 对象（调用方必须处于 COM 已初始化线程）"""
    try:
        return win32com.client.Dispatch("Shell.Application")
    except Exception as e:
        logger.error("Failed to get Shell.Application: %s", e)
        raise


def _init_com() -> bool:
    """在当前线程初始化 COM。返回 True 表示此调用实际初始化了 COM（需要对应的 CoUninitialize）。"""
    try:
        pythoncom.CoInitialize()
        return True
    except pythoncom.com_error:
        return False
    except Exception as e:
        logger.warning("Unexpected COM init error: %s", e)
        return False


def session_path(name: str) -> Path:
    return SESSION_DIR / f"{name}.json"


def _capture_explorer_hwnds(shell) -> set[int] | None:
    """记录当前 ShellWindows 中的 Explorer HWND，用于识别本次新建窗口。"""
    hwnds: set[int] = set()
    try:
        for w in shell.Windows():
            try:
                hwnd = int(w.HWND)
                if hwnd:
                    hwnds.add(hwnd)
            except Exception:
                continue
    except Exception as e:
        logger.warning("Failed to capture Explorer HWNDs: %s", e)
        return None
    return hwnds


def _is_valid_window(hwnd: int) -> bool:
    return bool(hwnd and _USER32.IsWindow(ctypes.wintypes.HWND(hwnd)))


def _wait_for_window_hwnd(
    path: str,
    timeout: float = WAIT_TIMEOUT,
    shell=None,
    existing_hwnds: set[int] | None = None,
) -> int | None:
    """
    轮询 ShellWindows，等待指定路径的 Explorer 窗口创建完成。
    返回有效 HWND，超时返回 None。
    
    Args:
        path: 目标窗口路径
        timeout: 超时秒数
        shell: 可复用的 Shell.Application 对象。为 None 时内部创建。
        existing_hwnds: 创建窗口前已有的 HWND；命中这些 HWND 时必须忽略。
    """
    start = time.time()
    if shell is None:
        try:
            shell = win32com.client.Dispatch("Shell.Application")
        except Exception as e:
            logger.error("Failed to create Shell.Application in _wait_for_window_hwnd: %s", e)
            return None
    excluded = existing_hwnds or set()
    while time.time() - start < timeout:
        try:
            for w in shell.Windows():
                try:
                    folder = w.Document
                    if folder is None:
                        continue
                    self_path = str(folder.Folder.Self.Path)
                    if not _paths_equal(self_path, path):
                        continue
                    hwnd = int(w.HWND)
                    if hwnd not in excluded and _is_valid_window(hwnd):
                        return hwnd
                except Exception as e:
                    logger.debug("Error inspecting ShellWindow: %s", e)
                    continue
        except Exception as e:
            logger.debug("Error enumerating ShellWindows: %s", e)
        time.sleep(WAIT_INTERVAL)
    logger.warning("Timeout waiting for HWND for path: %s", path)
    return None


def _get_monitor_info(monitor) -> _MONITORINFO | None:
    if not monitor:
        return None
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _USER32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
        return None
    return mi


def _screen_rect_usable(left: int, top: int, width: int, height: int) -> bool:
    """判断屏幕坐标是否仍落在某个显示器工作区内。"""
    if width < _MIN_RELIABLE_WINDOW_WIDTH or height < _MIN_RELIABLE_WINDOW_HEIGHT:
        return False
    if width > 20000 or height > 20000:
        return False
    rect = _RECT(left, top, left + width, top + height)
    monitor = _USER32.MonitorFromRect(ctypes.byref(rect), _MONITOR_DEFAULTTONULL)
    mi = _get_monitor_info(monitor)
    if mi is None:
        return False
    visible_width = min(rect.right, mi.rcWork.right) - max(rect.left, mi.rcWork.left)
    visible_height = min(rect.bottom, mi.rcWork.bottom) - max(rect.top, mi.rcWork.top)
    return (
        visible_width >= _MIN_VISIBLE_INTERSECTION_WIDTH
        and visible_height >= _MIN_VISIBLE_INTERSECTION_HEIGHT
    )


def _fallback_window_size(width: int, height: int) -> tuple[int, int]:
    """过滤最小化占位矩形等异常小尺寸。"""
    if width < _MIN_RELIABLE_WINDOW_WIDTH or width > 20000:
        width = _DEFAULT_WINDOW_WIDTH
    if height < _MIN_RELIABLE_WINDOW_HEIGHT or height > 20000:
        height = _DEFAULT_WINDOW_HEIGHT
    return width, height


def _centered_primary_rect(
    width: int = _DEFAULT_WINDOW_WIDTH,
    height: int = _DEFAULT_WINDOW_HEIGHT,
) -> tuple[int, int, int, int]:
    """在主显示器工作区居中，供坐标不可信时兜底。"""
    width, height = _fallback_window_size(width, height)
    work = _RECT()
    if _USER32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):  # SPI_GETWORKAREA
        work_left, work_top = work.left, work.top
        work_width = work.right - work.left
        work_height = work.bottom - work.top
    else:
        work_left = work_top = 0
        work_width = _USER32.GetSystemMetrics(0)
        work_height = _USER32.GetSystemMetrics(1)
    max_width = max(MIN_VISIBLE_WIDTH, int(work_width * MAX_WINDOW_SIZE_RATIO))
    max_height = max(MIN_VISIBLE_HEIGHT, int(work_height * MAX_WINDOW_SIZE_RATIO))
    width = max(MIN_VISIBLE_WIDTH, min(width, max_width))
    height = max(MIN_VISIBLE_HEIGHT, min(height, max_height))
    left = work_left + (work_width - width) // 2
    top = work_top + (work_height - height) // 2
    return left, top, width, height


def _sanitize_window_rect(left: int, top: int, width: int, height: int) -> tuple[int, int, int, int]:
    """修正窗口坐标和尺寸，处理多屏缺失/DPI变更"""
    if _screen_rect_usable(left, top, width, height):
        return left, top, width, height
    return _centered_primary_rect(width, height)


def _capture_window_geometry(hwnd: int, browser) -> dict:
    """捕获与 SetWindowPos 同坐标系的真实窗口矩形及显示状态。"""
    placement = _WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
    has_placement = bool(_USER32.GetWindowPlacement(
        ctypes.wintypes.HWND(hwnd), ctypes.byref(placement)))
    show_cmd = int(placement.showCmd) if has_placement else _SW_SHOWNORMAL
    minimized = show_cmd in {2, 6, 7, 11}

    rect = _RECT()
    reliable = (
        not minimized
        and bool(_USER32.GetWindowRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)))
        and _screen_rect_usable(
            int(rect.left), int(rect.top),
            int(rect.right - rect.left), int(rect.bottom - rect.top))
    )

    normal = placement.rcNormalPosition
    normal_width = int(normal.right - normal.left) if has_placement else 0
    normal_height = int(normal.bottom - normal.top) if has_placement else 0
    if reliable:
        left, top = int(rect.left), int(rect.top)
        width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
    else:
        width = normal_width or int(getattr(browser, "Width", 800))
        height = normal_height or int(getattr(browser, "Height", 600))
        left, top, width, height = _centered_primary_rect(width, height)

    result = {
        "Left": left,
        "Top": top,
        "Width": width,
        "Height": height,
        "ShowCmd": show_cmd,
        "GeometryReliable": reliable,
    }
    if has_placement:
        result.update({
            "NormalLeft": int(normal.left),
            "NormalTop": int(normal.top),
            "NormalWidth": normal_width,
            "NormalHeight": normal_height,
        })
    return result


def _center_normal_rect_on_saved_monitor(
    left: int,
    top: int,
    width: int,
    height: int,
    preferred_width: int,
    preferred_height: int,
) -> tuple[int, int, int, int]:
    rect = _RECT(left, top, left + width, top + height)
    monitor = _USER32.MonitorFromRect(ctypes.byref(rect), _MONITOR_DEFAULTTONULL)
    mi = _get_monitor_info(monitor)
    if mi is None:
        return _centered_primary_rect(preferred_width, preferred_height)
    work_width = mi.rcWork.right - mi.rcWork.left
    work_height = mi.rcWork.bottom - mi.rcWork.top
    preferred_width, preferred_height = _fallback_window_size(
        preferred_width, preferred_height)
    max_width = max(MIN_VISIBLE_WIDTH, int(work_width * MAX_WINDOW_SIZE_RATIO))
    max_height = max(MIN_VISIBLE_HEIGHT, int(work_height * MAX_WINDOW_SIZE_RATIO))
    preferred_width = max(MIN_VISIBLE_WIDTH, min(preferred_width, max_width))
    preferred_height = max(MIN_VISIBLE_HEIGHT, min(preferred_height, max_height))
    return (
        mi.rcWork.left + (work_width - preferred_width) // 2,
        mi.rcWork.top + (work_height - preferred_height) // 2,
        preferred_width,
        preferred_height,
    )


def _apply_window_geometry(hwnd: int, item: dict) -> None:
    """先恢复普通态并定位，再按保存状态恢复最大化。"""
    width = int(item.get("Width", 800))
    height = int(item.get("Height", 600))
    if item.get("GeometryReliable", True):
        left, top, width, height = _sanitize_window_rect(
            int(item.get("Left", 0)), int(item.get("Top", 0)), width, height)
    else:
        left, top, width, height = _centered_primary_rect(
            int(item.get("NormalWidth", width)),
            int(item.get("NormalHeight", height)),
        )

    show_cmd = int(item.get("ShowCmd", _SW_SHOWNORMAL))
    if show_cmd == _SW_SHOWMAXIMIZED and item.get("GeometryReliable", True):
        left, top, width, height = _center_normal_rect_on_saved_monitor(
            int(item.get("Left", left)), int(item.get("Top", top)),
            int(item.get("Width", width)), int(item.get("Height", height)),
            int(item.get("NormalWidth", width)), int(item.get("NormalHeight", height)),
        )

    hwnd_value = ctypes.wintypes.HWND(hwnd)
    _USER32.ShowWindow(hwnd_value, _SW_RESTORE)
    _USER32.SetWindowPos(
        hwnd_value, ctypes.wintypes.HWND(0),
        ctypes.c_int(left), ctypes.c_int(top), ctypes.c_int(width), ctypes.c_int(height),
        ctypes.c_uint(_SWP_NOZORDER | _SWP_NOACTIVATE),
    )
    _USER32.ShowWindow(
        hwnd_value,
        _SW_SHOWMAXIMIZED if show_cmd == _SW_SHOWMAXIMIZED else _SW_SHOWNORMAL,
    )


def _reapply_window_geometries(restored_windows: list[tuple[int, dict]]) -> None:
    if not restored_windows:
        return
    time.sleep(_GEOMETRY_REAPPLY_DELAY)
    for hwnd, item in restored_windows:
        try:
            if _is_valid_window(hwnd):
                _apply_window_geometry(hwnd, item)
        except Exception as e:
            logger.debug("Failed to reapply geometry for HWND %s: %s", hwnd, e)


def _paths_equal(a: str, b: str) -> bool:
    """比较两个路径（处理 UNC、尾部斜杠差异）"""
    if a == b:
        return True
    try:
        return Path(a).resolve() == Path(b).resolve()
    except Exception:
        return os.path.normcase(a.rstrip("\\")) == os.path.normcase(b.rstrip("\\"))


def _path_accessible(path_str: str) -> bool:
    """检查路径是否可访问（网络/UNC/shell路径跳过检查）"""
    if not path_str:
        return False
    if path_str.startswith("shell") or path_str.startswith("\\\\"):
        return True
    if len(path_str) >= 2 and path_str[1] == ":":
        drive = path_str[:2] + "\\"
        if ctypes.windll.kernel32.GetDriveTypeW(drive) == 4:  # DRIVE_REMOTE
            return True
    return Path(path_str).exists()


def _ensure_group_ids(data: list[dict]) -> list[dict]:
    """为无 GroupId 的旧 Session 分配组 ID。坐标完全相同 → 同组。"""
    coord_to_gid = {}
    next_gid = 1
    for entry in data:
        if "GroupId" in entry:
            continue
        key = (entry.get("Left"), entry.get("Top"), entry.get("Width"), entry.get("Height"))
        if key not in coord_to_gid:
            coord_to_gid[key] = next_gid
            next_gid += 1
        entry["GroupId"] = coord_to_gid[key]
    return data


def _get_browser_path(browser) -> str:
    try:
        return str(browser.Document.Folder.Self.Path)
    except Exception:
        try:
            return _normalize_location_url(str(browser.LocationURL or ""))
        except Exception:
            return ""


def _browser_matches_path(browser, path_str: str) -> bool:
    actual = _get_browser_path(browser)
    return bool(actual and _paths_equal(actual, path_str))


def _windows_for_hwnd(shell, hwnd: int) -> list:
    windows = []
    try:
        for w in shell.Windows():
            try:
                if int(w.HWND) == hwnd:
                    windows.append(w)
            except Exception:
                continue
    except Exception as e:
        logger.debug("Error enumerating windows for HWND %s: %s", hwnd, e)
    return windows


def _wait_for_tab_host(hwnd: int, timeout: float = WAIT_TIMEOUT) -> int | None:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        host = _USER32.FindWindowExW(
            ctypes.wintypes.HWND(hwnd), 0, "ShellTabWindowClass", None)
        if host:
            return int(host)
        time.sleep(WAIT_INTERVAL)
    return None


def _is_window_responsive(hwnd: int) -> bool:
    result = ctypes.c_size_t()
    return bool(_USER32.SendMessageTimeoutW(
        ctypes.wintypes.HWND(hwnd), 0, 0, 0,
        0x0001 | 0x0002, 150, ctypes.byref(result)))  # SMTO_BLOCK | SMTO_ABORTIFHUNG


def _wait_for_first_window_ready(
    shell,
    hwnd: int,
    path_str: str,
    timeout: float = _FIRST_WINDOW_READY_TIMEOUT,
    stable_duration: float = _FIRST_WINDOW_STABLE_DURATION,
) -> bool:
    """等待首路径、标签宿主和窗口响应连续稳定，避免过早创建标签。"""
    start = time.monotonic()
    stable_since: float | None = None
    stable_host: int | None = None
    while time.monotonic() - start < timeout:
        host = _USER32.FindWindowExW(
            ctypes.wintypes.HWND(hwnd), 0, "ShellTabWindowClass", None)
        ready = bool(host and _is_window_responsive(hwnd) and _is_window_responsive(int(host)))
        windows = _windows_for_hwnd(shell, hwnd) if ready else []
        if len(windows) != 1 or not _browser_matches_path(windows[0], path_str):
            ready = False
        if ready:
            try:
                if bool(windows[0].Busy):
                    ready = False
            except Exception:
                pass

        now = time.monotonic()
        if ready:
            if stable_since is None or stable_host != int(host):
                stable_since = now
                stable_host = int(host)
            elif now - stable_since >= stable_duration:
                return True
        else:
            stable_since = None
            stable_host = None
        time.sleep(WAIT_INTERVAL)
    return False


def _make_navigate_target(path_str: str, shell=None):
    """为 Navigate2 准备参数：普通路径直接传字符串，特殊路径用 Folder 对象"""
    try:
        shell_app = shell or win32com.client.Dispatch("Shell.Application")
        folder = shell_app.NameSpace(path_str)
        if folder is not None:
            return folder
    except Exception:
        pass
    return path_str


def _try_open_as_tab(path_str: str, target_hwnd: int, shell) -> bool:
    """在 target_hwnd 窗口中创建新标签页并导航。成功返回 True，失败不留垃圾标签页。"""
    tab_hwnd = _wait_for_tab_host(target_hwnd, timeout=6.0)
    if tab_hwnd is None:
        return False
    before: set[tuple[int, str]] = set()
    old_count = 0
    try:
        for w in shell.Windows():
            try:
                hwnd = int(w.HWND)
                before.add((hwnd, str(w.LocationURL or "")))
                if hwnd == target_hwnd:
                    old_count += 1
            except Exception:
                pass
    except Exception as e:
        logger.debug("Failed to capture browser keys: %s", e)
        return False

    if not _USER32.PostMessageW(
            ctypes.wintypes.HWND(tab_hwnd), _WM_COMMAND, _NEW_TAB_COMMAND, 0):
        return False

    candidate = None
    start = time.monotonic()
    while time.monotonic() - start < _TAB_CREATE_TIMEOUT:
        time.sleep(WAIT_INTERVAL)
        current = _windows_for_hwnd(shell, target_hwnd)
        if len(current) <= old_count:
            continue
        for w in current:
            try:
                key = (target_hwnd, str(w.LocationURL or ""))
                if key not in before:
                    candidate = w
                    break
            except Exception:
                continue
        if candidate is None:
            candidate = current[-1]  # 新标签初始 URL 与已有标签重复时按数量增量兜底
        break

    if candidate is None:
        return False

    success = False
    for _ in range(3):
        try:
            candidate.Navigate2(_make_navigate_target(path_str, shell))
        except Exception as e:
            logger.debug("Navigate2 failed for %s: %s", path_str, e)
        verify_start = time.monotonic()
        while time.monotonic() - verify_start < _TAB_NAVIGATE_TIMEOUT:
            if _browser_matches_path(candidate, path_str):
                success = True
                break
            time.sleep(WAIT_INTERVAL)
        if success:
            break
        time.sleep(0.12)

    if not success:
        _USER32.PostMessageW(
            ctypes.wintypes.HWND(tab_hwnd), _WM_COMMAND, _CLOSE_TAB_COMMAND, 1)
    return success


def _normalize_location_url(url: str) -> str:
    """将 LocationURL 转为可比路径"""
    import urllib.parse
    if url.startswith("file:///"):
        return urllib.parse.unquote(url[8:]).replace("/", "\\")
    if url.startswith("file:"):
        return urllib.parse.unquote(url[5:]).replace("/", "\\")
    return url


# ─── 会话文件名（带时间戳） ──────────────────────────

def generate_session_name() -> str:
    """生成默认会话名称：2026-05-08_143052"""
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ─── 核心 API ──────────────────────────────────────────

def get_open_windows() -> list[dict]:
    """
    获取所有打开的 Explorer 窗口信息。
    对应 Get-ExplorerSessions.ps1
    返回: [{"Path": str, "Left": int, "Top": int, "Width": int, "Height": int, "GroupId": int}, ...]
    """
    results = []
    com_initialized = _init_com()
    try:
        shell = _get_shell()
        hwnd_to_gid: dict[int, int] = {}
        geometry_by_hwnd: dict[int, dict] = {}
        next_gid = 1
        for w in shell.Windows():
            try:
                folder = w.Document
                if folder is None:
                    continue
                self_path = folder.Folder.Self.Path
                if self_path is None:
                    continue
                hwnd = int(w.HWND)
                if hwnd not in hwnd_to_gid:
                    hwnd_to_gid[hwnd] = next_gid
                    try:
                        geometry_by_hwnd[hwnd] = _capture_window_geometry(hwnd, w)
                    except Exception as e:
                        logger.debug("Failed to capture geometry for HWND %s: %s", hwnd, e)
                        geometry_by_hwnd[hwnd] = {
                            "Left": int(getattr(w, "Left", 0)),
                            "Top": int(getattr(w, "Top", 0)),
                            "Width": int(getattr(w, "Width", 800)),
                            "Height": int(getattr(w, "Height", 600)),
                            "ShowCmd": _SW_SHOWNORMAL,
                            "GeometryReliable": False,
                        }
                    next_gid += 1
                item = {
                    "Path": str(self_path),
                    "GroupId": hwnd_to_gid[hwnd],
                }
                item.update(geometry_by_hwnd[hwnd])
                results.append(item)
            except AttributeError:
                continue
            except Exception as e:
                logger.warning("Error reading window info: %s", e)
                continue
    except Exception as e:
        logger.error("Failed to enumerate Explorer windows: %s", e)
    finally:
        if com_initialized:
            pythoncom.CoUninitialize()
    return results


def save_session(name: str | None = None) -> int:
    """
    保存当前 Explorer 窗口状态。
    对应 Save-Session.ps1
    返回: 保存的窗口数量
    """
    if name is None:
        name = generate_session_name()
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    data = get_open_windows()
    path = session_path(name)
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Session saved: %s (%d windows)", name, len(data))
    except OSError as e:
        logger.error("Failed to write session file %s: %s", name, e)
        raise
    return len(data)


def list_sessions() -> list[dict]:
    """
    列出已保存的会话。
    对应 List-Sessions.ps1
    返回: [{"name": str, "count": int, "time": datetime}, ...]
         按时间倒序排列
    """
    sessions = []
    for f in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text("utf-8"))
            count = len(data) if isinstance(data, list) else 0
        except Exception:
            count = 0
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        sessions.append({
            "name": f.stem,
            "count": count,
            "time": mtime,
            "time_str": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return sessions


def delete_session(name: str) -> bool:
    """
    删除指定会话。
    对应 Delete-Session.ps1
    返回: True 删除成功, False 未找到
    """
    path = session_path(name)
    if path.exists():
        try:
            path.unlink()
            logger.info("Session deleted: %s", name)
            return True
        except OSError as e:
            logger.error("Failed to delete session %s: %s", name, e)
            return False
    logger.warning("Session not found: %s", name)
    return False


def _restore_group_items(
    items: list[dict],
    shell,
    restored_windows: list[tuple[int, dict]] | None = None,
) -> tuple[list[int], list[int]]:
    """恢复同一标签组；标签恢复失败时不拆成独立窗口。"""
    success, failed = [], []
    if not items:
        return success, failed

    first = items[0]
    first_path = str(first.get("Path", ""))
    if not first_path or not _path_accessible(first_path):
        if first_path:
            logger.info("Skipping inaccessible path: %s", first_path)
        return success, list(range(len(items)))

    try:
        existing_hwnds = _capture_explorer_hwnds(shell)
        if existing_hwnds is None:
            return success, list(range(len(items)))
        shell.Open(first_path)
        hwnd = _wait_for_window_hwnd(
            first_path, shell=shell, existing_hwnds=existing_hwnds)
        if hwnd is None:
            return success, list(range(len(items)))
        _apply_window_geometry(hwnd, first)
        success.append(0)
        if restored_windows is not None:
            restored_windows.append((hwnd, first))
    except Exception as e:
        logger.warning("Failed to restore window %s: %s", first_path, e)
        return success, list(range(len(items)))

    if len(items) > 1 and not _wait_for_first_window_ready(shell, hwnd, first_path):
        logger.warning("First Explorer window did not become ready: %s", first_path)
        return success, list(range(1, len(items)))

    for i, item in enumerate(items[1:], start=1):
        path_str = str(item.get("Path", ""))
        if not path_str or not _path_accessible(path_str):
            if path_str:
                logger.info("Skipping inaccessible path: %s", path_str)
            failed.append(i)
            continue
        if _try_open_as_tab(path_str, hwnd, shell):
            success.append(i)
        else:
            logger.warning("Failed to restore tab in group: %s", path_str)
            failed.append(i)
    return success, failed


def restore_session(
    name: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[int, int, list]:
    """
    恢复指定会话。
    对应 Restore-Session.ps1
    使用轮询替代 sleep(0.3) 等待窗口创建，提高可靠性。

    Args:
        name: 会话名称
        progress_callback: 进度回调 (success, failed, current_path)
        cancel_check: 取消检查回调，返回 True 时停止恢复

    Returns:
        (成功数, 失败数, 失败路径列表)
    """
    path = session_path(name)
    if not path.exists():
        raise SessionError(f"Session not found: {name}")

    try:
        data = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read session %s: %s", name, e)
        raise SessionError(f"Invalid session data: {name}") from e

    if not isinstance(data, list):
        raise SessionError(f"Invalid session data: {name}")

    data = _ensure_group_ids(data)

    total = len(data)
    logger.info("Restoring session: %s (%d windows)", name, total)

    # 按 GroupId 分组（无 GroupId 的条目各自独立成组）
    groups: list[list[dict]] = []
    _fallback = -1
    for item in data:
        gid = item.get("GroupId")
        if gid is None:
            gid = _fallback; _fallback -= 1
        added = False
        for g in groups:
            if g[0].get("GroupId") == gid:
                g.append(item); added = True; break
        if not added:
            groups.append([item])

    com_initialized = _init_com()
    try:
        shell = _get_shell()
        all_ok, all_fail = 0, 0
        failed_paths: list[str] = []
        restored_windows: list[tuple[int, dict]] = []
        processed = 0
        for group in groups:
            if cancel_check and cancel_check():
                logger.info("Restore cancelled at %d/%d", processed, total)
                break
            ok, fail = _restore_group_items(group, shell, restored_windows)
            all_ok += len(ok); all_fail += len(fail)
            for fi in fail:
                p = str(group[fi].get("Path", ""))
                if p: failed_paths.append(p)
            processed += len(group)
            if progress_callback:
                last = group[-1] if group else {}
                progress_callback(all_ok, all_fail,
                    f"[{processed}/{total}] {last.get('Path', '') or '(empty)'}")
        _reapply_window_geometries(restored_windows)
    finally:
        if com_initialized:
            pythoncom.CoUninitialize()

    logger.info("Session restored: %s (%d/%d)", name, all_ok, all_fail)
    return all_ok, all_fail, failed_paths


def session_exists(name: str) -> bool:
    """检查会话是否存在"""
    return session_path(name).exists()


def rename_session(old_name: str, new_name: str) -> bool:
    """
    重命名会话文件。
    返回: True 成功, False 失败
    """
    if old_name == new_name:
        return True
    old_path = session_path(old_name)
    new_path = session_path(new_name)
    if not old_path.exists():
        logger.warning("Session not found for rename: %s", old_name)
        return False
    if new_path.exists():
        logger.warning("Target name already exists: %s", new_name)
        return False
    try:
        old_path.rename(new_path)
        logger.info("Session renamed: %s -> %s", old_name, new_name)
        return True
    except OSError as e:
        logger.error("Failed to rename session %s -> %s: %s", old_name, new_name, e)
        return False


def get_session_windows(name: str) -> list[dict]:
    """
    获取指定会话内的窗口列表（附加索引）。
    返回: [{"index": int, "Path": str, "Left": int, ...}, ...]
    """
    path = session_path(name)
    if not path.exists():
        raise SessionError(f"Session not found: {name}")
    try:
        data = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise SessionError(f"Invalid session data: {name}") from e
    if not isinstance(data, list):
        raise SessionError(f"Invalid session data: {name}")
    windows = []
    for idx, item in enumerate(data):
        win = dict(item)
        win["index"] = idx
        windows.append(win)
    return windows


def delete_window_from_session(name: str, index: int) -> bool:
    """
    从会话 JSON 数组中移除指定索引的窗口条目。
    返回: True 成功, False 失败
    """
    path = session_path(name)
    if not path.exists():
        logger.warning("Session not found: %s", name)
        return False
    try:
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, list):
            return False
        if index < 0 or index >= len(data):
            logger.warning("Index %d out of range for session %s", index, name)
            return False
        removed = data.pop(index)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Window removed from session %s at index %d: %s", name, index, removed.get("Path", ""))
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to modify session %s: %s", name, e)
        return False


def restore_windows_from_session(
    name: str,
    indices: list[int],
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[int, int, list]:
    """
    恢复会话中指定索引的窗口。
    Args:
        name: 会话名称
        indices: 要恢复的窗口索引列表
        progress_callback: 进度回调 (success, failed, current_path)
        cancel_check: 取消检查回调，返回 True 时停止恢复
    Returns:
        (成功数, 失败数, 失败路径列表)
    """
    path = session_path(name)
    if not path.exists():
        raise SessionError(f"Session not found: {name}")

    try:
        all_data = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read session %s: %s", name, e)
        raise SessionError(f"Invalid session data: {name}") from e

    if not isinstance(all_data, list):
        raise SessionError(f"Invalid session data: {name}")

    data = []
    for idx in indices:
        if 0 <= idx < len(all_data):
            data.append(all_data[idx])

    total = len(data)
    if total == 0:
        return 0, 0, []

    logger.info("Restoring %d windows from session %s", total, name)

    # 按 GroupId 分组
    groups: list[list[dict]] = []
    _fallback = -1
    for item in data:
        gid = item.get("GroupId")
        if gid is None:
            gid = _fallback; _fallback -= 1
        added = False
        for g in groups:
            if g[0].get("GroupId") == gid:
                g.append(item); added = True; break
        if not added:
            groups.append([item])

    com_initialized = _init_com()
    try:
        shell = _get_shell()
        all_ok, all_fail = 0, 0
        failed_paths: list[str] = []
        restored_windows: list[tuple[int, dict]] = []
        processed = 0
        for group in groups:
            if cancel_check and cancel_check():
                logger.info("Restore cancelled at %d/%d", processed, total)
                break
            ok, fail = _restore_group_items(group, shell, restored_windows)
            all_ok += len(ok); all_fail += len(fail)
            for fi in fail:
                p = str(group[fi].get("Path", ""))
                if p: failed_paths.append(p)
            processed += len(group)
            if progress_callback:
                last = group[-1] if group else {}
                progress_callback(all_ok, all_fail,
                    f"[{processed}/{total}] {last.get('Path', '') or '(empty)'}")
        _reapply_window_geometries(restored_windows)
    finally:
        if com_initialized:
            pythoncom.CoUninitialize()

    logger.info("Session restored: %s (%d/%d)", name, all_ok, all_fail)
    return all_ok, all_fail, failed_paths


def update_window_path(name: str, index: int, new_path: str) -> bool:
    """
    更新会话中指定索引的窗口路径。
    返回: True 成功, False 失败
    """
    path = session_path(name)
    if not path.exists():
        logger.warning("Session not found: %s", name)
        return False
    try:
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, list):
            return False
        if index < 0 or index >= len(data):
            logger.warning("Index %d out of range for session %s", index, name)
            return False
        old_path = data[index].get("Path", "")
        data[index]["Path"] = new_path
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Window path updated in session %s at index %d: %s -> %s", name, index, old_path, new_path)
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to update session %s: %s", name, e)
        return False


def get_latest_session_name() -> str | None:
    """
    获取最新会话的名称。
    返回: 会话名或 None（没有会话时）
    """
    sessions = list_sessions()
    if sessions:
        return sessions[0]["name"]
    return None
