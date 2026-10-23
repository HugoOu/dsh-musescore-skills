# MusicXML 速查（只列会被 MuseScore 静默吞掉的那些规则）

`scripts/mxml.py` 已经处理了这里的大部分规则；手写/改 XML 时按这份对照。

## 骨架

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <work><work-title>标题</work-title></work>
  <identification><creator type="composer">作曲</creator></identification>
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1"> ... </measure>
  </part>
</score-partwise>
```

DOCTYPE 可以省略，MuseScore 不校验 DTD；但保留它能让你用校验工具自查。

## divisions：全谱唯一的时间刻度

`<divisions>` = 每个四分音符切成几份，**整份谱只能有一个值**（写在第一小节 `<attributes>` 里）。

| divisions | 能表示的最短时值 |
|---|---|
| 1 | 四分音符（不能写八分！） |
| 2 | 八分 |
| 4 | 十六分 |
| 8 | 三十二分 |

`mxml.py` 用 8，所以附点/三十二分都能写。`<duration>` 一律是 divisions 整数倍：
divisions=8 时，全=32、附点二分=24、二分=16、附点四分=12、四分=8、附点八分=6、八分=4、十六分=2、附点十六分=3、三十二分=1。

## 和弦：必须是多个 `<note>`，不是多个 `<pitch>`

```xml
<!-- 正确：C3 大三和弦 -->
<note><pitch><step>C</step><octave>3</octave></pitch>
  <duration>32</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
<note><chord/>
  <pitch><step>E</step><octave>3</octave></pitch>
  <duration>32</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
<note><chord/>
  <pitch><step>G</step><octave>3</octave></pitch>
  <duration>32</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
```

**一个 `<note>` 里塞多个 `<pitch>` 是无效的，MuseScore 会把整个音直接丢掉**（实测：低音谱表整行空白）。
第二个及以后的音必须带 `<chord/>`，并且每个 `<note>` 都要重复 `<duration>`/`<voice>`/`<type>`/`<staff>`。

## 多谱表 / 多声部：靠 `<backup>` 回到本小节开头

同一小节里，第二个 `<staff>` 或第二个 `<voice>` 的音符流之前要插入：

```xml
<backup><duration>本小节已用掉的总时值</duration></backup>
```

之后从头写另一条流。规则简单但容易错：**每条流自己凑满一小节的时值**，`<backup>` 的时值等于「刚写完那条流的总时值」。
（`mxml.py` 按 `(staff, voice)` 分组自动插入。）

## 延音线 vs 圆滑线

```xml
<!-- 延音线：同一个音高跨越，声音相连。两处都要写 -->
<note>
  <pitch>...</pitch>
  <duration>16</duration>
  <tie type="start"/>                 <!-- 声音层 -->
  <voice>1</voice><type>half</type>
  <notations><tied type="start"/></notations>   <!-- 显示层 -->
</note>

<!-- 圆滑线：不同音高之间的连奏，只有显示层 -->
<notations><slur type="start" number="1"/></notations>
... 目标音 ...
<notations><slur type="stop" number="1"/></notations>
```

只写 `<tie>` 不写 `<tied>`（或反之）会出现「有声音没连线 / 有连线没声音」。

## 力度、速度、排练记号

```xml
<!-- 力度（挂在谱表上，placement 决定在谱表上/下） -->
<direction placement="below"><direction-type>
  <dynamics><mp/></dynamics></direction-type><staff>1</staff></direction>

<!-- 速度 -->
<direction placement="above"><direction-type>
  <metronome><beat-unit>quarter</beat-unit><per-minute>96</per-minute></metronome>
  </direction-type><sound tempo="96"/></direction>

<!-- 排练记号 -->
<direction placement="above"><direction-type><rehearsal>A</rehearsal></direction-type></direction>
```

## 反复、房子、小节线

```xml
<!-- 反复：必须成对，位置在小节线 -->
<barline location="left"><repeat direction="forward"/></barline>     <!-- 反复开始 -->
<barline location="right"><repeat direction="backward" times="2"/></barline>  <!-- 反复结束 -->

<!-- 终止线 -->
<barline location="right"><bar-style>light-heavy</bar-style></barline>

<!-- 房子（1./2. 结尾）：写在 <measure> 的 attributes 里 -->
<ending number="1" type="start"/>
... 该房子包含的小节 ...
<ending number="1" type="stop"/>
```

## 换行 / 换页

```xml
<print new-system="yes"/>   <!-- 该小节另起一行（实测有效，用来控制系统断行） -->
<print new-page="yes"/>
```

写进 `<measure>` 开头。想让一页放几小节、哪小节换行，这是唯一可靠的文本级控制手段；
更细的排版（音符间距、页边距）建议改 `.mss` 样式文件或进 GUI 调。

## 多声部/合奏：`<part-group>`

```xml
<part-list>
  <part-group type="start" number="1">
    <group-symbol>bracket</group-symbol>
    <group-barline>yes</group-barline>
  </part-group>
  <score-part id="P1"><part-name>Soprano</part-name></score-part>
  ...
  <part-group type="stop" number="1"/>
</part-list>
```

**漏掉它不会报错**，但导出的谱表不连括号、小节线不对齐，看起来像几个独立系统（实测对比过）。

## 调号 / 拍号 / 谱号变更

```xml
<measure number="12">
  <attributes>
    <key><fifths>2</fifths></key>          <!-- 2=D, -2=Bb, 1=G, -1=F -->
    <time><beats>3</beats><beat-type>4</beat-type></time>
    <clef number="1"><sign>G</sign><line>2</line></clef>
  </attributes>
  ...
```

只在变更处写；第一小节的 `<attributes>` 还要带 `<divisions>`、`<staves>`（多谱表）。

## 三连音（`mxml.py` 未封装，需要手写）

```xml
<note>
  <pitch><step>C</step><octave>5</octave></pitch>
  <duration>4</duration>                    <!-- 名义时值 = 实际 8 的 2/3 → divisions=8 时写 4? 见下 -->
  <voice>1</voice><type>eighth</type>
  <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
  <notations><tuplet type="start" number="1"/></notations>
</note>
```

要点：`<duration>` 写**实际占用的 tick**（三个八分三连音，每个占 `8/3`… 需要 divisions 能整除 3，
例如 divisions=24 时每个占 8），`<type>` 写名义时值（eighth），三个音的最后一个加 `<tuplet type="stop"/>`。
divisions 不能整除时 MuseScore 会自行调整，但可能出现时值误差——这是本 skill 的已知边界。

## 装饰音（倚音）

```xml
<note>
  <grace/>
  <pitch><step>D</step><octave>5</octave></pitch>
  <voice>1</voice><type>eighth</type>
  <notations><slur type="start" number="1"/></notations>
</note>
```

`<grace/>` 的 note **不带 `<duration>`**。

## 校验思路

MuseScore 对不合法 XML 的处理是「尽量导入 + 可能弹修复提示」，命令行下**不报错也可能丢内容**。
所以每次生成后至少做两件事：

1. 导 PNG 肉眼看（本 skill 的核心做法）；
2. `mscore.py meta out.mscz` 复核 `measures` / `keysig` / `timesig` / `title` 是否符合预期。
