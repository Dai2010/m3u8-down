from __future__ import annotations

import configparser
import os
import platform
import shutil
import subprocess
from pathlib import Path


THEME_OPTIONS = ("system", "light", "dark")


def normalize_theme(value: object) -> str:
    theme = str(value or "system").strip().lower()
    return theme if theme in THEME_OPTIONS else "system"


def should_use_dark_theme(preference: object = "system", *, default: bool = False) -> bool:
    theme = normalize_theme(preference)
    if theme == "dark":
        return True
    if theme == "light":
        return False

    override = _environment_theme()
    if override == "dark":
        return True
    if override == "light":
        return False

    detected = system_prefers_dark()
    return default if detected is None else detected


def system_prefers_dark() -> bool | None:
    env_detected = _detect_environment_dark()
    if env_detected is not None:
        return env_detected

    if platform.system() == "Windows":
        return _windows_prefers_dark()
    return _linux_prefers_dark()


def _environment_theme() -> str:
    value = os.environ.get("M3U8_DOWNLOADER_THEME", "")
    theme = normalize_theme(value)
    return "" if not value or theme == "system" else theme


def _detect_environment_dark() -> bool | None:
    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if gtk_theme:
        return "dark" in gtk_theme

    colorfgbg = os.environ.get("COLORFGBG", "")
    if ";" in colorfgbg:
        background = colorfgbg.split(";")[-1]
        if background.isdigit():
            return int(background) < 8
    return None


def _windows_prefers_dark() -> bool | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as registry_key:
            value, _ = winreg.QueryValueEx(registry_key, "AppsUseLightTheme")
        return int(value) == 0
    except Exception:
        return None


def _linux_prefers_dark() -> bool | None:
    gnome_value = _gnome_color_scheme()
    if gnome_value is not None:
        return gnome_value

    kde_value = _kde_color_scheme()
    if kde_value is not None:
        return kde_value
    return None


def _gnome_color_scheme() -> bool | None:
    if not shutil.which("gsettings"):
        return None
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip().strip("'").lower()
    if "dark" in value:
        return True
    if "light" in value or "default" in value:
        return False
    return None


def _kde_color_scheme() -> bool | None:
    kdeglobals = Path.home() / ".config" / "kdeglobals"
    if not kdeglobals.exists():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(kdeglobals, encoding="utf-8")
        scheme = parser.get("General", "ColorScheme", fallback="").lower()
    except Exception:
        return None
    if "dark" in scheme:
        return True
    if scheme:
        return False
    return None
