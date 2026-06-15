# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=[],
    datas=[('Project\\OAuth\\certs', 'certs'), ('Project\\ico.ico', '.')],
    hiddenimports=['selenium', 'selenium.webdriver', 'selenium.webdriver.edge', 'selenium.webdriver.edge.webdriver', 'selenium.webdriver.edge.options', 'selenium.webdriver.edge.service', 'selenium.webdriver.common', 'selenium.webdriver.common.by', 'selenium.webdriver.remote.webdriver', 'selenium.webdriver.remote.webelement', 'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlldayCareFetcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Project\\ico.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlldayCareFetcher',
)
