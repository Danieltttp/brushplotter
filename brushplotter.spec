# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para brushplotter (macOS .app).

Uso:
    pyinstaller brushplotter.spec

Genera:
    dist/brushplotter.app

Estructura asumida:
    Este .spec vive dentro del paquete brushplotter/, junto a __main__.py.
    Para que PyInstaller resuelva los imports `from .core.x import y` y
    similares, tratamos al PADRE de esta carpeta como pathex.
"""

import os
from pathlib import Path

# Esta .spec vive DENTRO del paquete brushplotter/, así que:
# - PACKAGE_DIR = brushplotter/ (carpeta de este .spec)
# - PROJECT_PARENT = padre, donde Python encuentra "brushplotter" como módulo
PACKAGE_DIR = Path(SPECPATH).resolve()
PROJECT_PARENT = PACKAGE_DIR.parent

block_cipher = None


# ── Hidden imports ──
# Módulos que PyInstaller no detecta por introspección (importaciones
# dinámicas, plugins, etc.).
hiddenimports = [
    # Qt
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Procesamiento de SVG
    "svgpathtools",
    "svgpathtools.parser",
    # vpype y dependencias indirectas
    "vpype",
    "vpype.io",
    "vpype.config",
    "shapely",
    "shapely.geometry",
    # SDK de Bantam Tools (si está instalado en el venv)
    "nextdraw",
    "nextdraw.nextdraw",
    "numpy",
]

datas = []

icon_path = PACKAGE_DIR / "resources" / "brushplotter.icns"

# El script de entrada es __main__.py del paquete brushplotter.
# PyInstaller lo trata como un script directo.
a = Analysis(
    [str(PACKAGE_DIR / "__main__.py")],
    pathex=[str(PROJECT_PARENT)],   # ← para que `import brushplotter.core...` funcione
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtNetwork",
        "PySide6.QtWebEngineCore",
        "PySide6.QtMultimedia",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtTest",
        "PySide6.QtXml",
        "PySide6.QtSql",
        "pytest",
        "_pytest",
    ],
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
    name="brushplotter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="brushplotter",
)


app = BUNDLE(
    coll,
    name="brushplotter.app",
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier="com.danielgarciaandujar.brushplotter",
    version="0.0.8",
    info_plist={
        "CFBundleName": "brushplotter",
        "CFBundleDisplayName": "brushplotter",
        "CFBundleVersion": "0.0.8",
        "CFBundleShortVersionString": "0.0.8",
        "CFBundleIdentifier": "com.danielgarciaandujar.brushplotter",
        "CFBundleExecutable": "brushplotter",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSAppleEventsUsageDescription": (
            "brushplotter necesita comunicarse con el plotter "
            "NextDraw/AxiDraw conectado por USB."
        ),
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Scalable Vector Graphics",
                "CFBundleTypeExtensions": ["svg"],
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
            }
        ],
        "NSHumanReadableCopyright": (
            "© 2026 Daniel García Andújar. Licencia GPL-3.0."
        ),
    },
)
