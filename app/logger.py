"""
logger.py
日志系统：按启动时间戳生成日志文件到 BASE_DIR/logs/
"""

import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from app.common import get_base_dir
from app.constants import LOG_DEFAULT_MAX_ENTRIES, LOG_MAX_ENTRIES_MIN, LOG_MAX_ENTRIES_MAX

BASE_DIR = get_base_dir()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_PREFIX = "explorerStorage-"
_LOG_GLOB_PATTERN = "explorerStorage-*.log"

# 日志格式
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# 全局文件 handler 及状态
_file_handler: Optional[logging.FileHandler] = None
_log_enabled: bool = True
_max_entries: int = LOG_DEFAULT_MAX_ENTRIES

# 自定义 Logger 注册表（替代 logging.Logger.manager.loggerDict）
_registered_loggers: dict[str, logging.Logger] = {}

# 语言管理器实例（由 AppCore 设置，供其他模块间接访问）
_language_manager: Any = None

# ── 日志文件名正则（用于排序清理） ─────────────────────
_LOG_FILENAME_RE = re.compile(
    rf"^{re.escape(_LOG_PREFIX)}(\d{{4}}-\d{{2}}-\d{{2}}-\d{{2}}-\d{{2}}-\d{{2}})\.log$"
)



def set_language_manager(lm: Any) -> None:
    """设置语言管理器实例，供其他模块间接访问（无循环导入问题）。"""
    global _language_manager
    _language_manager = lm


def get_language_manager() -> Any:
    """获取语言管理器实例。未设置时返回 None。"""
    return _language_manager


def get_logger(name: str) -> logging.Logger:
    """
    获取（或创建）一个按模块命名的 Logger。
    所有 Logger 共享一个文件 Handler，避免重复写入。
    使用自定义注册表 _registered_loggers 替代 logging.Logger.manager.loggerDict，
    避免访问 Python 私有属性带来的兼容性风险。
    """
    if name in _registered_loggers:
        return _registered_loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 使用共享的文件 Handler（如果已创建）
    if _file_handler is not None:
        logger.addHandler(_file_handler)

    # 控制台 Handler（仅在非打包模式输出）
    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(_FORMAT, _DATE_FMT))
        logger.addHandler(ch)

    _registered_loggers[name] = logger
    return logger


def _get_all_loggers() -> list[logging.Logger]:
    """
    遍历自定义注册表中的所有 Logger 对象。
    替代直接访问 logging.Logger.manager.loggerDict 私有属性。
    """
    return list(_registered_loggers.values())


def configure_logging(enabled: bool, max_entries: int) -> None:
    """
    运行时配置日志系统。
    - enabled: 是否启用日志文件输出
    - max_entries: 最多保留的日志文件数（>=5）
    """
    global _file_handler, _log_enabled, _max_entries

    _log_enabled = enabled
    _max_entries = max(max_entries, LOG_MAX_ENTRIES_MIN)

    if enabled:
        # 创建带时间戳的新日志文件
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_file = LOG_DIR / f"{_LOG_PREFIX}{timestamp}.log"
        _file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FMT))

        # 将新 handler 添加到所有已注册的 Logger
        for logger_obj in _get_all_loggers():
            logger_obj.addHandler(_file_handler)
    else:
        # 禁用日志：从所有 Logger 中移除文件 Handler
        if _file_handler is not None:
            for logger_obj in _get_all_loggers():
                logger_obj.removeHandler(_file_handler)
            _file_handler.close()
            _file_handler = None

    # 清理旧日志
    _cleanup_old_logs(_max_entries)


def _cleanup_old_logs(max_entries: int) -> None:
    """
    清理 logs/ 目录下超出 max_entries 数量的旧日志文件。
    文件名格式：explorerStorage-YYYY-MM-DD-HH-MM-SS.log
    按时间戳字符串升序排列，删除最旧的文件。
    """
    if not LOG_DIR.exists():
        return

    try:
        # 获取所有匹配的日志文件
        log_files: list[Path] = []
        for f in LOG_DIR.iterdir():
            if f.is_file() and _LOG_FILENAME_RE.match(f.name):
                log_files.append(f)

        # 按文件名（即按时间戳）升序排列，旧的在前面
        log_files.sort(key=lambda p: p.name)

        if len(log_files) <= max_entries:
            return

        # 删除超出数量的最旧文件
        to_delete = log_files[:len(log_files) - max_entries]
        for f in to_delete:
            try:
                f.unlink()
            except OSError:
                pass
    except Exception:
        pass