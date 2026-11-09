#!/usr/bin/env bash
# Install LRBar-RankGen for the current user (no root required).
#
#   bash linux/install.sh                 # install dist/LRBar-RankGen
#   bash linux/install.sh path/to/binary  # install a different build
#   bash linux/install.sh --uninstall     # remove the app, keep user data
set -eu

APP_NAME="LRBar-RankGen"
APP_ID="lrbar-rankgen"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="$DATA_HOME/$APP_ID"
BIN_LINK="$BIN_HOME/$APP_ID"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_ROOT="$DATA_HOME/icons/hicolor"

usage() {
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
}

uninstall() {
    rm -f "$BIN_LINK" "$DESKTOP_DIR/$APP_ID.desktop"
    for size in 16 24 32 48 64 128 256; do
        rm -f "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
    done
    rm -rf "$APP_DIR"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    fi
    echo "Removed $APP_NAME."
    echo "Your projects, templates and licence stay in:"
    echo "  $DATA_HOME/$APP_NAME"
    echo "  ${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
}

if [ "${1:-}" = "--uninstall" ]; then
    uninstall
    exit 0
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

SOURCE="${1:-$ROOT/dist/$APP_NAME}"
if [ ! -f "$SOURCE" ]; then
    echo "Build not found: $SOURCE" >&2
    echo "Run 'python build_linux.py' first, or pass the binary path." >&2
    exit 1
fi

mkdir -p "$APP_DIR" "$BIN_HOME" "$DESKTOP_DIR"
install -m 0755 "$SOURCE" "$APP_DIR/$APP_NAME"
ln -sfn "$APP_DIR/$APP_NAME" "$BIN_LINK"

for size in 16 24 32 48 64 128 256; do
    src="$ROOT/icons/$APP_ID-$size.png"
    [ -f "$src" ] || continue
    mkdir -p "$ICON_ROOT/${size}x${size}/apps"
    install -m 0644 "$src" "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
done

cat > "$DESKTOP_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Ranking Video Generator
Comment=Create animated ranking videos with a live preview
Exec=$BIN_LINK
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Video;Graphics;
StartupNotify=true
StartupWMClass=$APP_NAME
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q "$ICON_ROOT" >/dev/null 2>&1 || true
fi

echo "Installed $APP_NAME to $APP_DIR/$APP_NAME"
echo "Launcher: $BIN_LINK"
echo "Desktop entry: $DESKTOP_DIR/$APP_ID.desktop"
case ":$PATH:" in
    *":$BIN_HOME:"*) ;;
    *) echo "Note: add $BIN_HOME to PATH to run '$APP_ID' from a terminal." ;;
esac
