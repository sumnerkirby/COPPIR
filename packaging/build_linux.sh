#!/usr/bin/env bash
# Build COPPIR for Linux.
# Produces: dist/COPPIR-linux.tar.gz  and  dist/COPPIR-linux/coppir.desktop
#
# Requirements (install before running):
#   System packages (Ubuntu/Debian):
#     sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1 \
#                      libgtk-3-dev libgirepository1.0-dev gcc pkg-config
#   Python packages:
#     pip install pyinstaller pillow
#     pip install pywebview[gtk]   (or install via apt: python3-webview)
#
#   On Fedora/RHEL replace the apt packages with:
#     sudo dnf install python3-gobject webkit2gtk4.1 gtk3-devel gobject-introspection-devel
#
# Run from the packaging/ directory:
#   cd packaging && bash build_linux.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
DIST="$SCRIPT_DIR/dist"
OUT_DIR="$DIST/COPPIR-linux"

echo "==> Installing Python build dependencies"
pip install --quiet pyinstaller pillow

echo "==> Generating icons"
python "$SCRIPT_DIR/make_icons.py"

echo "==> Running PyInstaller"
cd "$ROOT"
pyinstaller \
    --distpath "$DIST" \
    --workpath "$SCRIPT_DIR/build_tmp" \
    --noconfirm \
    "$SCRIPT_DIR/coppir.spec"

BIN="$DIST/COPPIR/COPPIR"
if [ ! -f "$BIN" ]; then
    echo "ERROR: $BIN not found — PyInstaller may have failed."
    exit 1
fi

# Rename the output folder so the tarball has a predictable name
mv "$DIST/COPPIR" "$OUT_DIR"

# Write a .desktop launcher so the app appears in system menus
DESKTOP_ICON="$OUT_DIR/icon.png"
cp "$SCRIPT_DIR/icon.png" "$DESKTOP_ICON"

cat > "$OUT_DIR/coppir.desktop" << EOF
[Desktop Entry]
Type=Application
Name=COPPIR
GenericName=Common Operational Picture Program for Incident Response
Exec=$OUT_DIR/COPPIR
Icon=$DESKTOP_ICON
Terminal=false
Categories=Utility;
EOF
chmod +x "$OUT_DIR/coppir.desktop"

echo "==> Creating tarball"
TAR="$DIST/COPPIR-linux.tar.gz"
tar -czf "$TAR" -C "$DIST" "COPPIR-linux"

echo ""
echo "Build complete: $TAR"
echo ""
echo "Distribute COPPIR-linux.tar.gz. Users extract and run:"
echo "  tar -xzf COPPIR-linux.tar.gz"
echo "  ./COPPIR-linux/COPPIR"
echo ""
echo "To add to the system application menu:"
echo "  cp COPPIR-linux/coppir.desktop ~/.local/share/applications/"
echo ""
echo "NOTE: The binary links against the system WebKit2GTK library."
echo "Users must have these packages installed:"
echo "  Ubuntu/Debian:  python3-gi  gir1.2-webkit2-4.1  (or webkit2-4.0)"
echo "  Fedora/RHEL:    python3-gobject  webkit2gtk4.1"
