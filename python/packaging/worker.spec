# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for document-worker one-file executable.

Packages the Python document worker as a standalone binary for bundling as a
Tauri sidecar. The binary is placed in src-tauri/binaries/ with a target-triple
suffix for platform detection during build.
"""

block_cipher = None

a = Analysis(
    ["../src/document_worker/main.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "markitdown",
        "markitdown.converters",
        "markitdown.converters._base_converter",
        "markitdown.converters._csv_converter",
        "markitdown.converters._docx_converter",
        "markitdown.converters._epub_converter",
        "markitdown.converters._html_converter",
        "markitdown.converters._ipynb_converter",
        "markitdown.converters._pdf_converter",
        "markitdown.converters._plaintext_converter",
        "markitdown.converters._pptx_converter",
        "markitdown.converters._xlsx_converter",
        "markitdown.converters._xls_converter",
        "markitdown.converters._zip_converter",
        "onnxruntime",
        "PIL",
        "html5lib",
        "bs4",
        "pypdf",
        "openpyxl",
        "pptx",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    onefile=True,
)
