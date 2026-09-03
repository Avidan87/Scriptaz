# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None
ROOT_DIR = Path('/Users/Avidan/Scriptaz')

datas = [
    (str(ROOT_DIR / 'resources'), 'resources'),
    (str(ROOT_DIR / 'data'), 'data'),
]

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'engine.api',
        'engine.theological_graph',
        'engine.rag_service',
        'core.db',
        'core.models',
        'core.config',
        'services.scheduler',
        'services.macos_dock',
        'AppKit',
        'objc',
        'ui.tray_app',
        'ui.popup_card',
        'ui.settings_dialog',
        'resources.styles',
        'resources.icons',
        'uvicorn',
        'fastapi',
        'pydantic',
        'sqlite3',
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
    [],
    exclude_binaries=True,
    name='Scriptaz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT_DIR / 'resources' / 'icons' / 'Scriptaz.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Scriptaz',
)

app = BUNDLE(
    coll,
    name='Scriptaz.app',
    icon=str(ROOT_DIR / 'resources' / 'icons' / 'Scriptaz.icns'),
    bundle_identifier='com.scriptaz.app',
    info_plist={
        'CFBundleDisplayName': 'Scriptaz',
        'CFBundleName': 'Scriptaz',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2026 Scriptaz. All rights reserved.',
        'NSHighResolutionCapable': 'True',
    },
)
