# m3u8-downloader 使用说明

## 支持范围

项目支持通用 HLS/m3u8、DASH/mpd、Smooth Streaming、RTSP 和常见直链音视频下载、过滤与合并，覆盖 Linux、Windows、Termux 和 Android。

B 站兼容功能已在全平台下线。此前版本中标记的 B 站兼容功能已确认不可用，后续版本不再继续开发、修复或恢复该功能。

## CLI

```bash
python -m m3u8_downloader "https://example.com/video/index.m3u8" -o video.mp4
python -m m3u8_downloader "https://example.com/video/manifest.mpd" -o video.mp4
python -m m3u8_downloader "https://example.com/video/movie.mp4" -o movie.mp4
```

常用参数：

- `--header "Name: value"`：追加请求头。
- `--threads N`：设置 HLS 分片并发数。
- `--variant N`：选择主播放列表中的变体。
- `--keyword TEXT`：过滤包含关键词的分片。
- `--regex`：将过滤关键词按正则表达式处理。
- `--dump-filtered PATH`：保存过滤后的播放列表。
- `--keep-segments`：保留下载分片。

## GUI 和 TUI

使用源码运行时，执行 `python -m pip install ".[desktop]"` 安装桌面端依赖，再运行 `python -m m3u8_downloader.gui.app` 启动 GUI；运行 `python -m m3u8_downloader.tui.app` 启动 TUI。无 URL 运行 CLI 也会进入 TUI。Windows 安装包已包含 Python 依赖和 FFmpeg。

## Android

Android 应用提供流播、下载和设置入口，最低支持 Android 10。发布 APK 使用项目升级签名密钥签名；安装升级包前不要卸载已有应用。

## 配置和测试

桌面配置位于 `~/.config/m3u8-downloader/config.json`。测试命令：

```bash
python -m pytest tests
```
