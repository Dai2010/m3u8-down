#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-0.4.0}"
DEB_ROOT="$ROOT/build/deb-root"
OUT_DIR="$ROOT/build/release"

rm -rf "$DEB_ROOT"
mkdir -p \
  "$DEB_ROOT/DEBIAN" \
  "$DEB_ROOT/usr/bin" \
  "$DEB_ROOT/usr/share/applications" \
  "$DEB_ROOT/usr/share/man/man1" \
  "$DEB_ROOT/usr/share/m3u8-downloader" \
  "$OUT_DIR"

cat > "$DEB_ROOT/DEBIAN/control" <<CONTROL
Package: m3u8-downloader
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Dai2010 <noreply@github.com>
Depends: python3 (>= 3.10), python3-requests, python3-aiohttp, python3-pyqt6, python3-textual, ffmpeg
Recommends: mpv | vlc
Description: m3u8 downloader and ad-filtering streamer
 A self-contained m3u8 downloader and local ad-filtering stream proxy.
CONTROL

cp -a "$ROOT/m3u8_downloader" "$DEB_ROOT/usr/share/m3u8-downloader/"
cp "$ROOT/README.md" "$ROOT/setup.py" "$ROOT/requirements.txt" "$ROOT/requirements-desktop.txt" "$DEB_ROOT/usr/share/m3u8-downloader/"
cp "$ROOT/packaging/linux/m3u8-downloader.desktop" "$DEB_ROOT/usr/share/applications/"
gzip -9c "$ROOT/packaging/linux/m3u8-downloader.1" > "$DEB_ROOT/usr/share/man/man1/m3u8-downloader.1.gz"

cat > "$DEB_ROOT/usr/bin/m3u8-downloader" <<'SH'
#!/bin/sh
PYTHONPATH=/usr/share/m3u8-downloader exec python3 -m m3u8_downloader "$@"
SH
cat > "$DEB_ROOT/usr/bin/m3u8-downloader-gui" <<'SH'
#!/bin/sh
PYTHONPATH=/usr/share/m3u8-downloader exec python3 -m m3u8_downloader.gui.app "$@"
SH
cat > "$DEB_ROOT/usr/bin/m3u8-downloader-tui" <<'SH'
#!/bin/sh
PYTHONPATH=/usr/share/m3u8-downloader exec python3 -m m3u8_downloader.tui.app "$@"
SH
chmod 0755 "$DEB_ROOT/usr/bin/m3u8-downloader" "$DEB_ROOT/usr/bin/m3u8-downloader-gui" "$DEB_ROOT/usr/bin/m3u8-downloader-tui"

for size in 16 32 48 64 128 256 512; do
  icon_dir="$DEB_ROOT/usr/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$icon_dir"
  if command -v convert >/dev/null 2>&1; then
    convert "$ROOT/packaging/assets/m3u8-downloader.png" -resize "${size}x${size}" "$icon_dir/m3u8-downloader.png"
  else
    cp "$ROOT/packaging/assets/m3u8-downloader.png" "$icon_dir/m3u8-downloader.png"
  fi
done

dpkg-deb --build "$DEB_ROOT" "$OUT_DIR/m3u8-downloader_${VERSION}_amd64.deb"
