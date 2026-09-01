# -*- mode: python ; coding: utf-8 -*-

import os


PROJECT_ROOT = os.path.abspath(SPECPATH)
BUILD_MODE = os.environ.get("MINEEXP_BUILD_MODE", "onefile").lower()
if BUILD_MODE not in {"onefile", "onedir"}:
    raise ValueError(f"Unsupported MINEEXP_BUILD_MODE: {BUILD_MODE}")


a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "language"), "language"),
        (os.path.join(PROJECT_ROOT, "app", "resources"), "app/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Shell.Application 使用动态 COM；不需要 makepy/PythonWin 的类型库生成界面。
        "win32com.client.makepy",
        "win32com.client.selecttlb",
        "win32com.client.genpy",
        "pywin",
        "win32ui",
    ],
    noarchive=False,
    optimize=1,
)


def keep_runtime_file(entry):
    """只保留本项目实际使用的 Qt Widgets Windows 运行时。"""
    name = entry[0].replace("\\", "/").lower()

    # 应用使用自己的 ini 翻译，未加载 Qt .qm 翻译包。
    if name.startswith("pyqt6/qt6/translations/"):
        return False

    # 仅运行在 Windows 桌面；保留平台插件和原生 Windows 11 样式。
    if name.startswith("pyqt6/qt6/plugins/"):
        return name in {
            "pyqt6/qt6/plugins/platforms/qwindows.dll",
            "pyqt6/qt6/plugins/styles/qmodernwindowsstyle.dll",
        }

    return name not in {
        # Qt Core 在 Windows 上使用系统 ICU。禁止从 PATH 误收集 Poppler 等第三方 ICU。
        "icudt78.dll",
        "icuuc.dll",
        # 本项目不使用 Qt PDF、SVG、网络或 OpenGL/Qt Quick 渲染。
        "pyqt6/qt6/bin/opengl32sw.dll",
        "pyqt6/qt6/bin/qt6network.dll",
        "pyqt6/qt6/bin/qt6pdf.dll",
        "pyqt6/qt6/bin/qt6svg.dll",
    }


a.binaries = [entry for entry in a.binaries if keep_runtime_file(entry)]
a.datas = [entry for entry in a.datas if keep_runtime_file(entry)]

pyz = PYZ(a.pure)

exe_options = {
    "name": "MineExp",
    "debug": False,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": True,
    "console": False,
    "disable_windowed_traceback": False,
    "argv_emulation": False,
    "target_arch": None,
    "codesign_identity": None,
    "entitlements_file": None,
    "icon": [os.path.join(PROJECT_ROOT, "app", "resources", "icon.ico")],
}

if BUILD_MODE == "onefile":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        upx_exclude=[],
        runtime_tmpdir=None,
        **exe_options,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **exe_options,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="MineExp",
    )
