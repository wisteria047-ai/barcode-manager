# -*- mode: python ; coding: utf-8 -*-
"""
PassportManager PyInstaller spec file
macOS: .app バンドル生成
Windows: 単一 .exe 生成
"""

import sys
import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(base_dir, 'passport_manager.py')],
    pathex=[base_dir],
    binaries=[],
    datas=[
        (os.path.join(base_dir, 'sample_passports.csv'), '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'test', 'unittest', 'xmlrpc', 'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'darwin':
    # ── macOS: .app バンドル ──
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='PassportManager',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        target_arch=None,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name='PassportManager',
    )
    app = BUNDLE(
        coll,
        name='PassportManager.app',
        icon=os.path.join(base_dir, 'icon.icns') if os.path.exists(os.path.join(base_dir, 'icon.icns')) else None,
        bundle_identifier='com.passportmanager.app',
        info_plist={
            'CFBundleName': 'PassportManager',
            'CFBundleDisplayName': 'パスポート管理システム',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
        },
    )
else:
    # ── Windows: 単一 .exe ──
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
        [],
        name='PassportManager',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        icon=os.path.join(base_dir, 'icon.ico') if os.path.exists(os.path.join(base_dir, 'icon.ico')) else None,
    )
