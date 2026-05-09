# 单元测试 — Mine Exp

本项目使用 [pytest](https://docs.pytest.org/) 作为测试框架，共包含 **36 项测试用例**，覆盖核心模块的全部公开函数。

---

## 目录结构

```
tests/
├── README.md                        # 本文件
├── __init__.py                      # 包声明（使 pytest 能发现测试）
├── conftest.py                      # 共享 fixture 配置
├── test_config_manager.py           # 配置模块测试
├── test_hotkey_manager.py           # 热键模块测试
├── test_language_manager.py         # 多语言模块测试
└── test_session_manager.py          # 会话管理模块测试
```

---

## 测试内容总览

### 1. `test_config_manager.py` — 配置管理（11 项）

| 测试类 | 测试用例 | 覆盖内容 |
|--------|---------|---------|
| `TestDetectEncoding` | 4 项 | UTF‑8（无 BOM）、UTF‑8‑BOM、UTF‑16 LE、UTF‑16 BE 编码自动检测 |
| `TestReadIni` | 4 项 | 正常读值、键名大小写保留、文件不存在时返回空字典、BOM 兼容读取 |
| `TestSaveLoadConfig` | 3 项 | 保存再加载闭环、配置文件缺失时返回默认值 |

### 2. `test_hotkey_manager.py` — 热键验证（7 项）

| 测试类 | 测试用例 | 覆盖内容 |
|--------|---------|---------|
| `TestHotkeyValidation` | 5 项 | 合法组合键（Ctrl+Shift+S, Alt+F1 等）、单键无修饰符拒绝、非法键名拒绝、修饰符映射表完整性、虚拟键码表完整性 |

### 3. `test_language_manager.py` — 多语言翻译（6 项）

| 测试类 | 测试用例 | 覆盖内容 |
|--------|---------|---------|
| `TestLanguageManager` | 6 项 | 中文加载、英文加载、回退机制（不存在的语言 → zh_CN）、缺失键名返回原文、中文参数替换（`%1` `%2`）、英文参数替换 |

### 4. `test_session_manager.py` — 会话管理（12 项）

| 测试类 | 测试用例 | 覆盖内容 |
|--------|---------|---------|
| `TestSessionName` | 1 项 | 会话文件名格式验证（`YYYY-MM-DD_HHMMSS`） |
| `TestSessionExists` | 2 项 | 存在/不存在判断 |
| `TestSaveSession` | 2 项 | 按名保存创建文件、JSON 内容合法性 |
| `TestListSessions` | 2 项 | 空列表、按修改时间倒序排列 |
| `TestDeleteSession` | 2 项 | 删除已存在、删除不存在 |
| `TestRenameSession` | 4 项 | 重命名成功、同名重命名（不做操作）、重命名不存在（拒绝）、覆盖保护（目标已存在则拒绝） |
| `TestGetLatestSession` | 2 项 | 获取最新会话、无会话返回 None |

---

## 运行方法

确保虚拟环境已激活：

```cmd
venv\Scripts\activate
```

### 运行全部测试

```cmd
pytest tests\ -v
```

### 运行单个测试文件

```cmd
pytest tests\test_session_manager.py -v
```

### 运行单个测试用例

```cmd
pytest tests\test_session_manager.py::TestRenameSession::test_rename_success -v
```

### 带覆盖率报告（需先安装 pytest-cov）

```cmd
pytest tests\ --cov=app --cov-report=term-missing
```

---

## 隔离机制

所有测试使用 `tmp_path` 临时目录，**不会污染**生产环境：

- **`conftest.py`** 中的 `session_dir` fixture 通过 `monkeypatch` 将 `SESSION_DIR` 重定向到临时路径
- **`test_config_manager.py`** 通过 `monkeypatch` 将 `CONFIG_FILE` 重定向到临时路径
- **`test_language_manager.py`** 在临时目录动态生成翻译文件

测试完成后，所有临时文件自动清理。

---

## 编写新测试的约定

1. 每个模块对应一个 `test_<模块名>.py` 文件
2. 使用类组织相关测试，类名以 `Test` 开头
3. 测试方法签名：`def test_<描述>(self, ...)`
4. 利用 `conftest.py` 中的 `session_dir` fixture（如涉及会话目录操作）
5. 断言使用 `assert` 原生语句
6. 如需临时修改配置/路径，优先使用 `monkeypatch`

### 示例

```python
# tests/test_my_module.py
from app.my_module import my_func

class TestMyFunc:
    def test_basic(self):
        assert my_func("input") == "expected_output"

    def test_edge_case(self):
        assert my_func("") is None