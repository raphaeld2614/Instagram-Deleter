# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Instagram Eraser (onedir, windowed).

Build from the project root with:
    pyinstaller build/unliker.spec --noconfirm

Why the explicit collect_all / copy_metadata:
  * undetected_chromedriver loads submodules dynamically and reads its own version
    metadata at runtime.
  * selenium ships the `selenium-manager` binary inside the package and reads its
    metadata to locate it; collect_all pulls that binary into the build.
This is an onedir build on purpose — undetected_chromedriver patches/launches a
driver binary and is unreliable under onefile's temp-extraction model.
"""

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

project_root = os.path.dirname(SPECPATH)

datas = []
binaries = []
hiddenimports = []

for pkg in ("undetected_chromedriver", "selenium"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

datas += copy_metadata("undetected_chromedriver")
datas += copy_metadata("selenium")

a = Analysis(
    [os.path.join(project_root, "run_unliker.py")],
    pathex=[project_root],
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
    [],
    exclude_binaries=True,
    name="InstagramEraser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="InstagramEraser",
)
