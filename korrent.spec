# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['torrent_gui_app/app.py'],
    pathex=['torrent_gui_app'],    binaries=[],
    datas=[
        ('torrent_gui_app/style.qss', '.'),
        ('image/image.png', 'image'),
        ('torrent_gui_app/api_client.py', '.'),
    ],
    hiddenimports=[
        'api_client',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'requests',
        'urllib3',
        'certifi',
        'webbrowser',
        'pyperclip',
        'json',
        'threading',
        'datetime'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'],
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
    name='Korrent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='image/image.png',
)
