from __future__ import annotations

import locale
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox, QWidget


FFMPEG_ZIP = "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip"
CN_FFMPEG_ZIP = "https://gh.llkk.cc/https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip"


def ensure_ffmpeg(parent: QWidget | None = None) -> bool:
    if os.name != "nt" or shutil.which("ffmpeg"):
        return True

    answer = QMessageBox.question(
        parent,
        "缺少 FFmpeg",
        "下载合并需要 FFmpeg。当前系统没有找到 ffmpeg.exe，是否自动下载安装到当前用户目录？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False

    try:
        bin_dir = _install_ffmpeg()
    except Exception as exc:  # noqa: BLE001 - show concise GUI failure.
        QMessageBox.critical(parent, "FFmpeg 安装失败", str(exc))
        return False

    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    QMessageBox.information(parent, "FFmpeg 已安装", f"已安装到：{bin_dir}")
    return True


def _install_ffmpeg() -> Path:
    install_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "m3u8-downloader" / "ffmpeg"
    bin_dir = install_root / "bin"
    ffmpeg = bin_dir / "ffmpeg.exe"
    if ffmpeg.exists():
        return bin_dir

    install_root.mkdir(parents=True, exist_ok=True)
    archive = install_root / "ffmpeg.zip"
    errors: list[str] = []
    for url in _candidate_urls():
        try:
            urllib.request.urlretrieve(url, archive)  # noqa: S310 - fixed trusted binary release URLs.
            _extract_ffmpeg(archive, install_root)
            if ffmpeg.exists():
                return bin_dir
            errors.append(f"{url}: 压缩包内没有找到 ffmpeg.exe")
        except Exception as exc:  # noqa: BLE001 - try the next mirror.
            errors.append(f"{url}: {exc}")
    raise RuntimeError("无法自动下载 FFmpeg：\n" + "\n".join(errors))


def _candidate_urls() -> list[str]:
    language = (locale.getlocale()[0] or "").lower()
    timezone = os.environ.get("TZ", "").lower()
    country_hint = "cn" in language or "asia/shanghai" in timezone
    return [CN_FFMPEG_ZIP, FFMPEG_ZIP] if country_hint else [FFMPEG_ZIP, CN_FFMPEG_ZIP]


def _extract_ffmpeg(archive: Path, install_root: Path) -> None:
    bin_dir = install_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith("/bin/ffmpeg.exe") or name.endswith("/bin/ffprobe.exe"):
                target = bin_dir / Path(name).name
                with zf.open(name) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
