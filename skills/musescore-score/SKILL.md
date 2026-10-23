---
name: musescore-score
description: 用 MuseScore 4 写谱作曲：把 MusicXML 无头排版成谱面，导出 .mscz/PDF/PNG/MP3/MIDI，也能在已有谱上改内容、转调、抽分谱。当用户要写歌、作曲、编曲、做五线谱、要打印谱或音频时使用；不负责 GUI 实时编辑与图片/简谱识谱（各需 MCP 桥或 OMR 工具）。
---
# MuseScore 写谱（直连路线）

把「写 MusicXML → MuseScore 命令行无头排版 → 渲染 PNG 自查 → 修」这一套固化成脚本与检查表。
不需要 GUI、插件或联网。产出物是谱面文件（.mscz / PDF / PNG / MP3 / MIDI），不是文字说明。

## 前置条件

- 本机装有 **MuseScore 4**（实测 4.7.5）。安装路径非标准时设 `MSCORE_PATH`。
- **Python 3.10+**，脚本只用标准库，无需 pip 安装。
- 找不到 MuseScore 时**停下并告诉用户装什么**，不要尝试自行下载安装（沙箱里 pip/安装包基本走不通，会浪费十几分钟）。

## 路径

    $MS  技能目录（base directory），本机为 "$env:DSH_HOME\skills\musescore-score"
         DSH_HOME 未设置时退回 "$env:USERPROFILE\.dsh\skills\musescore-score"
    $PY  当前可用的 Python 3.10+（DSH 会话里取 load_workspace_dependencies 返回的 python）

正文提到的 `scripts/…`、`references/…` 一律相对 `$MS` 解析。

## 第 0 步：先自检（新环境 / MuseScore 升级后必做）

    & $PY "$MS\scripts\selfcheck.py" --out .\ms-selfcheck

12 项全 PASS 才继续；失败项会直接指到「找不到 MuseScore」还是「产物异常」。
顺手打开 `.\ms-selfcheck\selfcheck-1.png` 确认字体与符号正常。

## 第 1 步：用 mxml 写谱

```python
import sys; sys.path.insert(0, r"<技能目录>\scripts")
from mxml import Score

s = Score(title="曲名", composer="作者", key=0, time=(4, 4), tempo=96)
p = s.add_part("Piano", program=1)          # staves=2 时自动配高低音谱号
m = p.add_measure()
notes = m.line("C4:1 C4:1 G4:1 G4:1 A4:1 A4:1 G4:2")   # 音名:时值(四分音符倍数)
for n, t in zip(notes, list("一闪一闪亮晶晶")):
    n.lyric(t)
m.barlines.append("light-heavy")
s.write("out.musicxml")
```

- 时值单位是**四分音符的倍数**：`1`=四分、`0.5`=八分、`2`=二分、`4`=全音符、`1.5`=附点四分、`0.25`=十六分。
- 和弦 `m.chord(["C3","E3","G3"], dur=1, staff=2, voice=2)`；双谱表左手用 `staff=2` + `voice=2`。
- 每小节**每条流都要正好凑满**，否则后面全乱。
- 多声部/合奏必须 `s.group_parts("bracket")`，否则谱表不连括号、小节线不对齐。
- 延音线 `n.tie="start"/"stop"`；圆滑线 `n.slur=…`；断奏 `n.articulations.append("staccato")`；
  延长记号 `n.fermata=True`；力度 `m.dynamic("mp")`；变速 `m.set_tempo(120)`；换行 `m.system_break()`。
- 配方见 `references/notation-recipes.md`；会被静默吞掉的 XML 规则见 `references/musicxml-cheatsheet.md`。

## 第 2 步：编译 + 验货

    & $PY "$MS\scripts\mscore.py" convert out.musicxml out.mscz
    & $PY "$MS\scripts\mscore.py" convert out.mscz out.pdf
    & $PY "$MS\scripts\mscore.py" render out.mscz --dpi 130      # 生成 out-1.png
    & $PY "$MS\scripts\mscore.py" meta out.mscz                  # 标题/调号/拍号/小节数

**必须真的看图**（用 `read_image` 打开 `out-1.png`）。MuseScore 遇到不合法 MusicXML 不报错，
只是悄悄丢内容——空谱表、缺音符、和弦消失都可能伴随「退出码 0」。

看图检查：音符与和弦对不对、歌词对齐、延音线/圆滑线成对、反复记号、小节线、有没有整行空白。
改一处 → 重新 `convert` → 再看图，直到对。

**分辨率会骗人**：低 DPI 下相邻三度叠置的和弦会挤成一团黑块，看着像丢音或错音。
先放大确认是渲染假象再决定改不改——`render ... --dpi 300` 重渲染，或裁一块放大（有 Pillow 时
`Image.open(p).crop(box).resize(...)`）。凭缩略图改数据，经常把本来正确的和弦改坏。

## 第 3 步：交付

| 要什么 | 命令 |
|---|---|
| 可编辑工程 | `convert out.musicxml out.mscz` |
| 打印/交付 PDF | `convert out.mscz out.pdf` |
| 图片 | `render out.mscz --dpi 150` |
| 音频 | `convert out.mscz out.mp3 --bitrate 192` |
| MIDI | `convert out.mscz out.mid` |
| 只要第 1 页 | `convert out.mscz out.pdf --page 1` |

`mscore.py` 自带 magic bytes 校验，逐行打印 `OK/BAD`；出现 `BAD` 就是真失败。
验收标准：**图对 + `meta` 数字对 + 全部 OK**，三者缺一不算完成。

## 坑（违反就静默出错）

- 和弦必须写成多个 `<note>`（第 2 个起带 `<chord/>`）。一个 `<note>` 塞多个 `<pitch>` 会让 MuseScore
  丢掉整个音，谱表整行空白且不报错。`mxml.chord()` 已处理，手写 XML 时注意。
- 多谱表/多声部换流要 `<backup>` 回到小节头；`<backup>` 的时值 = 刚写完那条流的总时值。
- `stderr: failed open log file …LocalLow` 是无害的写日志失败，导出照常成功，别据此判失败。
- `-o out.png` 实际生成 `out-1.png`（多页 `out-2.png`…）；`mscore.py render` 已处理。
- 命令行**不能**启动 MuseScore 插件（MS4 已移除 `-p`），所有「实时编辑」需求都超出本技能范围。
- `--score-parts` 会往 stdout 打整包 JSON（上万字符），非必要不碰。

## 失败处理

- 脚本返回非 0 或打印 `BAD`：先看是「源文件不存在」「找不到 exe」还是「产物 0 字节」，按提示修，不要直接重试。
- 同一处连续改两次仍不对：**退回最小可编译版本**（1 小节、1 个音）确认链路通，再逐步加回，
  不要在一份复杂 MusicXML 上盲改。
- 渲染图异常但 meta 正常：多半是内容缺失（和弦/时值），回到第 2 步看整行而不是只看局部。
- 三次尝试仍不通就停下，报告：卡在哪一步、`selfcheck` 输出、最后一份可编译文件路径。

## 边界

- **不做实时编辑**：要「你看着我在 MuseScore 里改」需要 mcp-score-server 之类 WebSocket 插件桥，另一条路线。
- **不控精细排版**：文本层只能控系统断行/换页（`<print new-system>`）；页边距、间距、字体用 `.mss` 样式或进 GUI。
- **未封装**：三连音、房子（1./2. 结尾）、渐强渐弱、装饰音、六线谱、鼓谱——需要手写 XML 片段
  （规则见 `references/musicxml-cheatsheet.md`），做完必须出图确认。
- 转调别依赖 `--score-transpose`（版本间行为不稳）：在生成阶段整体改音高最可靠。
- 渲染质量取决于本机 MuseScore 大版本；换版本后先跑 `selfcheck.py`。

## 资源

- `references/notation-recipes.md`：旋律/钢琴/合唱/延音线/反复/歌词/转调等 13 个配方——需要具体写法时读。
- `references/musicxml-cheatsheet.md`：要手写或修改 MusicXML 时读（元素顺序、和弦、backup、tuplet、part-group）。
- `references/musescore-cli.md`：要用批量 `-j`、`--page`、样式文件，或排查导出异常时读。
- `assets/examples/twinkle.py`、`assets/examples/satb.py`：可直接运行的完整例子，复制改写最快。
