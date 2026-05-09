"""
hotkey_manager.py
Win32 全局热键注册管理。
"""

import ctypes
import ctypes.wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter

from app.logger import get_logger

logger = get_logger(__name__)

# ─── Win32 常量 ────────────────────────────────────────
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

# ─── 虚拟键码映射 ─────────────────────────────────────
VK_MAP = {
    **{chr(0x41 + i): 0x41 + i for i in range(26)},          # A-Z
    **{chr(0x30 + i): 0x30 + i for i in range(10)},          # 0-9
    **{f"F{i}": 0x70 + i - 1 for i in range(1, 25)},         # F1-F24
    "Space": 0x20, "Enter": 0x0D, "Escape": 0x1B, "Tab": 0x09,
    "Backspace": 0x08, "Delete": 0x2E, "Insert": 0x2D,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "Left": 0x25, "Right": 0x27, "Up": 0x26, "Down": 0x28,
    # ── 小键盘 ──
    "Numpad0": 0x60, "Numpad1": 0x61, "Numpad2": 0x62, "Numpad3": 0x63,
    "Numpad4": 0x64, "Numpad5": 0x65, "Numpad6": 0x66, "Numpad7": 0x67,
    "Numpad8": 0x68, "Numpad9": 0x69, "NumpadMul": 0x6A,
    "NumpadAdd": 0x6B, "NumpadSub": 0x6D, "NumpadDiv": 0x6F,
    # ── 系统键 ──
    "PrintScreen": 0x2C, "Pause": 0x13, "ScrollLock": 0x91,
    "CapsLock": 0x14, "NumLock": 0x90,
    # ── 符号键 ──
    "OEM1": 0xBA,  # ;:
    "OEMPlus": 0xBB,  # =+
    "OEMComma": 0xBC,  # ,<
    "OEMMinus": 0xBD,  # -_
    "OEMPeriod": 0xBE,  # .>
    "OEM2": 0xBF,  # /?
    "OEM3": 0xC0,  # `~
    "OEM4": 0xDB,  # [{
    "OEM5": 0xDC,  # \|
    "OEM6": 0xDD,  # ]}
    "OEM7": 0xDE,  # '"
    "OEM8": 0xDF,  # misc
}

MOD_NAME_MAP = {
    "Ctrl": MOD_CONTROL, "Shift": MOD_SHIFT,
    "Alt": MOD_ALT, "Win": MOD_WIN,
}
REV_MOD_MAP = {v: k for k, v in MOD_NAME_MAP.items()}


class HotkeyError(Exception):
    """热键注册异常"""
    pass


class HotkeyManager:
    """封装 RegisterHotKey / UnregisterHotKey 调用"""

    def __init__(self, hwnd: int):
        self._hwnd = hwnd
        self._bindings = {}
        self._next_id = 1000

    def register(self, hotkey_str: str, callback) -> bool:
        mods, vk = self._parse(hotkey_str)
        if vk is None:
            raise HotkeyError(f"Invalid hotkey: {hotkey_str}")
        hkid = self._next_id
        self._next_id += 1
        user32 = ctypes.windll.user32
        ok = user32.RegisterHotKey(self._hwnd, hkid, mods | MOD_NOREPEAT, vk)
        if ok:
            self._bindings[hkid] = callback
        else:
            logger.warning("Failed to register hotkey: %s", hotkey_str)
        return bool(ok)

    def unregister_all(self):
        user32 = ctypes.windll.user32
        count = len(self._bindings)
        for hkid in list(self._bindings):
            user32.UnregisterHotKey(self._hwnd, hkid)
        self._bindings.clear()

    def dispatch(self, hkid: int):
        cb = self._bindings.get(hkid)
        if cb:
            try:
                cb()
            except Exception as e:
                logger.exception("Error dispatching hotkey id=%d: %s", hkid, e)

    @staticmethod
    def _parse(s: str):
        parts = s.strip().split("+")
        mods = 0
        vk = None
        for p in parts:
            p = p.strip()
            if p in MOD_NAME_MAP:
                mods |= MOD_NAME_MAP[p]
            else:
                vk = VK_MAP.get(p)
        return mods, vk

    @staticmethod
    def validate(hotkey_str: str) -> bool:
        """验证热键字符串是否有效"""
        mods, vk = HotkeyManager._parse(hotkey_str)
        return vk is not None and mods != 0


class WinHotkeyFilter(QAbstractNativeEventFilter):
    """Win32 事件过滤器（用于 QAbstractNativeEventFilter 的辅助类）"""

    def __init__(self, hk_manager: HotkeyManager):
        super().__init__()
        self.hk_manager = hk_manager

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg_ptr = int(message.__int__())
            msg = ctypes.wintypes.MSG.from_address(msg_ptr)
            if msg.message == WM_HOTKEY:
                hkid = msg.wParam
                self.hk_manager.dispatch(hkid)
                return True, 0
        return False, 0