#!/usr/bin/env bash
# Build COPPIR for macOS.
# Produces: dist/COPPIR-mac.dmg
#
# Requirements:
#   - Python 3.10+ with pip
#   - Xcode Command Line Tools  (xcode-select --install)
#   - All Python dependencies installed in the active environment
#
# Run from the packaging/ directory:
#   cd packaging && bash build_mac.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
DIST="$SCRIPT_DIR/dist"

echo "==> Installing build dependencies"
pip install --quiet pyinstaller pillow

echo "==> Generating icons"
python3 "$SCRIPT_DIR/make_icons.py"

echo "==> Converting icon.iconset -> icon.icns"
iconutil -c icns "$SCRIPT_DIR/icon.iconset" -o "$SCRIPT_DIR/icon.icns"

echo "==> Running PyInstaller"
# Run from ROOT so that relative imports in main.py resolve correctly.
cd "$ROOT"
pyinstaller \
    --distpath "$DIST" \
    --workpath "$SCRIPT_DIR/build_tmp" \
    --noconfirm \
    "$SCRIPT_DIR/coppir.spec"

APP="$DIST/COPPIR.app"

if [ ! -d "$APP" ]; then
    echo "ERROR: $APP not found — PyInstaller may have failed."
    exit 1
fi

echo "==> Creating DMG"
DMG="$DIST/COPPIR-mac.dmg"
# Create a temporary sparse image large enough to hold the .app
hdiutil create \
    -volname "COPPIR" \
    -srcfolder "$APP" \
    -ov \
    -format UDZO \
    "$DMG"

echo ""
echo "Build complete: $DMG"
echo ""
echo "Distribute COPPIR-mac.dmg. Users open it, drag COPPIR.app to Applications,"
echo "then double-click to launch."
echo ""
echo "Note: The app is not code-signed. On first launch users may need to:"
echo "  System Settings > Privacy & Security > Open Anyway"
