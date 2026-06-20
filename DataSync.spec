# -*- mode: python ; coding: utf-8 -*-
# Onefile-Build der DataSync-Anwendung (noconsole).
# Alle Laufzeit-Abhängigkeiten (Zertifikate, Icon, .env-Secrets, selenium inkl.
# Selenium-Manager-Binary, keyring + Windows-Backend) werden in die einzelne
# DataSync.exe eingebettet und zur Laufzeit nach sys._MEIPASS entpackt.

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('Project\\OAuth\\certs', 'certs'),   # -> sys._MEIPASS/certs/localhost(-key).pem
    ('Project\\ico.ico', '.'),            # -> sys._MEIPASS/ico.ico (Tray-Icon)
    ('.env', '.'),                        # -> sys._MEIPASS/.env (AZURE-Secrets)
]
binaries = []
hiddenimports = [
    'pystray._win32',                     # dynamisch geladenes Tray-Backend
    'PIL._tkinter_finder',
    'keyring.backends.Windows',           # OS-Keyring (Windows Credential Manager)
]
hiddenimports += collect_submodules('win32ctypes')  # vom keyring-Windows-Backend genutzt

# selenium vollständig (inkl. selenium-manager.exe als Data-Binary)
for pkg in ('selenium', 'keyring'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden


a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
