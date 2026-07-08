# m3u8-downloader

自研 m3u8 下载、合并与去广告流播工具，覆盖 Linux、Windows 和 Android。项目核心目标是把 m3u8 播放列表解析、广告片段过滤、分片并发下载、MP4 合并和本地流播代理做成一套可控、可扩展的实现，而不是依赖在线解析服务。

桌面端使用 Python 实现，提供 CLI、PyQt6 GUI 和 Textual TUI。Android 端使用 Kotlin、Jetpack Compose 和 Media3/ExoPlayer 实现，包名为 `com.dai2010.m3u8down`，最低支持 Android 10。

## 功能

- 解析媒体播放列表和主播放列表，支持自动选择最高码率变体。
- 按关键词或正则过滤广告片段。
- 多线程下载 TS 分片，支持 `.part` 临时文件和已完成分片跳过。
- 调用 FFmpeg 将分片合并为 MP4。
- 提供本地 m3u8 流播代理，可动态过滤广告片段后转发给 mpv、VLC 等播放器。
- 桌面端支持 CLI、GUI、TUI 三种使用方式。
- Android 端以“流播”和“下载”作为入口，支持在线播放、下载、选择保存目录和设置下载并发线程数。
- 去广告过滤是可选功能，关闭时不会显示过滤关键词输入。
- Android 播放页面支持屏幕旋转时保留播放状态。
- Release workflow 可产出 Android APK、Linux deb、Windows exe 和 Windows msi。

## 桌面端使用

安装运行环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

命令行下载：

```bash
python -m m3u8_downloader "https://example.com/video/index.m3u8" -o video.mp4
```

常用参数：

```bash
python -m m3u8_downloader "https://example.com/master.m3u8" -o video.mp4 --variant 0
python -m m3u8_downloader "https://example.com/video.m3u8" -o video.mp4 --threads 16
python -m m3u8_downloader "https://example.com/video.m3u8" -o video.mp4 --keyword adjump --dump-filtered filtered.m3u8
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

流播代理会输出本地播放地址，可复制到 mpv 或 VLC：

```text
http://127.0.0.1:8888/stream.m3u8?src=...
```

桌面端需要系统已安装 FFmpeg：

```bash
sudo apt install ffmpeg
```

## Android 端

Android APK 面向不依赖 GMS 的侧载安装场景，当前优先发布 `arm64-v8a` APK。

- Package: `com.dai2010.m3u8down`
- Min Android: Android 10, SDK 29
- Target SDK: 35
- 架构：`arm64-v8a`

应用打开后分为“流播”和“下载”两个入口。两个入口都可以按需开启去广告过滤；未开启时不显示过滤关键词。下载页可设置输出文件名、保存目录和并发线程数。未选择目录时，文件保存到应用外部文件目录。

## Windows 端

Windows 版本由 GitHub Actions Release workflow 在 `windows-latest` 上构建，产物包括：

- `m3u8-downloader-0.2.0-windows-x64.exe`
- `m3u8-downloader-0.2.0-windows-x64.msi`

Windows GUI 使用 PyInstaller 打包。下载合并仍依赖 FFmpeg，使用下载功能时需要系统 PATH 中可找到 `ffmpeg`。

## 配置

桌面端配置文件路径：

```text
~/.config/m3u8-downloader/config.json
```

默认配置包含下载线程数、保存目录、请求头、过滤关键词、输出格式、代理端口和主题设置。

## 测试

```bash
python3 -m pytest tests
```

## 构建

Android debug APK 构建示例：

```bash
cd android
ANDROID_HOME="$HOME/Android/Sdk" ANDROID_SDK_ROOT="$HOME/Android/Sdk" ~/gradle-8.10.2/bin/gradle :app:assembleDebug -PtargetAbi=arm64-v8a --no-daemon --max-workers=1
```

Linux deb 构建示例：

```bash
packaging/linux/build_deb.sh 0.2.0
```

发布 Windows、Android 和 Linux 资产时，可以在 GitHub Actions 中手动运行 `Release` workflow，并填写 tag，例如 `v0.2.0`。

## 发布产物

APK/AAB、deb/dpkg 包和构建目录不提交到 Git。发布版本时只把最终产物作为 GitHub Release assets 上传。

当前发布资产包括：

- `m3u8-downloader-android-arm64-v8a-debug.apk`
- `m3u8-downloader_0.2.0_amd64.deb`
- `m3u8-downloader-0.2.0-windows-x64.exe`
- `m3u8-downloader-0.2.0-windows-x64.msi`
