from m3u8_downloader.config.manager import delete_profile, load_config, save_config, upsert_profile
from m3u8_downloader.config.theme import normalize_theme, should_use_dark_theme


def test_load_config_merges_defaults(tmp_path):
    path = tmp_path / "config.json"
    save_config({"threads": 4, "headers": {"Referer": "https://example.com"}}, path)

    config = load_config(path)

    assert config["threads"] == 4
    assert config["headers"]["Referer"] == "https://example.com"
    assert "User-Agent" in config["headers"]


def test_load_config_migrates_legacy_default_keywords(tmp_path):
    path = tmp_path / "config.json"
    save_config({"filter_keywords": ["adjump", "ad", "banner"]}, path)

    config = load_config(path)

    assert config["filter_keywords"] == ["/video/adjump/"]


def test_profile_helpers_keep_at_least_one_profile():
    profiles = upsert_profile([], 0, {"name": "A", "threads": "4", "tags": [" x ", ""]})

    assert profiles[0]["name"] == "A"
    assert profiles[0]["threads"] == 4
    assert profiles[0]["tags"] == ["x"]
    assert delete_profile(profiles, 0)[0]["name"] == "默认配置"


def test_theme_preference_normalization(monkeypatch):
    monkeypatch.delenv("M3U8_DOWNLOADER_THEME", raising=False)

    assert normalize_theme("DARK") == "dark"
    assert normalize_theme("bad") == "system"
    assert should_use_dark_theme("dark") is True
    assert should_use_dark_theme("light") is False
