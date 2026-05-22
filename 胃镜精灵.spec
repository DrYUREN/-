# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 胃镜精灵 — onedir mode"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'config' / 'settings.yaml'), 'config'),
        (str(PROJECT_ROOT / 'config' / 'classes.yaml'), 'config'),
        (str(PROJECT_ROOT / 'config' / 'classes_1class.yaml'), 'config'),
        (str(PROJECT_ROOT / 'models' / 'best.pt'), 'models'),
    ],
    hiddenimports=[
        'ultralytics',
        'ultralytics.nn',
        'ultralytics.utils',
        'ultralytics.data',
        'ultralytics.engine',
        'torch',
        'torchvision',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'yaml',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / 'runtime_hook.py')],
    excludes=[
        'jupyter',
        'notebook',
        'IPython',
        'tkinter',
        'pytest',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='胃镜精灵',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='胃镜精灵',
)
