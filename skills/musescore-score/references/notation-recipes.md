# 记谱配方（都用 `scripts/mxml.py` 的 API，均已实测排版通过）

统一开头：

```python
import sys, os
sys.path.insert(0, r"<skill>\scripts")        # 实际路径见 SKILL.md 的 $MS
from mxml import Score

s = Score(title="曲名", composer="作者", key=0, time=(4, 4), tempo=96)
```

`key` 是调号 fifths：`0=C, 1=G, 2=D, -1=F, -2=Bb, 3=A, -3=Eb`。
时值单位：`1`=四分音符、`0.5`=八分、`2`=二分、`4`=全音符、`1.5`=附点四分、`0.25`=十六分。

---

## 1. 单旋律（可带歌词）

```python
p = s.add_part("Piano", program=1)
m = p.add_measure()
notes = m.line("C4:1 C4:1 G4:1 G4:1 A4:1 A4:1 G4:2")
for n, txt in zip(notes, ["一","闪","一","闪","亮","晶","晶"]):
    n.lyric(txt)
```

**歌词是逐个挂在 Note 上的**，所以先接住 `line()` 的返回值，再按顺序 `zip`。
中文歌词实测正常（字体走 MuseScore 默认 Edwin + 系统回退）。

## 2. 钢琴双谱表（右手旋律 + 左手和弦）

```python
p = s.add_part("Piano", program=1, staves=2, clefs=(("G",2), ("F",4)))
m = p.add_measure()

m.line("E4:1 G4:1 C5:2", staff=1)                 # 右手：staff=1，voice 默认 1
m.chord(["C3","E3","G3"], dur=1, staff=2, voice=2) # 左手第一拍
m.chord(["C3","E3","G3"], dur=1, staff=2, voice=2) # 左手第二拍
m.rest(2, staff=2, voice=2)                        # 补满 4 拍（必须凑满！）
```

要点：**左手这条流也必须正好凑满一小节**，否则导出会错位或自动补休止。
`staff=2` 一定要配 `voice=2`（同一个 staff 内想写两条旋律才用 voice 区分）。

## 3. 同一谱表两条旋律（复调）

```python
m = p.add_measure()
m.line("E5:2 D5:2", staff=1, voice=1)   # 上声部
m.line("C5:4",      staff=1, voice=2)   # 下声部，自动 backup 回到小节头
```

两条流各自的时值加起来都必须是 4。符干方向 MuseScore 会自动处理。

## 4. 四声部合唱（多 part）

```python
s = Score(title="圣咏", key=0, time=(4,4), tempo=72)
s.group_parts("bracket")                 # 关键：不调用就没有括号、小节线不对齐

S = s.add_part("Soprano", program=53, clefs=(("G",2),))
A = s.add_part("Alto",    program=53, clefs=(("G",2),))
T = s.add_part("Tenor",   program=53, clefs=(("F",4),))
B = s.add_part("Bass",    program=53, clefs=(("F",4),))

for i, (sop, alt, ten, bas) in enumerate([...]):
    S.add_measure().note(sop, dur=4)
    A.add_measure().note(alt, dur=4)
    T.add_measure().note(ten, dur=4)
    B.add_measure().note(bas, dur=4)
```

每个 part 的小节数必须相同；`program=53` 是 Choir Aahs（见文末 GM 表）。

## 5. 跨小节延音线

```python
m1 = p.add_measure()
n = m1.line("C5:2 D5:1 E5:1")[0]      # 让 C5 是 2 拍
n.tie = "start"

m2 = p.add_measure()
n2 = m2.line("C5:2 G4:2")[0]
n2.tie = "stop"
```

跨系统的延音线 MuseScore 会自动断成两段画（实测正常）。真正要求「同一音高」，
写错音高不会报错，只是画出来是两条独立线——回图检查。

## 6. 圆滑线 / 断奏 / 重音 / 延长记号

```python
notes = m.line("A4:1 B4:1 C5:2")
notes[0].slur = "start"
notes[-1].slur = "stop"
notes[1].articulations.append("staccato")   # 或 accent / tenuto / marcato
notes[-1].fermata = True
```

`slur` 的 `number` 由 mxml 固定为 1；同一时刻多条圆滑线（交叉连线）本库不支持，需要手写 XML。

## 7. 力度、速度变化、排练记号

```python
m = p.add_measure()
m.dynamic("mp")          # 放本小节开头，p / mf / f / sf / cresc. 需用 wedge 手写
m.set_tempo(120)         # 本小节起变速（会输出 metronome 标记）
m.mark("A")              # 排练记号
```

渐强/渐弱（`<wedge type="crescendo"/>`）本库未封装：需要手写 `<direction>`，或干脆用分层力度近似。

## 8. 反复与终止线

```python
m1.repeat = "start"      # 小节线在左侧：反复开始
m4.repeat = "end"        # 小节线在右侧：反复结束
m4.barlines.append("light-heavy")    # 终止线
```

「房子」（1./2. 结尾）本库未封装，手写 `<ending number="1" type="start"/>`。

## 9. 调号 / 拍号中途变化

```python
m = p.add_measure()
m.set_key(2)             # 转到 D 大调
m.set_time(3, 4)         # 转 3/4 拍
```

会输出到该小节的 `<attributes>`。切谱号用 `m.set_clef(1, "F", 4)`。

## 10. 控制换行

```python
m6.system_break()        # 第 6 小节另起一行
m12.page_break()         # 新一页
```

文本层能控的就这些；再细的排版（音符间距、页边距、字体）要写 `.mss` 样式或进 GUI。

## 11. 出图 / 出 PDF / 出音频 / 自检

导出命令与验收标准只在 SKILL.md「第 2 / 3 步」维护，这里不重复。
唯一要记的：`mscore.py` 的参数名是 `--dpi` / `--bitrate` / `--page`，不是传给 exe 的 `-r` / `-b`。


## 12. 改一份已有的 `.mscz`

`.mscz` 是 zip，里面是 `.mscx`（纯 XML）：

```powershell
Expand-Archive -Path in.mscz -DestinationPath work\     # 或 python -m zipfile -e
# 改 work\in.mscx 后重新打包
Compress-Archive -Path work\* -DestinationPath out.mscz
```

**风险**：`.mscx` 是 MuseScore 私有格式，改错可能触发「修复」甚至损坏。适用边界：

- 只改文本类内容（标题、作者、歌词、速度值）→ 相对安全；
- 动音符/排版 → 不要改 mscx，优先重新生成 MusicXML；
- 永远先备份原件，改完 `mscore.py meta` + 渲染 PNG 双重确认。

## 13. 转调

不要依赖 `--score-transpose`（版本间行为不稳，有 no-op 的已知问题）。两个可靠办法：

1. 在生成阶段换音高（推荐）：把你记录的音名整体 ±n 半音，再重新生成；
2. 换调号 + 整体移调后重新导出，并**核实音频/谱面**。

## 附：常用 GM 音色号

| program | 音色 | program | 音色 |
|---|---|---|---|
| 1 | Acoustic Grand Piano | 41 | Violin |
| 7 | Harpsichord | 43 | Cello |
| 25 | Acoustic Guitar (nylon) | 57 | Trumpet |
| 33 | Acoustic Bass | 69 | Oboe |
| 53 | Choir Aahs | 74 | Flute |

完整表：General MIDI Level 1 program numbers（0-based 时整体减 1）。

## 已知边界（别硬扛）

- **三连音/多连音**：未封装，需手写 `<time-modification>` + `<tuplet>`；divisions 不能整除时可能有时值误差。
- **房子、渐强渐弱、装饰音、跨谱表符干、打击乐谱**：需要手写 XML 片段。
- **精细排版**：本 skill 只控到「系统断行/换页」，其余进 GUI 或 `.mss`。
- **吉他六线谱/TAB、鼓谱**：可以写（改 `<clef>` 和 note 的 `<staff>`/`<notehead>`），但本库无辅助 API，属于手写区间。
