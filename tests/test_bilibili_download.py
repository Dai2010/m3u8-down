from pathlib import Path

import m3u8_downloader.core.bilibili_download as bilibili_download
from m3u8_downloader.core.bilibili import (
    BilibiliInput,
    BilibiliMediaManifest,
    BilibiliPage,
    BilibiliRequestConfig,
    BilibiliRequestSession,
    BilibiliTrack,
)
from m3u8_downloader.core.direct_downloader import DirectDownloadError


def _manifest(track_url: str) -> BilibiliMediaManifest:
    page = BilibiliPage(1, "cid-1", "P1", 1000)
    track = BilibiliTrack(track_url, (), "video", quality_id=80, codec_id=7)
    return BilibiliMediaManifest(
        source_url="https://www.bilibili.com/video/BV1?p=1",
        input=BilibiliInput("https://www.bilibili.com/video/BV1?p=1", "video", bvid="BV1", aid="1"),
        title="title",
        description="",
        cover_url="",
        pages=(page,),
        selected_page=page,
        video_tracks=(track,),
        audio_tracks=(),
        subtitles=(),
    )


def test_bilibili_download_refreshes_expired_track_once(tmp_path, monkeypatch):
    initial = _manifest("https://primary.bilivideo.com/video.m4s?token=old")
    refreshed = _manifest("https://primary.bilivideo.com/video.m4s?token=new")
    download_urls: list[str] = []
    resolve_calls: list[tuple[str, int | None]] = []

    def fake_download(track, output_path: Path, session, options, cancel_callback):
        download_urls.append(track.url)
        if len(download_urls) == 1:
            raise DirectDownloadError("HTTP 403", status_code=403, category="download_http")
        output_path.write_bytes(b"video")

    def fake_resolve(self, url, page=None):
        resolve_calls.append((url, page))
        return refreshed

    def fake_merge(video_path, audio_path, output_path, **kwargs):
        output_path.write_bytes(video_path.read_bytes())
        return True

    monkeypatch.setattr(bilibili_download, "_download_track", fake_download)
    monkeypatch.setattr(bilibili_download.BilibiliProvider, "resolve", fake_resolve)
    monkeypatch.setattr(bilibili_download, "merge_bilibili_tracks", fake_merge)

    result = bilibili_download.download_bilibili_manifest(
        initial,
        tmp_path / "output.mp4",
        BilibiliRequestSession(BilibiliRequestConfig(request_interval=0)),
        bilibili_download.BilibiliDownloadOptions(
            threads=1,
            save_subtitles=False,
            save_cover=False,
            save_danmaku=False,
            save_chapters=False,
            save_info=False,
            keep_intermediates=True,
        ),
    )

    assert download_urls == [initial.video_tracks[0].url, refreshed.video_tracks[0].url]
    assert resolve_calls == [(initial.source_url, 1)]
    assert result.output_path.read_bytes() == b"video"
