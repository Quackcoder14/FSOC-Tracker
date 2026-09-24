# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

backend_dir = Path.cwd()

a = Analysis(
    ['main.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[
        ('configs/*.yaml', 'configs'),
        ('templates/*.j2', 'templates'),
        ('models/*.onnx', 'models'),
    ],
    hiddenimports=[
        'scipy.special.cython_special',
        'onnxruntime',
        'websockets',
        'msgpack',
        'jinja2',
        'cv2',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'notebook', 'IPython'],
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
    name='fsoc-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
