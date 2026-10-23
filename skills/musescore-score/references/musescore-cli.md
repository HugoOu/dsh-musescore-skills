# MuseScore 4 命令行速查（实测 4.7.5 / Windows）

本机实测环境：`C:\Program Files\MuseScore 4\bin\MuseScore4.exe`，`MuseScore4 4.7.5`。
`scripts/mscore.py` 已经把这些封装好了；这一页是「为什么要封装」和「什么时候需要直接调 exe」。

## 找可执行文件

查找顺序（`mscore.py` 实现相同）：

1. 环境变量 `MSCORE_PATH` / `MUSESCORE_PATH`
2. Windows：`%ProgramFiles%\MuseScore 4\bin\MuseScore4.exe`、`%ProgramFiles(x86)%\...`、`%LOCALAPPDATA%\Programs\MuseScore 4\...`
3. macOS：`/Applications/MuseScore 4.app/Contents/MacOS/mscore`
4. Linux：`/usr/bin/musescore4`、`/usr/bin/mscore`
5. `PATH` 里的 `mscore` / `musescore` / `MuseScore4`

## 核心用法：`-o` 决定一切

```bat
MuseScore4.exe -o 输出文件 输入文件
```

输出格式**只看扩展名**：`.mscz` `.musicxml` `.mxl` `.pdf` `.png` `.svg` `.mp3` `.flac` `.wav` `.mid`。
输入同样靠扩展名识别：`.mscz` `.mscx` `.musicxml` `.mxl` `.mid` `.gp` 等。

## 常用开关（`--help` 原文语义）

| 开关 | 作用 | 备注 |
|---|---|---|
| `-o, --export-to <file>` | 导出 | 可重复给多个 `-o` 一次导出多格式 |
| `-f, --force` | 忽略「文件损坏/版本不符」警告强行导出 | 处理别人给的谱时常用 |
| `-r, --image-resolution <DPI>` | PNG/SVG 分辨率 | 默认 300；论文插图 150–200 够 |
| `-T, --trim-image <margin>` | PNG/SVG 裁边（像素） | 只要一行的片段图时很好用 |
| `-b, --bitrate <kbps>` | MP3 码率 | |
| `--page <spec>` | 只导出指定页 | 实测 `--page 1`、`--page 1-3` 可用 |
| `-S, --style <file>` | 加载 `.mss` 样式 | 统一排版风格 |
| `-j, --job <file>` | 批量作业 JSON | 见下 |
| `--score-meta` | 打印元数据 JSON 到 stdout | 标题/作曲/调号/拍号/小节数/页数/声部 |
| `--score-elements` | 打印全谱元素 JSON | 很大，务必重定向 |
| `--score-media` | 打印整份谱的媒体 JSON | 同上，含 base64 |
| `--score-parts` | 生成分谱 | **会把巨大 JSON 打到 stdout**；一般别直接跑 |
| `-P, --export-score-parts` | 导出「谱+分谱」到一个 PDF | 实测对未生成分谱的文件退出码 1，谨慎 |
| `--transpose <opts>` / `--score-transpose` | 转调 | 版本间行为不稳，宁可在 MusicXML 层改音高 |
| `--no-audio` / `--resolution` / `--fps` | 视频导出用 | 与本 skill 无关 |
| `-p`（MuseScore 3 的插件启动） | **MS4 已移除** | 无法从命令行触发插件 |

## 批量作业 JSON（实测可用）

```json
[
  {
    "in":  "C:/work/satb.musicxml",
    "out": ["C:/work/out/satb.pdf", "C:/work/out/satb.mid"]
  }
]
```

```bat
MuseScore4.exe -j job.json
```

一次进程启动跑完多条，省掉每次 4–6 秒的冷启动。`out` 里也可以写 `["x.png", {"dpi": 200}]` 形式带参数。

## 踩坑清单（都是实测踩过的）

1. **stderr 里那行 `failed open log file: ...LocalLow\MuseScore...` 是无害的**——沙箱/权限导致写不了日志，导出照常成功。`mscore.py` 会过滤；直接调 exe 时不要因为它就判定失败。
2. **`-o out.png` 实际生成 `out-1.png`**（多页则 `out-2.png`…）。要按页取图就得 glob，不要死等 `out.png`。
3. **退出码 0 ≠ 产物正常**：`-o` 成功但文件 0 字节的情况存在，必须校验 magic bytes（`mscore.py verify` 做的就是这件事）。
4. **PowerShell 里别拼字符串命令**：路径带空格（`Program Files`）时用参数数组/`& $exe -o $a $b`。
5. **首次运行慢**（约 4–6 秒，含字体/音色初始化）；写循环批量导出时用 `-j`，或接受每次 5 秒。
6. **命令行不能启动插件**（MS4 没有 `-p`）：所有「插件/实时编辑」类方案都不走 CLI。
7. **`--score-parts` 会往 stdout 打整包 JSON**：在代理环境里可能刷屏数万字符，只在你确实要分谱数据时用，并且 `> file` 重定向。
8. `--force` 不会修复文件，只是跳过警告；导出后仍要用 `--score-meta` 复核页数/小节数。

## 与 MuseScore 3 的差异（选方案时会踩）

- MS4 删掉 Qt5/QtWebSockets QML 模块与 dock 插件，插件 API 迁移到 Qt6。
- MS4 自 **4.4.2** 起提供官方 WebSocket API（`api.websocket` / `api.websocketserver`），
  这是所有「MCP 实时编辑」方案的底座；4.4.2 之前没有。
- MS4 的命令行**不能**启动插件，插件的启用/运行只能在 GUI 里点。
