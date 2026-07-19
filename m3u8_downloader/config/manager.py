from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .theme import normalize_button_color, normalize_theme


DEFAULT_FILTER_KEYWORDS = ["/video/adjump/"]
LEGACY_DEFAULT_FILTER_KEYWORDS = ["adjump", "ad", "banner"]


DEFAULT_CONFIG: dict[str, Any] = {
    "threads": 16,
    "save_dir": "~/Downloads",
    "headers": {
        "Referer": "",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    },
    "filter_keywords": DEFAULT_FILTER_KEYWORDS,
    "output_format": "mp4",
    "enable_resume": True,
    "bilibili_compat": False,
    "proxy_port": 8888,
    "theme": "system",
    "button_color": "",
    "profiles": [],
}


DEFAULT_PROFILE: dict[str, Any] = {
    "name": "默认配置",
    "tags": [],
    "note": "",
    "ad_filter": False,
    "filter_keywords": DEFAULT_FILTER_KEYWORDS,
    "threads": 16,
    "save_dir": "~/Downloads",
}


def config_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "m3u8-downloader" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or config_path()
    if not target.exists():
        return deepcopy(DEFAULT_CONFIG)
    with target.open("r", encoding="utf-8") as file_obj:
        loaded = json.load(file_obj)
    return _normalize_config(_deep_merge(deepcopy(DEFAULT_CONFIG), loaded))


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    target = path or config_path()
    config = _normalize_config(_deep_merge(deepcopy(DEFAULT_CONFIG), config))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file_obj:
        json.dump(config, file_obj, indent=2, ensure_ascii=False)
        file_obj.write("\n")


def load_profiles(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    source = config or load_config()
    profiles = source.get("profiles") or []
    if not profiles:
        return [profile_from_config(source)]
    return [_normalize_profile(_deep_merge(deepcopy(DEFAULT_PROFILE), profile)) for profile in profiles]


def profile_from_config(config: dict[str, Any]) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_PROFILE)
    profile["filter_keywords"] = _normalize_keywords(list(config.get("filter_keywords", DEFAULT_PROFILE["filter_keywords"])))
    profile["threads"] = int(config.get("threads", DEFAULT_PROFILE["threads"]))
    profile["save_dir"] = config.get("save_dir", DEFAULT_PROFILE["save_dir"])
    return profile


def save_profiles(profiles: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    updated = deepcopy(config or load_config())
    updated["profiles"] = normalize_profiles(profiles)
    save_config(updated)
    return updated


def normalize_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_profile(_deep_merge(deepcopy(DEFAULT_PROFILE), profile)) for profile in profiles]
    return normalized or [deepcopy(DEFAULT_PROFILE)]


def new_profile(name: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = _normalize_profile(_deep_merge(deepcopy(DEFAULT_PROFILE), deepcopy(base or {})))
    profile["name"] = name.strip() or DEFAULT_PROFILE["name"]
    return profile


def upsert_profile(profiles: list[dict[str, Any]], index: int, profile: dict[str, Any]) -> list[dict[str, Any]]:
    updated = normalize_profiles(profiles)
    normalized = _normalize_profile(_deep_merge(deepcopy(DEFAULT_PROFILE), profile))
    if 0 <= index < len(updated):
        updated[index] = normalized
    else:
        updated.append(normalized)
    return normalize_profiles(updated)


def delete_profile(profiles: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    updated = normalize_profiles(profiles)
    if 0 <= index < len(updated):
        del updated[index]
    return normalize_profiles(updated)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    config["theme"] = normalize_theme(config.get("theme", "system"))
    config["button_color"] = normalize_button_color(config.get("button_color", ""))
    config["filter_keywords"] = _normalize_keywords(config.get("filter_keywords", []))
    config["profiles"] = [_normalize_profile(profile) for profile in config.get("profiles", [])]
    return config


def _normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    profile["filter_keywords"] = _normalize_keywords(profile.get("filter_keywords", []))
    profile["tags"] = [str(tag).strip() for tag in profile.get("tags", []) if str(tag).strip()]
    profile["threads"] = _coerce_threads(profile.get("threads", DEFAULT_PROFILE["threads"]))
    profile["name"] = str(profile.get("name") or DEFAULT_PROFILE["name"]).strip()
    profile["note"] = str(profile.get("note", "")).strip()
    profile["save_dir"] = str(profile.get("save_dir") or DEFAULT_PROFILE["save_dir"]).strip()
    profile["ad_filter"] = bool(profile.get("ad_filter", False))
    return profile


def _normalize_keywords(keywords: list[str]) -> list[str]:
    return DEFAULT_FILTER_KEYWORDS.copy() if keywords == LEGACY_DEFAULT_FILTER_KEYWORDS else keywords


def _coerce_threads(value: object) -> int:
    try:
        threads = int(value)
    except (TypeError, ValueError):
        return int(DEFAULT_PROFILE["threads"])
    return max(1, min(128, threads))
