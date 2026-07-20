# m3u8-downloader

自研 m3u8 下载、合并与去广告流播工具，覆盖 Linux、Windows 和 Android。项目核心目标是把 m3u8 播放列表解析、广告片段过滤、分片并发下载、MP4 合并和本地流播代理做成一套可控、可扩展的实现，而不是依赖在线解析服务。

桌面端使用 Python 实现，提供 CLI、PyQt6 GUI 和 Textual TUI。Android 端使用 Kotlin、Jetpack Compose 和 Media3/ExoPlayer 实现，包名为 `com.dai2010.m3u8down`，最低支持 Android 10。

## 功能

- 解析媒体播放列表和主播放列表，支持自动选择最高码率变体。
- 用户停止输入 5 秒后自动探测媒体类型，也可以点击“立即探测”或在流播地址框按回车立即探测；识别为 HLS 后才开放 m3u8 全文预览，MP4、M4S、MP3、M4A、TS 等直链不会进入列表预览。
- 无扩展名的流媒体通过响应头和少量首字节识别，不依赖 URL 是否包含 `.m4s`；探测结果会复用于下载和流播，避免重复请求。
- 支持 HLS/m3u8、DASH/mpd、Smooth Streaming、RTSP 和常见直链音视频；HLS 继续使用内部分片下载，其他格式通过 FFmpeg/ExoPlayer 兜底。
- 按关键词或正则过滤广告片段。
- 多线程下载 TS 分片，支持 `.part` 临时文件和已完成分片跳过。
- 调用 FFmpeg 将分片合并为 MP4。
- 桌面 GUI 内嵌 libVLC 播放器，提供播放、停止、进度、倍速和全屏控制；本地 m3u8 流播代理可动态过滤广告片段。
- GUI 和 Android 端支持点击后预览 m3u8 列表完整全文，输入阶段不会自动拉取列表。
- 桌面端支持 CLI、GUI、TUI 三种使用方式。
- GUI、TUI 和 Android 端支持深色模式，默认跟随系统主题；GUI 和 Android 可自定义主按钮颜色。
- GUI、TUI 和 Android 端支持配置文件管理，可新建、修改和删除过滤、线程、保存目录、标签和备注。
- Android 端以“流播”“下载”和“设置”作为入口，支持在线播放、下载和统一设置管理。
- 去广告过滤是可选功能，关闭时不会显示过滤关键词输入。
- 支持 B 站普通视频页面、BV/AV/短链、多 P、画质、编码、音频语言、HDR、Cookie、字幕、封面、弹幕、章节和信息附件选项。
- 桌面 CLI、GUI、TUI 和 Android 下载/流播页提供 B 站兼容模式；Android Cookie 使用加密存储。
- Android 播放页面支持屏幕旋转时保留播放状态，系统返回手势会回到上一界面。
- Release workflow 可产出 Android APK、Linux deb、Termux aarch64 deb、Windows exe 和 Windows msi。

## 桌面端使用

完整的功能、开关、B 站地址类型和各端操作步骤请参阅：[USER_MANUAL.md](USER_MANUAL.md)。

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

也可以传入 DASH、Smooth Streaming、RTSP 或常见音视频直链；程序会在开始下载时识别类型并选择对应下载方式：

```bash
python -m m3u8_downloader "https://example.com/video/manifest.mpd" -o video.mp4
python -m m3u8_downloader "https://example.com/video/movie.mp4" -o movie.mp4
```

直接打开终端 TUI：

```bash
python -m m3u8_downloader
```

无参数运行 `m3u8-downloader` 会进入 TUI；传入 URL 和参数时会直接执行命令行下载。

常用参数：

```bash
python -m m3u8_downloader "https://example.com/master.m3u8" -o video.mp4 --variant 0
python -m m3u8_downloader "https://example.com/video.m3u8" -o video.mp4 --threads 16
python -m m3u8_downloader "https://example.com/video.m3u8" -o video.mp4 --keyword /video/adjump/ --dump-filtered filtered.m3u8
python -m m3u8_downloader "https://www.bilibili.com/video/BV..." -o video.mp4 --page 1 --quality 80 --video-codec avc --cookie 'SESSDATA=...'
python -m m3u8_downloader "https://www.bilibili.com/video/BV..." -o downloads --all-pages --save-danmaku
python -m m3u8_downloader --bilibili-login
python -m m3u8_downloader --tui
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

Termux 版本不依赖桌面 Qt，TUI 已按竖屏和小屏终端设计：下载、配置和日志分为独立页面，各页面可上下滑动；媒体地址支持点击“立即探测”或按回车探测。发布页提供 `m3u8-downloader_<版本>_termux_aarch64.deb`，在 arm64 Termux 中安装：

```bash
pkg install python ffmpeg
apt install ./m3u8-downloader_<版本>_termux_aarch64.deb
m3u8-downloader-tui
```

CLI/TUI 的 HLS 流播代理会输出本地播放地址，可复制到 mpv 或 VLC；桌面 GUI 会直接使用内嵌的 libVLC 播放器。非 HLS 媒体会直接输出原播放地址：

```text
http://127.0.0.1:8888/stream.m3u8?src=...
```

桌面端流播使用 libVLC，Linux deb 会自动依赖 VLC；Windows 安装包内置 VLC 运行库。桌面端下载和合并仍需要系统已安装 FFmpeg：

```bash
sudo apt install ffmpeg
```

## Android 端

Android APK 面向不依赖 GMS 的侧载安装场景，当前优先发布 `arm64-v8a` APK。

- Package: `com.dai2010.m3u8down`
- Min Android: Android 10, SDK 29
- Target SDK: 35
- 架构：`arm64-v8a`

应用打开后分为“流播”“下载”和“设置”三个入口。下载和流播页的“高级”区域包含去广告过滤和“开启B站兼容模式”；B 站链接会自动使用兼容模式，特殊地址也可以手动开启。设置页统一管理配置、外观和关于信息；配置管理会列出所有已有配置，点击配置即可编辑，右下角可新建配置。

## Windows 端

Windows 版本由 GitHub Actions Release workflow 在 `windows-latest` 上构建，产物包括：

- `m3u8-downloader-5.0.0-windows-x64.exe`
- `m3u8-downloader-5.0.0-windows-x64.msi`

Windows `.exe` 安装器和 `.msi` 都会安装 GUI、CLI 和 TUI 三个入口，并把安装目录加入 PATH，PowerShell 中可直接运行：

```powershell
m3u8-downloader
m3u8-downloader --tui
m3u8-downloader-gui
m3u8-downloader-tui
```

Windows 程序使用 PyInstaller 打包。下载合并仍依赖 FFmpeg，使用下载功能时需要系统 PATH 中可找到 `ffmpeg`。

## 配置

桌面端配置文件路径：

```text
~/.config/m3u8-downloader/config.json
```

默认配置包含下载线程数、保存目录、请求头、过滤关键词、输出格式、代理端口、主题设置和配置文件列表。

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
packaging/linux/build_deb.sh 5.0.0
```

所有平台构建均由 GitHub Actions 完成：`Build` workflow 会在 `main` 推送、针对 `main` 的 Pull Request 或手动触发时编译 Android arm64、Linux amd64、Termux aarch64 和 Windows x64；发布 Windows、Android、Linux 和 Termux aarch64 资产时，可以在 GitHub Actions 中手动运行 `Release` workflow，并填写 tag，例如 `v5.0.0`。

Android 发布前必须配置以下 GitHub Actions secrets：`M3U8_ANDROID_KEYSTORE_BASE64`、`M3U8_ANDROID_STORE_PASSWORD`、`M3U8_ANDROID_KEY_ALIAS` 和 `M3U8_ANDROID_KEY_PASSWORD`。工作流会使用持久保存的 PKCS#12 发布密钥签名并校验证书指纹；缺少私钥或指纹不一致时直接失败，不上传不可升级的 APK。更换发布密钥后，旧证书签名的 APK 不能直接覆盖安装。

## 发布产物

APK/AAB、deb/dpkg 包和构建目录不提交到 Git。发布版本时只把最终产物作为 GitHub Release assets 上传。

当前发布资产包括：

- `m3u8-downloader-android-arm64-v8a-debug.apk`
- `m3u8-downloader_5.0.0_amd64.deb`
- `m3u8-downloader_5.0.0_termux_aarch64.deb`
- `m3u8-downloader-5.0.0-windows-x64.exe`
- `m3u8-downloader-5.0.0-windows-x64.msi`

Linux deb 安装后可使用 `man m3u8-downloader` 查看完整 CLI 参数，包括 B 站下载选项。
