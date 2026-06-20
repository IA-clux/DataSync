# -*- mode: python ; coding: utf-8 -*-
# Onefile-Build der DataSync-Anwendung.
# Alle Laufzeit-Abhängigkeiten (Zertifikate, Icon, .env-Secrets) werden in die
# einzelne DataSync.exe eingebettet und zur Laufzeit nach sys._MEIPASS entpackt.

a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Project\\OAuth\\certs', 'certs'),   # -> sys._MEIPASS/certs/localhost(-key).pem
        ('Project\\ico.ico', '.'),            # -> sys._MEIPASS/ico.ico (Tray-Icon)
        ('.env', '.'),                        # -> sys._MEIPASS/.env (AZURE-Secrets)
    ],
    hiddenimports=[
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.edge',
        'selenium.webdriver.edge.webdriver',
        'selenium.webdriver.edge.options',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.webelement',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'pystray._win32',                     # dynamisch geladenes Tray-Backend
        'PIL._tkinter_finder',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='DataSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Project\\ico.ico'],
)
