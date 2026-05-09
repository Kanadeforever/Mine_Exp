"""
config_manager.py
配置读写，替代 main.py 中的 load_config/save_config 函数。
"""

import sys
import shutil
from pathlib import Path
import configparser

from app.common import get_base_dir, read_ini, _IniParser
from app.logger import get_logger
from app.constants import AUTOSAVE_DEFAULT_INTERVAL, AUTOSAVE_DEFAULT_MAX_COUNT, LOG_DEFAULT_MAX_ENTRIES

logger = get_logger(__name__)


BASE_DIR = get_base_dir()
CONFIG_FILE = BASE_DIR / "config.ini"
SESSION_DIR = BASE_DIR / "Session"
LANGUAGE_DIR = BASE_DIR / "language"


def init_resources():
    """
    PyInstaller frozen 模式：首次启动时释放 language/ 和资源到程序目录，
    使用户可以在 exe 旁边自由编辑/添加翻译文件。
    """
    if not getattr(sys, 'frozen', False):
        return  # 脚本模式直接读取项目下的文件
    # ── 语言文件 ──
    src_lang = Path(sys._MEIPASS) / "language"
    if src_lang.exists() and not LANGUAGE_DIR.exists():
        LANGUAGE_DIR.mkdir(parents=True, exist_ok=True)
        for f in src_lang.iterdir():
            if f.is_file() and f.suffix.lower() == ".ini":
                shutil.copy2(f, LANGUAGE_DIR / f.name)
    # ── 资源文件（图标等） ──
    src_res = Path(sys._MEIPASS) / "app" / "resources"
    if src_res.exists():
        dst_res = BASE_DIR / "app" / "resources"
        if not dst_res.exists():
            dst_res.mkdir(parents=True, exist_ok=True)
            for f in src_res.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst_res / f.name)


# 模块加载时自动释放资源
init_resources()

DEFAULT_CONFIG = {
    "Language": "zh_CN",
    "SaveSession": "Ctrl+Shift+S",
    "QuickRestore": "Ctrl+Shift+R",
    "AutoSaveEnabled": "true",
    "AutoSaveInterval": str(AUTOSAVE_DEFAULT_INTERVAL),
    "AutoSaveMaxCount": str(AUTOSAVE_DEFAULT_MAX_COUNT),
    "LogEnabled": "true",
    "LogMaxEntries": str(LOG_DEFAULT_MAX_ENTRIES),
}



def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if not CONFIG_FILE.exists():
        return cfg
    try:
        raw = read_ini(CONFIG_FILE)
        if "General" in raw:
            cfg["Language"] = raw["General"].get("Language", "zh_CN")
        if "Hotkeys" in raw:
            cfg["SaveSession"] = raw["Hotkeys"].get("SaveSession", "Ctrl+Shift+S")
            cfg["QuickRestore"] = raw["Hotkeys"].get("QuickRestore", "Ctrl+Shift+R")
        if "AutoSave" in raw:
            cfg["AutoSaveEnabled"] = raw["AutoSave"].get("Enabled", "true")
            cfg["AutoSaveInterval"] = raw["AutoSave"].get("IntervalMinutes", str(AUTOSAVE_DEFAULT_INTERVAL))
            cfg["AutoSaveMaxCount"] = raw["AutoSave"].get("MaxCount", str(AUTOSAVE_DEFAULT_MAX_COUNT))
        if "Logging" in raw:
            cfg["LogEnabled"] = raw["Logging"].get("Enabled", "true")
            cfg["LogMaxEntries"] = raw["Logging"].get("MaxEntries", str(LOG_DEFAULT_MAX_ENTRIES))
    except (configparser.Error, OSError) as e:
        logger.warning("Failed to load config, using defaults: %s", e)
    except Exception as e:
        logger.error("Unexpected error loading config: %s", e)
    return cfg


def save_config(cfg: dict):
    try:
        cp = _IniParser()
        cp.add_section("General")
        cp.set("General", "Language", cfg["Language"])
        cp.add_section("Hotkeys")
        cp.set("Hotkeys", "SaveSession", cfg["SaveSession"])
        cp.set("Hotkeys", "QuickRestore", cfg["QuickRestore"])
        cp.add_section("AutoSave")
        cp.set("AutoSave", "Enabled", cfg["AutoSaveEnabled"])
        cp.set("AutoSave", "IntervalMinutes", cfg["AutoSaveInterval"])
        cp.set("AutoSave", "MaxCount", cfg["AutoSaveMaxCount"])
        cp.add_section("Logging")
        cp.set("Logging", "Enabled", cfg["LogEnabled"])
        cp.set("Logging", "MaxEntries", cfg["LogMaxEntries"])
        with open(str(CONFIG_FILE), "w", encoding="utf-8") as f:
            cp.write(f)
    except OSError as e:
        logger.error("Failed to save config: %s", e)
        raise