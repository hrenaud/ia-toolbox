# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for document-worker one-file executable.

Packages the Python document worker as a standalone binary for bundling as a
Tauri sidecar. The binary is placed in src-tauri/binaries/ with a target-triple
suffix for platform detection during build.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

# Collect all data files, binaries, and hidden imports from MarkItDown
# (include_py_files=False keeps only data, not .py duplicates)
datas_markitdown, binaries_markitdown, hiddenimports_markitdown = collect_all(
    "markitdown", include_py_files=False
)

# MarkItDown depends on magika for file type detection.
# Its ML models and configuration are critical runtime data files.
datas_magika = collect_data_files("magika")
datas_magika_metadata = copy_metadata("magika")

# Combine all collected data and binaries
datas = datas_markitdown + datas_magika + datas_magika_metadata
binaries = binaries_markitdown
hiddenimports = hiddenimports_markitdown

a = Analysis(
    ["../src/document_worker/main.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="document-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
