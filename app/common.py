"""
common.py
项目公共工具函数，不依赖任何 app 内模块（避免循环导入）
"""

import sys
import configparser
from pathlib import Path


def get_base_dir() -> Path:
    """获取程序所在目录（兼容脚本和 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class _IniParser(configparser.ConfigParser):
    """保留 Key 原始大小写的 ConfigParser"""
    def optionxform(self, optionstr: str) -> str:
        return optionstr  # 不转小写


def _detect_encoding(path: Path) -> str:
    """检测 INI 文件编码：BOM → utf-8-sig, 否则 utf-8"""
    raw = path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw[:2] == b"\xff\xfe":
        return "utf-16-le"
    if raw[:2] == b"\xfe\xff":
        return "utf-16-be"
    return "utf-8"


def read_ini(path: Path) -> dict:
    """读取 INI 文件（自动检测 BOM），返回 {section: {key: value}}"""
    result = {}
    if not path.exists():
        return result
    cp = _IniParser(interpolation=None)
    encoding = _detect_encoding(path)
    cp.read(str(path), encoding=encoding)
    for sec in cp.sections():
        result[sec] = {k: v for k, v in cp.items(sec)}
    return result
