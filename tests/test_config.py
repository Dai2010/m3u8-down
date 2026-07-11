from m3u8_downloader.config.manager import load_config, save_config


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
