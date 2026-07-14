# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for PingSentry.

Build with:
    pyinstaller PingSentry.spec

Produces a single self-contained, windowed executable that bundles the
notification sounds (on.wav / off.wav) so alerts work on any machine, with
no console window flashing during ping checks.
"""
import sys
from pathlib import Path

try:
    ROOT = Path(SPECPATH)  # noqa: F821  (SPECPATH injected by PyInstaller)
except NameError:  # pragma: no cover
    ROOT = Path.cwd()

ASSETS = ROOT / "pingsentry" / "assets"

# Bundle the wav assets under pingsentry/assets so notifier._asset_dir()
# resolves them from sys._MEIPASS at runtime.
datas = [
    (str(ASSETS / "on.wav"), "pingsentry/assets"),
    (str(ASSETS / "off.wav"), "pingsentry/assets"),
]

hiddenimports = [
    "pystray._win32",
    "pystray._xorg",
    "pystray._darwin",
    "PIL._tkinter_finder",
]

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="PingSentry",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed: no console window flashes
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "icon.ico") if (ASSETS / "icon.ico").exists() else None,
)

# On macOS, also produce a .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="PingSentry.app",
        icon=str(ASSETS / "icon.icns") if (ASSETS / "icon.icns").exists() else None,
        bundle_identifier="com.pingsentry.app",
        info_plist={
            "NSHighResolutionCapable": "True",
            "LSUIElement": "0",
        },
    )
