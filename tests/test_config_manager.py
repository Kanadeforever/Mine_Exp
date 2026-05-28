"""测试 config_manager — INI 读写、BOM 检测、编码兼容性"""

import sys
from pathlib import Path
import pytest
from app.common import _detect_encoding, read_ini
from app.config_manager import save_config, load_config, CONFIG_FILE


class TestDetectEncoding:
    def test_utf8_no_bom(self, tmp_path: Path):
        f = tmp_path / "test.ini"
        f.write_bytes(b"[General]\nLanguage=zh_CN")
        assert _detect_encoding(f) == "utf-8"

    def test_utf8_bom(self, tmp_path: Path):
        f = tmp_path / "test.ini"
        f.write_bytes(b"\xef\xbb\xbf[General]\nLanguage=zh_CN")
        assert _detect_encoding(f) == "utf-8-sig"

    def test_utf16_le(self, tmp_path: Path):
        f = tmp_path / "test.ini"
        f.write_bytes(b"\xff\xfe[\x00G\x00e\x00n\x00e\x00r\x00a\x00l\x00]")
        assert _detect_encoding(f) == "utf-16-le"

    def test_utf16_be(self, tmp_path: Path):
        f = tmp_path / "test.ini"
        f.write_bytes(b"\xfe\xff\x00[\x00G\x00e\x00n\x00e\x00r\x00a\x00l\x00]")
        assert _detect_encoding(f) == "utf-16-be"


class TestReadIni:
    def test_read_normal(self, tmp_path: Path):
        ini = tmp_path / "test.ini"
        ini.write_text("[Section]\nKey1=Value1\nKey2=Value2", encoding="utf-8")
        result = read_ini(ini)
        assert result == {"Section": {"Key1": "Value1", "Key2": "Value2"}}

    def test_key_case_preserved(self, tmp_path: Path):
        ini = tmp_path / "test.ini"
        ini.write_text("[General]\nSaveBtn=保存\nSavebtn=另存为", encoding="utf-8")
        result = read_ini(ini)
        assert result["General"]["SaveBtn"] == "保存"
        assert result["General"]["Savebtn"] == "另存为"

    def test_file_not_found(self, tmp_path: Path):
        result = read_ini(tmp_path / "nope.ini")
        assert result == {}

    def test_utf8_bom_compatible(self, tmp_path: Path):
        ini = tmp_path / "test.ini"
        # write BOM + content using utf-8-sig (auto adds BOM)
        ini.write_bytes(b"\xef\xbb\xbf[Main]\nTitle=\xe4\xbd\xa0\xe5\xa5\xbd")
        result = read_ini(ini)
        assert result["Main"]["Title"] == "你好"


class TestSaveLoadConfig:
    def test_save_and_load(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("app.config_manager.CONFIG_FILE", tmp_path / "config.ini")
        cfg = {
            "Language": "en_US",
            "SaveSession": "Alt+1",
            "QuickRestore": "Alt+2",
            "AutoSaveEnabled": "true",
            "AutoSaveInterval": "30",
            "AutoSaveMaxCount": "10",
            "LogEnabled": "true",
            "LogMaxEntries": "50",
        }
        save_config(cfg)
        loaded = load_config()
        assert loaded == cfg

    def test_load_defaults_when_missing(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("app.config_manager.CONFIG_FILE", tmp_path / "config.ini")
        # file doesn't exist → should return defaults
        loaded = load_config()
        assert loaded["Language"] == "zh_CN"
        assert loaded["SaveSession"] == "Ctrl+Shift+S"