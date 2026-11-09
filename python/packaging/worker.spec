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

# Anonymization needs spaCy and presidio, and import analysis alone does not
# find either of them. A spaCy model is a package of data loaded by name at
# runtime, and presidio builds its recognizer registry by walking modules. A
# worker frozen without these starts, answers list_anonymization_formats, and
# then dies on the first analyze with no message, because it has already
# redirected its own stderr. Keep this list in step with
# document_worker.anonymization.detection._MODELS; a test asserts that it is.
DETECTION_PACKAGES = (
    "spacy",
    "presidio_analyzer",
    "fr_core_news_sm",
    "en_core_web_sm",
)

datas_detection = []
binaries_detection = []
hiddenimports_detection = []
for package in DETECTION_PACKAGES:
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas_detection += package_datas
    binaries_detection += package_binaries
    hiddenimports_detection += package_hiddenimports
    # The model packages declare their version through metadata, which spaCy
    # reads when it validates a pipeline against the version that trained it.
    datas_detection += copy_metadata(package)

# Combine all collected data and binaries
datas = datas_markitdown + datas_magika + datas_magika_metadata + datas_detection
binaries = binaries_markitdown + binaries_detection
hiddenimports = hiddenimports_markitdown + hiddenimports_detection

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
