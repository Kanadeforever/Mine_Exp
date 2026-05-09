"""pytest 共享 fixture"""

from pathlib import Path
import pytest


@pytest.fixture
def session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """将 SESSION_DIR 临时指向 tmp_path/Session，避免污染真实会话"""
    d = tmp_path / "Session"
    d.mkdir()
    import app.config_manager as cm
    monkeypatch.setattr(cm, "SESSION_DIR", d)
    # 同时重新 patch session_manager 模块内的引用
    import app.session_manager as sm
    monkeypatch.setattr(sm, "SESSION_DIR", d)
    return d