from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "threads": 16,
    "save_dir": "~/Downloads",
    "headers": {
        "Referer": "",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    },
    "filter_keywords": ["adjump", "ad", "banner"],
    "output_format": "mp4",
    "enable_resume": True,
    "proxy_port": 8888,
    "theme": "system",
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
    return _deep_merge(deepcopy(DEFAULT_CONFIG), loaded)


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file_obj:
        json.dump(config, file_obj, indent=2, ensure_ascii=False)
        file_obj.write("\n")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
