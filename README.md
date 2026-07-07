# m3u8-downloader

自研 m3u8 下载与去广告流播工具。项目正在按新规格重写：桌面端核心使用 Python，后续桌面 GUI/TUI 与 Android 端在同一规则模型上继续扩展。

## 当前进度

- Python 核心包：`m3u8_downloader/`
- M3U8 解析：媒体列表、主列表、分片、清晰度变体、基础 KEY 信息
- 广告过滤：关键词与正则匹配
- 下载器：多线程下载、`.part` 临时文件、已完成分片跳过
- 合并器：调用 FFmpeg concat list 合并为 MP4
- 配置：XDG 路径 `~/.config/m3u8-downloader/config.json`
- CLI：支持主播放列表自动选择最高码率、指定变体、导出过滤后的 m3u8、下载进度
- GUI：PyQt6 下载界面、设置对话框、多桌面样式适配、后台下载线程
- TUI：Textual 终端界面，支持下载和启动流播代理
- 流播代理：aiohttp 本地代理，动态过滤 m3u8 广告片段并转发 TS

旧 Go/Flutter 代码已删除，当前仓库是 Python 重写版。

## 使用

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m m3u8_downloader "https://example.com/video/index.m3u8" -o video.mp4
```

桌面 GUI：

```bash
pip install -r requirements-desktop.txt
python -m m3u8_downloader.gui.app
```

终端 TUI：

```bash
python -m m3u8_downloader.tui.app
```

流播代理会输出本地播放地址，可复制到 mpv/vlc：

```text
http://127.0.0.1:8888/stream.m3u8?src=...
```

常用参数：

```bash
python -m m3u8_downloader "https://example.com/master.m3u8" -o video.mp4 --variant 0
python -m m3u8_downloader "https://example.com/video.m3u8" -o video.mp4 --keyword adjump --dump-filtered filtered.m3u8
```

需要系统已安装 FFmpeg：

```bash
sudo apt install ffmpeg
```

## 测试

```bash
python3 -m pytest tests
```
