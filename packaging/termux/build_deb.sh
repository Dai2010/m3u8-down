#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-4.2.5}"
ARCHITECTURE="${TERMUX_DEB_ARCHITECTURE:-aarch64}"
PACKAGE_ROOT="$ROOT/build/termux-deb-root"
OUT_DIR="$ROOT/build/release"
DATA_DIR="$PACKAGE_ROOT/data/data/com.termux/files/usr/share/m3u8-downloader"
CODE_DIR="$DATA_DIR/m3u8_downloader"
BIN_DIR="$PACKAGE_ROOT/data/data/com.termux/files/usr/bin"

rm -rf "$PACKAGE_ROOT"
mkdir -p \
  "$PACKAGE_ROOT/DEBIAN" \
  "$DATA_DIR" \
  "$CODE_DIR" \
  "$BIN_DIR" \
  "$PACKAGE_ROOT/data/data/com.termux/files/usr/share/doc/m3u8-downloader" \
  "$OUT_DIR"

cat > "$PACKAGE_ROOT/DEBIAN/control" <<CONTROL
Package: m3u8-downloader
Version: $VERSION
Section: video
Priority: optional
Architecture: $ARCHITECTURE
Maintainer: Dai2010 <noreply@github.com>
Depends: python (>= 3.10), ffmpeg
Description: m3u8 downloader CLI and TUI for Termux
 A command-line and terminal user interface for downloading and streaming media.
 This Termux package excludes the desktop GUI and Qt dependencies.
CONTROL

cp "$ROOT/m3u8_downloader/__init__.py" "$ROOT/m3u8_downloader/__main__.py" "$ROOT/m3u8_downloader/main.py" "$CODE_DIR/"
cp -a "$ROOT/m3u8_downloader/config" "$ROOT/m3u8_downloader/core" "$ROOT/m3u8_downloader/tui" "$CODE_DIR/"
find "$CODE_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +
cp "$ROOT/README.md" "$ROOT/USER_MANUAL.md" "$PACKAGE_ROOT/data/data/com.termux/files/usr/share/doc/m3u8-downloader/"

cat > "$BIN_DIR/m3u8-downloader" <<'SH'
#!/data/data/com.termux/files/usr/bin/sh
exec env PYTHONPATH="${PREFIX}/share/m3u8-downloader${PYTHONPATH:+:$PYTHONPATH}" "${PREFIX}/bin/python" -m m3u8_downloader "$@"
SH
cat > "$BIN_DIR/m3u8-downloader-tui" <<'SH'
#!/data/data/com.termux/files/usr/bin/sh
exec env PYTHONPATH="${PREFIX}/share/m3u8-downloader${PYTHONPATH:+:$PYTHONPATH}" "${PREFIX}/bin/python" -m m3u8_downloader.tui.app "$@"
SH
chmod 0755 "$BIN_DIR/m3u8-downloader" "$BIN_DIR/m3u8-downloader-tui"
find "$PACKAGE_ROOT" -type d -exec chmod 0755 {} +
find "$CODE_DIR" "$PACKAGE_ROOT/data/data/com.termux/files/usr/share/doc" -type f -exec chmod 0644 {} +
chmod 0644 "$PACKAGE_ROOT/DEBIAN/control"

dpkg-deb --build "$PACKAGE_ROOT" "$OUT_DIR/m3u8-downloader_${VERSION}_termux_${ARCHITECTURE}.deb"
