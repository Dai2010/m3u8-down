# m3u8-downloader 使用手册

版本：`5.0.0`

本工具用于下载和流播 HLS/m3u8、DASH/mpd、Smooth Streaming、RTSP 以及常见直链媒体，也支持 B 站普通视频页面和短链。

请只处理自己拥有权利或获得合法授权的内容，并遵守平台规则。

## 一、B 站地址与兼容模式

CLI、GUI、TUI 和 Android 支持普通 B 站视频页面、BV/AV 地址、短链及多 P 视频。
请使用自己有权访问的内容，并避免在公开场合粘贴包含个人凭据的完整地址。

标准地址会自动启用兼容模式；非标准地址可以手动打开兼容模式。

桌面 GUI 和 Android 的“下载”“流播”页面都有“高级”区域，开关名称固定为：

```text
开启B站兼容模式
```

标准 B 站域名会自动生效，通常不需要手动打开。以下情况可以手动打开：

- 地址来源特殊，自动识别没有生效。
- 自动探测失败，需要手动尝试兼容模式。

Android 页面中的开关显示实际生效状态：当前输入或下载列表包含标准 B 站地址时，即使没有手动点击，开关也会显示为开启；普通地址则只显示手动设置的状态。

兼容模式不会改变普通第三方地址的处理方式。

## 二、桌面 CLI

### 安装与启动

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m m3u8_downloader --help
```

直接下载：

```bash
python -m m3u8_downloader "https://cdn.example.net/video/index.m3u8" -o video.mp4
```

B 站地址建议放在引号中，避免其中的特殊字符被 Shell 当成命令分隔符：

```bash
export BILIBILI_MEDIA_URL='粘贴完整的 B 站媒体地址'
python -m m3u8_downloader "$BILIBILI_MEDIA_URL" -o bilibili-video.mp4
```

环境变量示例中的值只应在本机临时使用，不要把真实 Cookie 或个人地址提交到仓库。

### CLI 参数

| 参数 | 用法 |
| --- | --- |
| `url` | 媒体 URL、B 站普通视频页面或短链；省略时进入 TUI。 |
| `-o`、`--output` | 输出文件路径；省略时根据 URL 扩展名生成文件名，播放列表默认输出 `video.mp4`。 |
| `--work-dir` | 指定临时工作目录。指定后目录不会由程序自动删除，便于排查失败任务。 |
| `--header` | 增加请求头，可重复使用，例如 `--header 'Cookie: SESSDATA=...'`。命令行值覆盖同名配置。 |
| `--cookie` | B 站 Cookie；优先于配置文件中的 `bilibili_cookie`。 |
| `--page` | 指定 B 站分 P 编号，从 `1` 开始；未指定时交互选择，非交互运行默认选择 P1。 |
| `--all-pages` | 下载普通 B 站视频的全部分 P；输出目录中按分 P 生成文件。 |
| `--quality` | B 站最高画质 ID，例如 `80`；不传时自动选择。 |
| `--video-codec` | 视频编码优先级，可重复指定 `avc`、`hevc` 或 `av1`；不传时为 AVC、HEVC、AV1。 |
| `--audio-language` | B 站音频语言代码；不传时自动选择。 |
| `--hdr` | 有可用资源时优先选择 HDR。 |
| `--no-subtitles` | 不保存或封装字幕。 |
| `--no-cover` | 不保存封面。 |
| `--save-danmaku` | 保存弹幕 XML。 |
| `--no-chapters` | 不写入章节。 |
| `--no-info` | 不保存信息 JSON。 |
| `--keep-bilibili-tracks` | 保留 B 站下载过程中的临时文件，便于排查失败任务。 |
| `--keyword` | HLS 去广告关键词，可重复使用；匹配播放列表条目或标题。没有传入时使用配置文件关键词。 |
| `--regex` | 把 `--keyword` 当作正则表达式；只影响 HLS 去广告。 |
| `--threads` | HLS 分片并发线程数；不传时使用配置值。 |
| `--variant` | 主播放列表变体的零基索引；不传时自动选择最高带宽变体。 |
| `--dump-filtered` | 将去广告后的 HLS 文本写入指定文件；只适用于 HLS。 |
| `--keep-segments` | 保留默认工作目录中的已下载分片；默认合并后删除。 |
| `--tui` | 打开终端界面。 |

常用例子：

```bash
python -m m3u8_downloader "https://cdn.example.net/video/master.m3u8" -o video.mp4 --variant 0
python -m m3u8_downloader "https://cdn.example.net/video/index.m3u8" -o video.mp4 --threads 16
python -m m3u8_downloader "https://cdn.example.net/video/index.m3u8" -o video.mp4 \
  --keyword /video/adjump/ --dump-filtered filtered.m3u8
python -m m3u8_downloader "https://cdn.example.net/video/index.m3u8" -o video.mp4 \
  --header 'Referer: https://example.com' --header 'Cookie: session=local-only'
```

桌面 CLI 对 B 站地址自动兼容。需要对非标准地址强制开启时，在配置文件中设置：

```json
{
  "bilibili_compat": true
}
```

配置文件位置见“配置文件”一节。

## 四、桌面 GUI

启动：

```bash
pip install -r requirements-desktop.txt
python -m m3u8_downloader.gui.app
```

首页有“流播”“下载”“设置”三个入口。

### 流播页

1. 在“媒体地址”输入最终媒体地址。
2. 停止输入约 5 秒等待自动探测，或点击“立即探测”、在地址框按回车立即探测。
3. 展开“高级”配置请求头和过滤选项。
4. HLS 可点击“预览 m3u8 列表”查看完整文本。
5. 点击“开始流播”启动内嵌播放器；程序会根据地址类型准备相应的播放方式，B 站页面可直接输入。
6. 播放器控制栏提供播放、停止、进度拖动和倍速；闲置 5 秒后自动隐藏，移动鼠标会重新显示。
7. 点击“全屏”或双击视频进入全屏，按 `Esc` 或再次点击按钮退出。
8. 点击“停止流播”停止播放并关闭本地代理。

流播页高级选项：

- `Referer，可留空`：站点要求来源页时填写。
- `开启B站兼容模式`：手动启用 B 站兼容模式。
- `启用去广告过滤`：对支持的 HLS 播放列表启用广告过滤。
- `过滤关键词，每行一个`：打开去广告后显示；匹配播放列表条目或标题。

### 下载页

- “保存目录”：选择任务输出目录。
- “并发线程数”：下载并发数量，桌面 GUI 范围为 `1` 到 `128`。
- “添加 URL”：增加批量下载任务。
- 每个任务可以填写最终媒体地址和输出文件名；文件名留空时自动命名。
- 每个 HLS 任务都有“预览 m3u8”按钮；直链不会进入列表预览。
- “删除”：移除当前任务。
- “高级”：包含 Referer、`开启B站兼容模式`、去广告过滤和关键词。
- “开始下载”：等待所有任务完成 5 秒探测后开始。
- “停止下载”：停止后续操作；当前网络请求结束后退出。
- 开始前可以选择使用已有配置或使用当前页面内容进行引导式下载。

桌面下载支持临时文件和有限重试；任务完成后会生成 MP4 等输出文件。

### 设置页

设置窗口包含以下页签：

**常规**

- `线程数`：默认下载线程数。
- `保存目录`：默认输出目录。
- `Referer`：全局来源页请求头。
- `User-Agent`：全局用户代理。
- `过滤关键词`：每行一个，作为默认 HLS 去广告关键词。

**外观**

- `主题`：`system`、`light`、`dark`，分别表示跟随系统、浅色、深色；打开下拉菜单悬停选项可即时预览，取消设置会恢复原主题。
- `按钮颜色`：填写六位十六进制颜色，例如 `#146C5A`；可使用调色板或恢复默认。

**配置管理**

每个配置可以保存：名称、标签、备注、去广告开关、过滤关键词、线程数和保存目录。至少保留一个配置；下载时可以选择已有配置。

**关于**

显示版本、项目主页和协议链接。

## 五、终端 TUI

启动：

```bash
python -m m3u8_downloader
python -m m3u8_downloader.tui.app
```

TUI 提供：

- 媒体 URL、输出路径、Referer 输入。
- 1 秒延迟媒体探测，也可以点击“立即探测”或在媒体地址输入框按回车立即探测。
- `Download` 下载按钮。
- `Start Proxy`、`Stop Proxy` 本地流播代理按钮。
- 配置编号、名称、标签、备注、去广告开关、关键词、线程数和保存目录。
- `Load Profile`、`New Profile`、`Save Profile`、`Delete Profile` 配置管理按钮。
- 下载、配置和日志分为独立页面，每个页面都支持上下滑动，适合 Termux 的竖屏和小屏终端。
- `q` 退出，并在退出时停止代理。

TUI 会自动识别标准 B 站地址，但没有单独的 `开启B站兼容模式` 可视开关；需要手动
设置时请改用 GUI、Android 或 CLI 配置。

### Termux

Termux 版本不需要桌面 Qt，发布页提供 arm64/aarch64 安装包。先安装运行依赖，再安装 deb 包：

```bash
pkg install python ffmpeg
apt install ./m3u8-downloader_<版本>_termux_aarch64.deb
m3u8-downloader-tui
```

也可以使用 `m3u8-downloader` 进入 TUI，或使用 `m3u8-downloader <媒体地址>` 执行命令行下载。

## 六、Android

Android 应用最低支持 Android 10，入口为“流播”“下载”“设置”。

### 流播

1. 输入最终媒体地址并等待约 5 秒自动探测。
2. 展开“高级”，可填写 Referer、打开 `开启B站兼容模式`、启用去广告并填写关键词。
3. HLS 可以先点击“预览 m3u8 列表”。
4. 点击“开始播放”进入 Media3 播放页面。
5. 播放页支持返回和旋转屏幕保持播放状态。

### 下载

1. 选择“使用已有配置”或“引导式下载”。
2. 每条任务输入最终媒体地址，并可单独填写输出文件名。
3. 点击“添加 URL”批量增加任务，垃圾任务可点击删除图标移除。
4. 设置并发线程数；Android 会限制在 `1` 到 `64`，默认值为 `8`。
5. 选择保存目录。建议使用系统目录选择器指定一个用户可访问的目录。
6. 展开“高级”使用 Referer、`开启B站兼容模式`、去广告和关键词。
7. 点击“开始下载”，应用会按任务顺序下载并显示进度。

Android HLS 下载会过滤分片、并发下载并使用内置 FFmpeg 合并；DASH、Smooth、RTSP 和直链由对应媒体处理路径完成。Android 页面没有独立的停止下载按钮，下载过程中请等待当前任务完成。

### 设置与配置

- `外观`：跟随系统、浅色、深色。
- `按钮颜色 #RRGGBB`：填写六位十六进制颜色，或选择预设颜色；可以恢复默认。
- `管理配置`：新建、编辑和删除配置；每个配置包含名称、标签、备注、去广告、关键词、线程数和保存目录。
- `关于`：查看版本和项目链接。

## 七、媒体类型与外部依赖

| 类型 | 识别方式 | 桌面处理方式 | m3u8 预览 |
| --- | --- | --- | --- |
| HLS/m3u8 | URL、响应头或 `#EXTM3U` | 内部分片下载、过滤、合并 | 支持 |
| DASH/mpd | URL、响应头或 MPD/XML | FFmpeg | 不支持 |
| Smooth Streaming | URL、响应头或 XML | FFmpeg/播放器路径 | 不支持 |
| RTSP | `rtsp://` | FFmpeg/播放器路径 | 不支持 |
| 直链媒体 | 扩展名、响应头或文件头 | 断点直链下载 | 不支持 |

桌面端流播依赖 libVLC。Linux deb 会安装 `vlc` 和 `python3-vlc`，Windows 安装包内置 VLC 运行库。桌面端下载 DASH、Smooth、RTSP 或需要合并的媒体时，仍需要系统 PATH 中存在 `ffmpeg`：

```bash
ffmpeg -version
```

Android 使用 APK 内置的 FFmpeg/Media3 依赖，不需要在手机上单独安装命令行 FFmpeg。

## 八、配置文件

桌面配置文件默认位置：

```text
~/.config/m3u8-downloader/config.json
```

设置了 `XDG_CONFIG_HOME` 时，路径为：

```text
$XDG_CONFIG_HOME/m3u8-downloader/config.json
```

常用字段：

```json
{
  "threads": 16,
  "save_dir": "~/Downloads",
  "headers": {
    "Referer": "",
    "User-Agent": "Mozilla/5.0"
  },
  "bilibili_cookie": "",
  "filter_keywords": ["/video/adjump/"],
  "bilibili_compat": false,
  "proxy_port": 8888,
  "theme": "system",
  "button_color": ""
}
```

桌面 GUI 的“常规”设置和 CLI 的 `--cookie` 都会写入或注入 `bilibili_cookie`；二维码登录成功后 GUI、CLI 和 TUI 都会自动保存登录状态。Cookie 仅用于 B 站请求，不会自动发送到其他站点。配置文件位于 `~/.config/m3u8-downloader/config.json`，程序会将其权限限制为当前用户可读写。不要在日志或仓库中保存真实 `Cookie`、访问令牌或媒体文件。

## 九、B 站 CLI 下载

CLI 支持普通 BV/av 视频页面、短链和多 P 视频。番剧、课程、合集和系列地址会给出明确的
不支持提示。需要登录权限的内容可以使用 `--cookie`，也可以在配置文件中保存
`bilibili_cookie`。

如果不方便手工复制 Cookie，可以运行 `python -m m3u8_downloader --bilibili-login`，
程序会生成二维码并轮询登录状态，成功后自动保存登录信息。GUI 设置页和 TUI 配置页
也提供相同的登录入口；Android 在应用内完成登录并自动保存状态。普通公开视频通常无需
填写 Cookie，受限内容需要先完成登录。

本项目桌面端使用配置文件保存登录状态并限制文件权限，Android 使用 Android Keystore
加密保存 Cookie；卸载 Android 应用或清除其安全存储后，登录状态可能丢失。Cookie
失效时重新使用二维码登录即可，不需要手工提取 Cookie。

### 参数速查

| 参数 | 说明 |
| --- | --- |
| `--cookie COOKIE` | 指定 B 站 Cookie，优先于配置文件。 |
| `--bilibili-login` | 通过二维码登录并保存登录状态。 |
| `--page PAGE` | 下载指定分 P，编号从 `1` 开始。 |
| `--all-pages` | 下载全部分 P；`--output` 应指定目录。 |
| `--quality QUALITY` | 设置最高画质 ID，例如 `80`。 |
| `--video-codec CODEC` | 设置编码优先级，可重复使用 `avc`、`hevc`、`av1`。 |
| `--audio-language LANGUAGE` | 设置音频语言代码。 |
| `--hdr` | 优先选择 HDR。 |
| `--no-subtitles` | 不保存或封装字幕。 |
| `--no-cover` | 不保存封面。 |
| `--save-danmaku` | 保存弹幕 XML。 |
| `--no-chapters` | 不写入章节。 |
| `--no-info` | 不保存信息 JSON。 |
| `--keep-bilibili-tracks` | 保留下载过程中的临时文件，便于排查失败任务。 |

### 示例

```bash
python -m m3u8_downloader "https://www.bilibili.com/video/BV..." \
  --cookie 'SESSDATA=...' --page 2 --quality 80 --video-codec avc \
  --output lesson.mp4

python -m m3u8_downloader "https://www.bilibili.com/video/BV..." \
  --all-pages --save-danmaku --output ./downloads

python -m m3u8_downloader "https://www.bilibili.com/video/BV..." \
  --video-codec hevc --video-codec avc --no-subtitles --no-cover \
  --no-chapters --no-info
```

未指定 `--page` 或 `--all-pages` 时，交互终端会显示分 P 选择；非交互终端默认选择
P1。GUI 和 TUI 提供对应的分 P、画质、附件和 Cookie 设置。

## 十、使用注意

请勿短时间内反复探测、刷新或重复提交同一个 B 站地址，也不要为了提速同时运行多个实例。
如果页面提示请求过于频繁，请停止操作并等待一段时间后再试。任何客户端都不能保证完全
避免平台限流或封禁，请遵守 B 站服务规则并只处理有权使用的内容。

## 十一、常见问题

### 提示媒体类型未知

确认链接仍然有效；等待约 1 秒探测，或点击“立即探测”；必要时填写 Referer；B 站非标准地址可以打开 `开启B站兼容模式`。

### B 站返回 403

确认链接仍然有效，并检查 Cookie 是否有权访问该内容；必要时重新输入页面地址或更新 Cookie，再尝试 `开启B站兼容模式`。

### m3u8 预览按钮不可用

只有探测结果为 HLS/m3u8 时才提供预览。`.m4s`、`.mp4`、DASH 和 RTSP 是媒体或其他协议，不提供 m3u8 列表预览。

### 去广告没有生效

去广告只适用于 HLS 播放列表。打开开关后，每行输入一个能匹配播放列表条目或标题的关键词；CLI 需要额外使用 `--regex` 才会按正则匹配。

### 合并失败

桌面端先执行 `ffmpeg -version`，确认 FFmpeg 已安装并在 PATH 中；检查工作目录中的分片是否完整；必要时用 `--work-dir` 保留现场并减少线程数重试。
