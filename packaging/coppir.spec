# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for COPPIR.
# Run from the packaging/ directory via the platform build scripts.
# Do not invoke directly with pyinstaller unless you have generated the
# icon files first (make_icons.py) and are inside the packaging/ directory.

import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH)   # packaging/
ROOT     = SPEC_DIR.parent  # project root (contains run.py, main.py, static/)

# Platform-specific icon
if sys.platform == 'darwin':
    icon_file = str(SPEC_DIR / 'icon.icns')
elif sys.platform == 'win32':
    icon_file = str(SPEC_DIR / 'icon.ico')
else:
    icon_file = str(SPEC_DIR / 'icon.png')

a = Analysis(
    [str(ROOT / 'run.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Bundle the entire static/ tree so the FastAPI server can serve it.
        (str(ROOT / 'static'), 'static'),
    ],
    hiddenimports=[
        # main.py is referenced as 'main:app' in a string in the dev code path.
        # The frozen code path does `from main import app`, but list it explicitly
        # to be safe.
        'main',

        # uvicorn dynamically loads its protocol and loop backends by name.
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',

        # httpx async backend
        'anyio',
        'anyio._backends._asyncio',
        'httpcore',

        # pydantic v2 ships a bundled v1 compatibility shim
        'pydantic.v1',
        'pydantic_core',

        # pywebview platform backends — PyInstaller only bundles the one that
        # exists on the current platform; unused entries are silently ignored.
        'webview.platforms.cocoa',          # macOS
        'webview.platforms.edgechromium',   # Windows (WebView2)
        'webview.platforms.winforms',       # Windows (fallback)
        'webview.platforms.gtk',            # Linux
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy test/dev packages that may be in the environment.
        'pytest', 'IPython', 'notebook', 'matplotlib',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='COPPIR',
    debug=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window on Windows / macOS
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='COPPIR',
)

# macOS .app bundle — only meaningful when building on macOS.
# PyInstaller ignores BUNDLE on other platforms.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='COPPIR.app',
        icon=icon_file,
        bundle_identifier='com.coppir.app',
        info_plist={
            'CFBundleName':             'COPPIR',
            'CFBundleDisplayName':      'COPPIR',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable':  True,
            # Allow the embedded server to make outbound HTTP calls
            # (Overpass / Nominatim geocoding).
            'NSAppTransportSecurity': {
                'NSAllowsArbitraryLoads': True,
            },
        },
    )
