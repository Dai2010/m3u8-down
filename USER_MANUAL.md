# m3u8-downloader 使用手册

版本：`4.2.3`

本工具用于下载、合并和流播 HLS/m3u8、DASH/mpd、Smooth Streaming、RTSP 以及常见直链媒体。B 站兼容模式只负责请求已经拿到的媒体地址，不负责解析 BV 页面、调用 B 站接口或选择音视频流。

请只处理自己拥有权利或获得合法授权的内容，并遵守平台规则。

## 一、最重要：B 站应该使用什么链接

### 1. “最终媒体地址”是什么

“最终媒体地址”是播放器真正拿来读取媒体数据的 URL。它直接返回以下内容之一：

- HLS 播放列表文本，响应内容通常以 `#EXTM3U` 开头，地址一般包含 `.m3u8`。
- DASH 播放列表文本，地址一般包含 `.mpd`，响应内容是 MPD/XML。
- 视频或音频媒体字节，地址一般包含 `.m4s`、`.mp4`、`.ts`、`.mp3` 等。

它不是视频网页地址，也不是返回 HTML 或 JSON 的接口地址。判断方法是：把地址交给播放器或本工具后，服务器直接返回播放列表或媒体数据，而不是先返回一个网页。

### 2. 可用地址示例

以下地址是格式示例，域名、文件名和查询参数均为演示内容，不保证可以访问。

**普通 HLS 播放列表，优先推荐：**

```text
https://cdn.example.net/live/channel/master.m3u8?token=demo-token&expires=1893456000
```

**B 站签名视频分片地址：**

```text
https://xy123.bilivideo.com/upgcxcode/00/00/00/video-30280.m4s?deadline=1893456000&platform=pc&trid=demo-trid&upsig=demo-signature
```

**B 站带端口的 mcdn 地址：**

```text
https://xy123.mcdn.bilivideo.cn:443/upgcxcode/00/00/00/video-30280.m4s?deadline=1893456000&trid=demo-trid&upsig=demo-signature
```

**普通直接媒体地址：**

```text
https://media.example.net/video/movie.mp4?token=demo-token
```

B 站真实地址通常会包含很长的签名查询参数。复制时必须保留完整的 `?`、`&`、`deadline`、`trid`、`upsig` 等参数；不要只复制到 `.m4s` 或 `.m3u8` 为止。

### 3. 不可直接使用的地址示例

下面这些是页面或 API 地址，不是本工具需要的最终媒体地址：

```text
https://www.bilibili.com/video/BV1xx411c7mD
https://www.bilibili.com/video/av123456789
https://www.bilibili.com/bangumi/play/ep123456
https://www.bilibili.com/bangumi/play/ss12345
https://api.bilibili.com/x/player/wbi/playurl?... 
```

部分专用 B 站下载工具可以接收 BV、av、ep、ss 页面标识，并通过 B 站接口继续解析；`m3u8-downloader` 不具备这层页面解析能力。因此，把 BV 页面直接粘贴进本工具时，通常会出现媒体类型未知、返回 HTML 或请求失败。

### 4. 如何取得最终媒体地址

以浏览器为例：

1. 打开有权访问的视频页面并开始播放。
2. 打开开发者工具的 `Network`/“网络”面板。
3. 使用筛选词 `m3u8`、`m4s` 或 `media`。
4. 找到响应内容为 `#EXTM3U`、MPD/XML 或媒体字节的请求。
5. 选择“复制链接地址”或“Copy URL”。
6. 粘贴到本工具，并保留完整查询参数。

如果同时看到视频 `.m4s` 和音频 `.m4s`，它们是两个独立的流。本工具可以下载你提供的单个媒体地址，但不会根据 BV 页面自动获取、选择并混合 B 站独立的视频流和音频流。需要完整成片时，优先寻找可直接播放的 HLS/m3u8 或已经包含音视频的媒体地址。

签名地址通常会过期。遇到 `403` 时，重新播放页面并复制新地址；不要把真实签名 URL 写进 README、Issue、日志或截图。

## 二、B 站兼容模式怎么用

### 自动模式

地址的主机名属于以下域名时，程序自动启用兼容请求：

- `bilibili.com`、`bilibili.tv`
- `bilivideo.com`、`bilivideo.cn`
- 上述域名的子域名

兼容层采用常见的 B 站 CDN 请求策略：

- 默认补充 `User-Agent: Mozilla/5.0`。
- 默认补充 `Referer: https://www.bilibili.com`。
- 保留配置中的 `Cookie` 等请求头。
- 桌面 CLI/TUI 在需要时可对 B 站 CDN 执行 HTTP 兼容替换。
- Android 始终保留 CDN 的 HTTPS；这是 Android 网络安全策略要求，不能使用明文 HTTP。
- 带端口的 `.mcdn.bilivideo.cn:<port>` 地址在所有平台保留 HTTPS。
- 下载失败日志只显示不带查询参数的 URL，避免把签名完整写入错误信息。

### 手动模式

桌面 GUI 和 Android 的“下载”“流播”页面都有“高级”区域，开关名称固定为：

```text
开启B站兼容模式
```

标准 B 站域名会自动生效，通常不需要手动打开。以下情况可以手动打开：

- 地址已经被代理改写，主机名不再是 B 站域名。
- CDN 使用了隐藏或非标准域名，但你确认它是 B 站媒体地址。
- 自动探测失败，需要强制使用 B 站请求头。

Android 页面中的开关显示实际生效状态：当前输入或下载列表包含标准 B 站地址时，即使没有手动点击，开关也会显示为开启；普通地址则只显示手动设置的状态。

手动模式不会把任意第三方地址强行变成 B 站媒体，也不会把 BV 页面解析成媒体地址。

## 三、桌面 CLI

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

B 站媒体地址建议放在引号中，避免签名 URL 中的 `&` 被 Shell 当成命令分隔符：

```bash
export BILIBILI_MEDIA_URL='粘贴完整的B站.m3u8或.m4s地址'
python -m m3u8_downloader "$BILIBILI_MEDIA_URL" -o bilibili-video.mp4
```

环境变量示例中的值只应在本机临时使用，不要把真实签名地址提交到仓库。

### CLI 参数

| 参数 | 用法 |
| --- | --- |
| `url` | 媒体 URL；省略时进入 TUI。接收最终媒体地址，不接收 BV 页面。 |
| `-o`、`--output` | 输出文件路径；省略时根据 URL 扩展名生成文件名，播放列表默认输出 `video.mp4`。 |
| `--work-dir` | 指定 HLS 分片工作目录。指定后目录不会由程序自动删除，便于排查分片问题。 |
| `--header` | 增加请求头，可重复使用，例如 `--header 'Cookie: SESSDATA=...'`。命令行值覆盖同名配置。 |
| `--keyword` | HLS 去广告关键词，可重复使用；匹配分片 URL 或标题。没有传入时使用配置文件关键词。 |
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

桌面 CLI 对 B 站地址自动兼容。需要对隐藏 CDN 地址强制开启时，在配置文件中设置：

```json
{
  "bilibili_compat": true
}
```

配置文件位置见“配置文件”一节。该字段只改变请求策略，仍然要求输入真正的媒体 URL。

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
5. 点击“开始流播”启动本地代理；HLS 会输出本地播放地址，复制到 mpv/VLC 等播放器。
6. 直链、DASH、Smooth 或 RTSP 会按媒体类型交给对应播放路径。
7. 点击“停止流播”关闭本地代理。

流播页高级选项：

- `Referer，可留空`：站点要求来源页时填写。
- `开启B站兼容模式`：强制使用 B 站请求策略。
- `启用去广告过滤`：只对 HLS 播放列表过滤分片。
- `过滤关键词，每行一个`：打开去广告后显示；匹配分片 URL 或标题。

### 下载页

- “保存目录”：选择任务输出目录。
- “并发线程数”：HLS 分片并发数量，桌面 GUI 范围为 `1` 到 `128`。
- “添加 URL”：增加批量下载任务。
- 每个任务可以填写最终媒体地址和输出文件名；文件名留空时自动命名。
- 每个 HLS 任务都有“预览 m3u8”按钮；直链不会进入列表预览。
- “删除”：移除当前任务。
- “高级”：包含 Referer、`开启B站兼容模式`、去广告过滤和关键词。
- “开始下载”：等待所有任务完成 5 秒探测后开始。
- “停止下载”：停止后续操作；当前网络请求结束后退出。
- 开始前可以选择使用已有配置或使用当前页面内容进行引导式下载。

桌面下载会保留 `.part` 临时文件并进行有限重试；已有临时内容且服务器返回 `206` 时会发送 Range 请求续传。HLS 分片会写入工作目录，合并完成后生成 MP4。

### 设置页

设置窗口包含以下页签：

**常规**

- `线程数`：默认下载线程数。
- `保存目录`：默认输出目录。
- `Referer`：全局来源页请求头。
- `User-Agent`：全局用户代理；B 站兼容模式只在未填写时补充 `Mozilla/5.0`。
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

TUI 对标准 B 站 CDN 地址会自动识别并使用兼容请求，但没有单独的 `开启B站兼容模式` 可视开关；隐藏 CDN 地址请改用 GUI、Android 或 CLI 配置。

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

桌面端下载 DASH、Smooth、RTSP 或需要合并的媒体时，需要系统 PATH 中存在 `ffmpeg`：

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
  "filter_keywords": ["/video/adjump/"],
  "bilibili_compat": false,
  "proxy_port": 8888,
  "theme": "system",
  "button_color": ""
}
```

不要在配置文件、日志或仓库中保存真实 `Cookie`、签名 URL、访问令牌或媒体文件。

## 九、B 站页面解析边界

本应用只处理已经取得的媒体地址，产品定位与从页面开始解析的专用 B 站下载工具不同：

- 专用 B 站下载工具：可以从 BV、av、ep、ss 等页面标识开始，通过 B 站 API 获取信息，并提供分P、画质、编码、音频、视频、字幕、弹幕、封面、账号登录和混流选项。
- 本应用：从最终 m3u8、mpd、m4s、mp4 等媒体地址开始，提供媒体探测、HLS 分片下载、去广告、断点续传、FFmpeg 合并、流播代理和跨平台界面。

因此，B 站页面链接的正确工作流是：

```text
B站视频页面 → 浏览器网络面板 → 复制最终 m3u8/m4s 媒体地址 → 粘贴到本应用
```

不要把下面两类地址混用：

```text
专用 B 站下载工具输入：B站页面/BV/av/ep/ss
m3u8-downloader 输入：页面解析后得到的最终媒体地址
```

## 十、常见问题

### 提示媒体类型未知

确认粘贴的是最终媒体地址；等待约 1 秒探测，或点击“立即探测”；检查地址是否过期；必要时填写 Referer；B 站非标准 CDN 可以打开 `开启B站兼容模式`。

### B 站返回 403

重新从正在播放的页面复制完整签名 URL，不要删掉查询参数。确认没有把 BV 页面、API JSON 地址或已经过期的 `.m4s` 地址粘贴进来。B 站 CDN 地址可尝试兼容模式，但兼容模式不能刷新过期签名。

### m3u8 预览按钮不可用

只有探测结果为 HLS/m3u8 时才提供预览。`.m4s`、`.mp4`、DASH 和 RTSP 是媒体或其他协议，不提供 m3u8 列表预览。

### 去广告没有生效

去广告只处理 HLS 分片 URL 和分片标题。打开开关后，每行输入一个能出现在分片 URL 或标题中的关键词；CLI 需要额外使用 `--regex` 才会按正则匹配。

### 合并失败

桌面端先执行 `ffmpeg -version`，确认 FFmpeg 已安装并在 PATH 中；检查工作目录中的分片是否完整；必要时用 `--work-dir` 保留现场并减少线程数重试。
