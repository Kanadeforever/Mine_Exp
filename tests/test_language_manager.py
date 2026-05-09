"""测试 language_manager — 翻译加载、参数替换、fallback"""

from pathlib import Path
import pytest
from app.language_manager import LanguageManager


@pytest.fixture
def lang_dir(tmp_path: Path) -> Path:
    d = tmp_path / "language"
    d.mkdir()
    # zh_CN.ini
    (d / "zh_CN.ini").write_text(
        "[Main]\nTitle=资源管理器会话保存器\nSaved=已保存会话 %1（%2 个窗口）\n",
        encoding="utf-8",
    )
    # en_US.ini
    (d / "en_US.ini").write_text(
        "[Main]\nTitle=Mine Exp\nSaved=Saved session %1 (%2 windows)\n",
        encoding="utf-8",
    )
    return d


class TestLanguageManager:
    def test_load_zh(self, lang_dir):
        lm = LanguageManager(lang_dir, "zh_CN")
        assert lm.t("Main", "Title") == "资源管理器会话保存器"

    def test_load_en(self, lang_dir):
        lm = LanguageManager(lang_dir, "en_US")
        assert lm.t("Main", "Title") == "Mine Exp"

    def test_fallback_to_zh_when_missing(self, lang_dir):
        lm = LanguageManager(lang_dir, "ja_JP")
        # 不存在 ja_JP → fallback zh_CN
        assert lm.t("Main", "Title") == "资源管理器会话保存器"

    def test_key_not_found_returns_key(self, lang_dir):
        lm = LanguageManager(lang_dir, "zh_CN")
        assert lm.t("Nope", "Missing") == "Missing"

    def test_parameter_substitution(self, lang_dir):
        lm = LanguageManager(lang_dir, "zh_CN")
        result = lm.t("Main", "Saved", "test_session", "5")
        assert result == "已保存会话 test_session（5 个窗口）"

    def test_parameter_substitution_en(self, lang_dir):
        lm = LanguageManager(lang_dir, "en_US")
        result = lm.t("Main", "Saved", "test_session", "5")
        assert result == "Saved session test_session (5 windows)"