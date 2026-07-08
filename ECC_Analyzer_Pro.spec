# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller build spec for ECC Analyzer Pro.

This project uses PySide6 + Matplotlib, so the default release target is an
onedir portable package instead of a single-file executable. Onedir builds are
larger, but they are usually much more stable for Qt desktop applications.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


# Matplotlib needs its font/data files at runtime.
datas = []
datas += collect_data_files("matplotlib")

# Keep user-facing docs beside the executable.
datas += [
    ("README.md", "."),
    ("USER_GUIDE.md", "."),
]

hiddenimports = []
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("matplotlib.backends")
hiddenimports += [
    "matplotlib.backends.backend_qtagg",
    "mplcursors",
    "scipy.signal",
    "scipy.integrate",
    "pandas",
    "openpyxl",
    "xlrd",
]


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ECC Analyzer Pro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ECC_Analyzer_Pro",
)
