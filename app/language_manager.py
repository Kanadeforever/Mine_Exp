"""
language_manager.py
语言管理模块，从 INI 文件加载翻译。
"""

from pathlib import Path
from app.common import read_ini


class LanguageManager:
    def __init__(self, lang_dir: Path, lang: str = "zh_CN"):
        self._lang_dir = lang_dir
        self._map = {}
        self.load(lang)

    def load(self, lang: str):
        self._map = {}
        path = self._lang_dir / f"{lang}.ini"
        if not path.exists():
            path = self._lang_dir / "zh_CN.ini"
        if path.exists():
            raw = read_ini(path)
            for sec, kv in raw.items():
                self._map[sec] = kv

    def t(self, module: str, key: str, *args) -> str:
        try:
            s = self._map[module][key]
        except KeyError:
            s = key
        for i, a in enumerate(args, 1):
            s = s.replace(f"%{i}", str(a))
        return s