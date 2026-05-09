"""测试 hotkey_manager — 热键字符串解析类"""

from app.hotkey_manager import HotkeyManager


class TestHotkeyValidation:
    def test_valid_modifier_key_combos(self):
        assert HotkeyManager.validate("Ctrl+Shift+S") is True
        assert HotkeyManager.validate("Alt+F1") is True
        assert HotkeyManager.validate("Win+E") is True
        assert HotkeyManager.validate("Ctrl+Alt+Delete") is True
        assert HotkeyManager.validate("Shift+F12") is True

    def test_single_keys_without_modifier_are_invalid(self):
        """单键无修饰符时 validate 返回 False（设计要求必须带修饰符）"""
        assert HotkeyManager.validate("F5") is False
        assert HotkeyManager.validate("Space") is False
        assert HotkeyManager.validate("Enter") is False
        assert HotkeyManager.validate("Escape") is False
        assert HotkeyManager.validate("Tab") is False

    def test_invalid_keys(self):
        assert HotkeyManager.validate("") is False
        assert HotkeyManager.validate("InvalidKey") is False
        assert HotkeyManager.validate("Ctrl+Invalid") is False
        assert HotkeyManager.validate("Ctrl+Shift+InvalidKey") is False

    def test_modifier_name_map_keys(self):
        """验证 MOD_NAME_MAP 包含所有预期的修饰符"""
        from app.hotkey_manager import MOD_NAME_MAP
        assert "Ctrl" in MOD_NAME_MAP
        assert "Shift" in MOD_NAME_MAP
        assert "Alt" in MOD_NAME_MAP
        assert "Win" in MOD_NAME_MAP

    def test_vk_map_keys(self):
        """验证 VK_MAP 包含所有预期的虚拟键码"""
        from app.hotkey_manager import VK_MAP
        assert "A" in VK_MAP
        assert "Z" in VK_MAP
        assert "0" in VK_MAP
        assert "9" in VK_MAP
        assert "F1" in VK_MAP
        assert "F12" in VK_MAP
        assert "Space" in VK_MAP
