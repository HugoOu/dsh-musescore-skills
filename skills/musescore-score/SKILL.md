---
name: musescore-score
description: 用 MuseScore 4 写谱与出成品：写 MusicXML → MuseScore 命令行无头排版，产出可编辑 .mscz、PDF、PNG、MP3、MIDI。适合创作/改编乐谱、在已有谱上加内容、转调/抽分谱/导音频、需要五线谱图片或打印稿；不负责「在已打开的 MuseScore 窗口里实时编辑」，那需要 MCP 插件桥。
---
# MuseScore 写谱（直连路线）

MuseScore 4 自带完整命令行排版器。本 skill 的循环是：
**写 MusicXML → 编译 → 渲染 PNG 自己看 → 改 → 再编译**。
不需要 GUI、不需要插件、不需要联网。

## 路径

    $MS = "$env:USERPROFILE\.dsh\skills\musescore-score"     # 技能目录
    $PY = <当前可用的 Python 3.10+>                            # DSH 会话里用 load_workspace_dependencies 返回的 python

脚本：`$MS\scripts\mxml.py`（构谱库）、`$MS\scripts\mscore.py`（MuseScore 封装）、`$MS\scripts\selfcheck.py`（自检）。

## 第 0 步：先自检一次（新环境必做）

    & $PY "$MS\scripts\selfcheck.py" --out .\ms-selfcheck

12 项全 PASS 才继续；失败项会直接告诉你是「找不到 MuseScore」还是「产物异常」。
输出目录里的 `selfcheck-1.png` 打开看一眼，确认字体/符号正常。

## 第 1 步：用 mxml 写谱

```python
import sys; sys.path.insert(0, r"<技能目录>\scripts")
from mxml import Score

s = Score(title="曲名", composer="作者", key=0, time=(4, 4), tempo=96)
p = s.add_part("Piano", program=1)          # 钢琴；staves=2 时自动配高低音谱号
m = p.add_measure()
notes = m.line("C4:1 C4:1 G4:1 G4:1 A4:1 A4:1 G4:2")   # 音名:时值(四分音符倍数)
for n, t in zip(notes, list("一闪一闪亮晶晶")):
    n.lyric(t)
m.barlines.append("light-heavy")
s.write("out.musicxml")
```

要点：

- 时值单位是**四分音符的倍数**：`1`=四分、`0.5`=八分、`2`=二分、`4`=全音符、`1.5`=附点四分、`0.25`=十六分。
- 和弦：`m.chord(["C3","E3","G3"], dur=1, staff=2, voice=2)`。
- 每小节**每条流都要正好凑满**；左手 `staff=2` 请配 `voice=2`。
- 多声部/合奏：`s.group_parts("bracket")`，**忘了就没有括号和整齐小节线**。
- 延音线 `n.tie="start"/"stop"`；圆滑线 `n.slur="start"/"stop"`；断奏 `n.articulations.append("staccato")`；
  延长记号 `n.fermata=True`；力度 `m.dynamic("mp")`；变速 `m.set_tempo(120)`；换行 `m.system_break()`。
- 详细写法见 `references/notation-recipes.md`，XML 规则见 `references/musicxml-cheatsheet.md`。

## 第 2 步：编译 + 验货

    & $PY "$MS\scripts\mscore.py" convert out.musicxml out.mscz
    & $PY "$MS\scripts\mscore.py" convert out.mscz out.pdf
    & $PY "$MS\scripts\mscore.py" render out.mscz --dpi 130      # 生成 out-1.png
    & $PY "$MS\scripts\mscore.py" meta out.mscz                  # 复核标题/调号/拍号/小节数

**必须真的看图**（`read_image` 打开 `out-1.png`）：MuseScore 遇到不合法 MusicXML 不报错，
只是悄悄丢内容——空谱表、缺音符、和弦消失都可能是「命令成功退出码 0」。

检查清单：音符对不对、和弦有没有少音、歌词对齐、延音线/圆滑线是否成对、反复记号、小节线。
改完再 `convert` 一次，直到图对。

## 第 3 步：交付

| 要什么 | 命令 |
|---|---|
| 可编辑工程 | `convert out.musicxml out.mscz` |
| 打印/交付 PDF | `convert out.mscz out.pdf` |
| 图片（发消息、插文档） | `render out.mscz --dpi 150` |
| 音频 | `convert out.mscz out.mp3 --bitrate 192` |
| MIDI（给别的软件） | `convert out.mscz out.mid` |
| 元数据核对 | `meta out.mscz` |
| 只要第 1 页 | `convert out.mscz out.pdf --page 1` |

`mscore.py` 会自动做 magic bytes 校验，输出 `OK/BAD`；看到 `BAD` 就是真失败。

## 怎么用才对

- **一次只改一件事再重编译**：MusicXML 里错一处，MuseScore 可能整行吞掉，改多了没法定位。
- **不要相信「退出码 0」**，只相信「PNG 看起来对 + meta 数字对」。
- **不要手拼带空格的命令行**（`Program Files`），交给 `mscore.py`，它用 argv 数组。
- **生成的临时文件放工作区**，不要写系统 temp（沙箱/权限容易踩坑）。
- **歌曲结构先定，再填音符**：小节数 × 每小节时值先算平，再写流。
- 有人给你现成 `.mscz` 要做**结构改动**时，优先让 MuseScore 先转成 MusicXML 再重新生成，
  比直接手改 `.mscx` 安全得多。

## 排错

| 现象 | 原因 / 处理 |
|---|---|
| `stderr: failed open log file ...LocalLow` | 无害，写日志被权限挡了，导出照常成功 |
| 谱表整行空白 | 和弦写成了一个 `<note>` 多个 `<pitch>`；必须是多个 `<note>`，第 2 个起带 `<chord/>` |
| 小节错位 / 后面全乱 | 某条流的时值没凑满小节；`<backup>` 时值算错 |
| 多声部不连括号、小节线不对齐 | 漏了 `s.group_parts()` |
| `找不到 MuseScore 可执行文件` | 安装路径特殊时设 `MSCORE_PATH` |
| 导出 PNG 找不到 `out.png` | 实际是 `out-1.png`（多页 `out-2.png`…） |
| 中文标题变方块 | 系统缺中文字体；换机器或用英文标题 |
| 超时 | 大谱/首次启动慢，加 `--timeout 600` |

## 边界

- **不做实时编辑**：命令行不能启动插件（MS4 已移除 `-p`）。要「你看着我在 MuseScore 里改」需要
  mcp-score-server 之类的 WebSocket 桥，那属于另一条路线。
- **不控精细排版**：文本层只能控系统断行/换页（`<print new-system>`），页边距/间距/字体用 `.mss` 样式或进 GUI。
- **三连音、房子（1./2. 结尾）、渐强渐弱、装饰音、六线谱、鼓谱**：`mxml.py` 未封装，要手写 XML 片段；
  手写规则见 `references/musicxml-cheatsheet.md`，做完务必出图确认。
- **转调**别依赖 `--score-transpose`：在生成阶段整体改音高最可靠。
- 渲染质量取决于本机 MuseScore 版本（本机 4.7.5）；换大版本后先跑 `selfcheck.py`。

## 参考

- `references/musicxml-cheatsheet.md` — 会被 MuseScore 静默吞掉的那些 XML 规则
- `references/musescore-cli.md` — CLI 开关、批量 job、踩坑清单、MS3/MS4 差异
- `references/notation-recipes.md` — 常用记谱配方（旋律/钢琴/合唱/延音线/反复/歌词/转调）
- `examples/twinkle.py`、`examples/satb.py` — 两个可直接跑的完整例子
