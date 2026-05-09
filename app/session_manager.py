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
import time
from pathlib import Path
from datetime import datetime
from typing import Callable

import pythoncom
import win32com.client

from app.config_manager import SESSION_DIR
from app.logger import get_logger
from app.constants import (
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN,
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN,
    WAIT_TIMEOUT, WAIT_INTERVAL,
    MIN_VISIBLE_WIDTH, MIN_VISIBLE_HEIGHT,
)

logger = get_logger(__name__)

# ─── Win32 ─────────────────────────────────────────────
_USER32 = ctypes.windll.user32


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


def _init_com():
    """在当前线程初始化 COM（每个线程只需调用一次）"""
    try:
        pythoncom.CoInitialize()
    except pythoncom.com_error:
        pass
    except Exception as e:
        logger.warning("Unexpected COM init error: %s", e)


def session_path(name: str) -> Path:
    return SESSION_DIR / f"{name}.json"


def _wait_for_window_hwnd(path: str, timeout: float = WAIT_TIMEOUT, shell=None) -> int | None:
    """
    轮询 ShellWindows，等待指定路径的 Explorer 窗口创建完成。
    返回有效 HWND，超时返回 None。
    
    Args:
        path: 目标窗口路径
        timeout: 超时秒数
        shell: 可复用的 Shell.Application 对象。为 None 时内部创建。
    """
    start = time.time()
    should_release_com = shell is None
    if should_release_com:
        try:
            shell = win32com.client.Dispatch("Shell.Application")
        except Exception as e:
            logger.error("Failed to create Shell.Application in _wait_for_window_hwnd: %s", e)
            return None
    while time.time() - start < timeout:
        try:
            for w in shell.Windows():
                try:
                    folder = w.Document
                    if folder is None:
                        continue
                    self_path = str(folder.Folder.Self.Path)
                    if self_path != path:
                        continue
                    hwnd = int(w.HWND)
                    if hwnd != 0 and _USER32.IsWindow(ctypes.wintypes.HWND(hwnd)):
                        return hwnd
                except Exception as e:
                    logger.debug("Error inspecting ShellWindow: %s", e)
                    continue
        except Exception as e:
            logger.debug("Error enumerating ShellWindows: %s", e)
        time.sleep(WAIT_INTERVAL)
    logger.warning("Timeout waiting for HWND for path: %s", path)
    return None


# ─── 会话文件名（带时间戳） ──────────────────────────

def generate_session_name() -> str:
    """生成默认会话名称：2026-05-08_143052"""
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ─── 核心 API ──────────────────────────────────────────

def get_open_windows() -> list[dict]:
    """
    获取所有打开的 Explorer 窗口信息。
    对应 Get-ExplorerSessions.ps1
    返回: [{"Path": str, "Left": int, "Top": int, "Width": int, "Height": int}, ...]
    """
    results = []
    _init_com()
    try:
        shell = _get_shell()
        for w in shell.Windows():
            try:
                folder = w.Document
                if folder is None:
                    continue
                self_path = folder.Folder.Self.Path
                if self_path is None:
                    continue
                results.append({
                    "Path": str(self_path),
                    "Left": int(getattr(w, "Left", 0)),
                    "Top": int(getattr(w, "Top", 0)),
                    "Width": int(getattr(w, "Width", 0)),
                    "Height": int(getattr(w, "Height", 0)),
                })
            except AttributeError:
                # 非资源管理器窗口（IE、控制面板等）跳过
                continue
            except Exception as e:
                logger.warning("Error reading window info: %s", e)
                continue
    except Exception as e:
        logger.error("Failed to enumerate Explorer windows: %s", e)
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


def _restore_single_window(
    item: dict,
    index: int,
    total: int,
    shell,
) -> bool:
    """
    恢复单个窗口（提取自 restore_session / restore_windows_from_session 的公共逻辑）。
    
    Args:
        item: 窗口数据字典（包含 Path, Left, Top, Width, Height）
        index: 当前进度索引（1-based，用于日志）
        total: 总窗口数（用于日志）
        shell: 复用的 Shell.Application COM 对象
        
    Returns:
        bool: 恢复成功返回 True
    """
    path_str = str(item.get("Path", ""))
    if not path_str:
        logger.warning("Skipping empty path at index %d/%d", index, total)
        return False

    try:
        shell.Open(path_str)

        hwnd = _wait_for_window_hwnd(path_str, shell=shell)
        if hwnd is None:
            logger.warning("Timeout waiting for HWND for %s", path_str)
            return False

        left = int(item.get("Left", 0))
        top = int(item.get("Top", 0))
        width = int(item.get("Width", 800))
        height = int(item.get("Height", 600))

        # ── 坐标修正：将窗口 clamp 到虚拟桌面范围内 ──
        virt_left = _USER32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        virt_top = _USER32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        virt_width = _USER32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        virt_height = _USER32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        left = max(virt_left, min(left, virt_left + virt_width - max(width, MIN_VISIBLE_WIDTH)))
        top = max(virt_top, min(top, virt_top + virt_height - max(height, MIN_VISIBLE_HEIGHT)))

        ret = _USER32.SetWindowPos(
            ctypes.wintypes.HWND(hwnd),
            ctypes.wintypes.HWND(0),  # HWND_TOP
            ctypes.c_int(left),
            ctypes.c_int(top),
            ctypes.c_int(width),
            ctypes.c_int(height),
            ctypes.c_uint(0x0040),  # SWP_SHOWWINDOW
        )
        if not ret:
            logger.warning("SetWindowPos failed for %s (hwnd=%d)", path_str, hwnd)
            return False
        return True
    except Exception as e:
        logger.warning("Failed to restore window %s: %s", path_str, e)
        return False


def restore_session(
    name: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int]:
    """
    恢复指定会话。
    对应 Restore-Session.ps1
    使用轮询替代 sleep(0.3) 等待窗口创建，提高可靠性。
    
    Args:
        name: 会话名称
        progress_callback: 进度回调 (success, failed, current_path)
        
    Returns:
        (成功数, 失败数)
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

    total = len(data)
    logger.info("Restoring session: %s (%d windows)", name, total)

    _init_com()
    shell = _get_shell()
    success = 0
    failed = 0

    for idx, item in enumerate(data):
        ok = _restore_single_window(item, idx + 1, total, shell)
        if ok:
            success += 1
        else:
            failed += 1
        if progress_callback:
            path_str = str(item.get("Path", "")) or "(empty)"
            progress_callback(success, failed, f"[{idx+1}/{total}] {path_str}")

    logger.info("Session restored: %s (%d/%d)", name, success, failed)
    return success, failed


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
) -> tuple[int, int]:
    """
    恢复会话中指定索引的窗口。
    Args:
        name: 会话名称
        indices: 要恢复的窗口索引列表
        progress_callback: 进度回调 (success, failed, current_path)
    Returns:
        (成功数, 失败数)
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

    # 按 indices 提取要恢复的项目
    data = []
    for idx in indices:
        if 0 <= idx < len(all_data):
            data.append(all_data[idx])

    total = len(data)
    if total == 0:
        return 0, 0

    logger.info("Restoring %d windows from session %s", total, name)

    _init_com()
    shell = _get_shell()
    success = 0
    failed = 0

    for idx, item in enumerate(data):
        ok = _restore_single_window(item, idx + 1, total, shell)
        if ok:
            success += 1
        else:
            failed += 1
        if progress_callback:
            path_str = str(item.get("Path", "")) or "(empty)"
            progress_callback(success, failed, f"[{idx+1}/{total}] {path_str}")

    logger.info("Session restored: %s (%d/%d)", name, success, failed)
    return success, failed


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
