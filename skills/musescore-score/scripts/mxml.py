#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mxml — 极简 MusicXML 4.0 (partwise) 构建器，专为「交给 MuseScore CLI 排版」设计。

只依赖标准库。目标不是覆盖 MusicXML 全貌，而是让代理用很少的代码写出**能正确排版**的谱。

核心概念
--------
* 时值单位统一用「四分音符」的倍数：1=四分音符，0.5=八分，2=二分，4=全音符，1.5=附点四分，0.25=十六分。
  内部按 8 units/四分音符 换算，因此附点、16 分、32 分都能精确表示（不接受无法精确表示的值）。
* 音高写法：`C4` `F#4` `Bb3` `C##5`（可读性优先，MIDI 编号请自行换算）。
* 一个 Measure 里按 (staff, voice) 分「流」(stream)，每条流从第 0 tick 开始，
  导出时自动插入 <backup>，所以双谱表/多声部不需要手工算 offset。
* line() 是给代理用的紧凑写法：`"C4:1 D4:0.5 R:0.5"`，返回 Note 列表，
  可以继续挂连音线/歌词/力度/表情记号。

最小用例
--------
    from mxml import Score

    s = Score(title="小星星", composer="Traditional", tempo=100)
    p = s.add_part("Piano")
    m = p.add_measure()
    notes = m.line("C4:1 C4:1 G4:1 G4:1 A4:1 A4:1 G4:2")
    m.new_line()          # 只是可读性分隔；换行不影响小节
    s.write("twinkle.musicxml")

命令行
------
    python mxml.py out.musicxml          # 生成一个内置示例（C 大调 + 双谱表）
"""

from __future__ import annotations

import sys
from xml.sax.saxutils import escape, quoteattr

DIVS_PER_QUARTER = 8          # 每个四分音符 8 units，16 分=2，32 分=1
UNITS_PER_WHOLE = DIVS_PER_QUARTER * 4

# units -> (MusicXML type 名, 附点个数)
_UNITS_TO_TYPE = {
    32: ("whole", 0), 48: ("whole", 1),
    16: ("half", 0), 24: ("half", 1),
    8: ("quarter", 0), 12: ("quarter", 1),
    4: ("eighth", 0), 6: ("eighth", 1),
    2: ("16th", 0), 3: ("16th", 1),
    1: ("32nd", 0),
}

_STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
_INDEX_TO_STEP = {v: k for k, v in _STEP_INDEX.items()}


def parse_pitch(text: str):
    """'F#4' / 'Bb3' / 'C4' -> (step, alter, octave)。"""
    text = text.strip()
    if not text:
        raise ValueError("空音高")
    step = text[0].upper()
    if step not in _STEP_INDEX:
        raise ValueError(f"无法识别的音名: {text!r}（应为 A-G 开头，如 C4 / F#4 / Bb3）")
    i = 1
    alter = 0
    while i < len(text) and text[i] in "#b":
        alter += 1 if text[i] == "#" else -1
        i += 1
    try:
        octave = int(text[i:])
    except ValueError:
        raise ValueError(f"音高缺少八度数字: {text!r}（如 C4）") from None
    if not -1 <= octave <= 9:
        raise ValueError(f"八度超出范围: {text!r}")
    return step, alter, octave


def _units(dur_quarters: float) -> int:
    """四分音符倍数 -> units；无法精确表示时直接报错（避免静默写错谱）。"""
    units = dur_quarters * DIVS_PER_QUARTER
    rounded = round(units)
    if abs(units - rounded) > 1e-6:
        raise ValueError(
            f"时值 {dur_quarters} 个四分音符无法精确表示（最小单位是 1/32 音符 = 0.125）"
        )
    if rounded < 1:
        raise ValueError(f"时值太小: {dur_quarters}")
    if rounded not in _UNITS_TO_TYPE:
        raise ValueError(
            f"时值 {dur_quarters} 没有对应的音符类型（支持：4 3 2 1.5 1 0.75 0.5 0.375 0.25 0.125）"
        )
    return rounded


class Note:
    """一个音符（可含多个音高 = 和弦）或一个休止符。"""

    def __init__(self, pitches, dur_quarters, staff=1, voice=1):
        self.pitches = list(pitches)                 # [(step, alter, octave), ...]；空 = 休止
        self.units = _units(dur_quarters)
        self.ntype, self.dots = _UNITS_TO_TYPE[self.units]
        self.staff = staff
        self.voice = voice
        self.tie = None            # None | "start" | "stop" | "continue"
        self.slur = None           # None | "start" | "stop" | "continue"
        self.fermata = False
        self.articulations = []    # "staccato" / "accent" / "tenuto" / "marcato" ...
        self.lyrics = []           # [(verse, text), ...]
        self.accidental = None     # "sharp" / "flat" / "natural" 强制显示临时记号

    @property
    def is_rest(self):
        return not self.pitches

    def lyric(self, text, verse=1):
        self.lyrics.append((verse, text))
        return self

    def lyrics_batch(self, words, verse=1):
        """把 words 依次挂到和弦的各个音上（单音时只挂第一个）。"""
        for w in words:
            if w:
                self.lyric(w, verse)
        return self


class Measure:
    def __init__(self, part, number):
        self.part = part
        self.number = number
        self.streams = {}          # (staff, voice) -> [Note, ...]
        self.tempo = None          # 本小节起生效的 BPM
        self.dynamics = []         # [(staff, "mp"), ...] 放在本小节开头
        self.rehearsal = None
        self.attributes = []       # 额外的 attributes 片段（调号/拍号变更等，见 set_key 等）
        self.new_system = False
        self.new_page = False
        self.repeat = None         # "start" | "end"
        self.barlines = []         # 附加小节线（"light-heavy" / "dashed" ...）
        self.coda = False
        self.segno = False

    # ---- 紧凑写谱 ----
    def line(self, text, staff=1, voice=1):
        """`"C4:1 D4:0.5 R:0.5"` / 和弦 `"C3+E3+G3:2"`；省略时值默认 1（四分音符）。

        返回写进去的 Note 列表（顺序与文本一致），可继续挂歌词/连音线。
        """
        created = []
        for token in text.split():
            if not token:
                continue
            body, _, dur_s = token.partition(":")
            dur = float(dur_s) if dur_s else 1.0
            if body.upper() in ("R", "REST"):
                n = Note([], dur, staff=staff, voice=voice)
            else:
                pitches = [parse_pitch(p) for p in body.split("+") if p]
                n = Note(pitches, dur, staff=staff, voice=voice)
            self.streams.setdefault((staff, voice), []).append(n)
            created.append(n)
        return created

    def rest(self, dur=1.0, staff=1, voice=1):
        return self.line(f"R:{dur}", staff=staff, voice=voice)[0]

    def note(self, pitch, dur=1.0, staff=1, voice=1):
        """单音便捷写法，返回 Note。"""
        return self.line(f"{pitch}:{dur}", staff=staff, voice=voice)[0]

    def chord(self, pitches, dur=1.0, staff=1, voice=1):
        return self.line(f"{'+'.join(pitches)}:{dur}", staff=staff, voice=voice)[0]

    def new_line(self):
        """Markdown 风格的可读性分隔，不影响导出。"""
        return self

    # ---- 记谱元素 ----
    def set_tempo(self, bpm):
        self.tempo = bpm
        return self

    def dynamic(self, text, staff=1):
        self.dynamics.append((staff, text))
        return self

    def mark(self, text):
        """排练记号（Rehearsal mark），如 "A"、"副歌"。"""
        self.rehearsal = text
        return self

    def set_key(self, fifths):
        self.attributes.append(f"<key><fifths>{fifths}</fifths></key>")
        return self

    def set_time(self, beats, beat_type):
        self.attributes.append(
            f"<time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>"
        )
        return self

    def set_clef(self, staff, sign, line=2):
        self.attributes.append(
            f'<clef number="{staff}"><sign>{sign}</sign><line>{line}</line></clef>'
        )
        return self

    def system_break(self):
        self.new_system = True
        return self

    def page_break(self):
        self.new_page = True
        return self

    # ---- 导出 ----
    def _emit_note(self, n: Note, out: list):
        """和弦在 MusicXML 里是「多个 <note>，从第二个起带 <chord/>」，
        不是一个 <note> 里放多个 <pitch>（那样 MuseScore 会直接丢掉这个音）。"""
        heads = n.pitches or [None]
        for idx, head in enumerate(heads):
            out.append("      <note>")
            if head is None:
                out.append("        <rest/>")
            else:
                if idx:
                    out.append("        <chord/>")
                step, alter, octave = head
                out.append("        <pitch>")
                out.append(f"          <step>{step}</step>")
                if alter:
                    out.append(f"          <alter>{alter}</alter>")
                out.append(f"          <octave>{octave}</octave>")
                out.append("        </pitch>")
            out.append(f"        <duration>{n.units}</duration>")
            if n.tie:
                out.append(f'        <tie type="{n.tie}"/>')
            out.append(f"        <voice>{n.voice}</voice>")
            out.append(f"        <type>{n.ntype}</type>")
            for _ in range(n.dots):
                out.append("        <dot/>")
            if idx == 0 and n.accidental:
                out.append(f'        <accidental>{n.accidental}</accidental>')
            if idx == 0:
                # notations：连线 / 延音线 / 延长记号 / 演奏法（只挂在和弦的第一个音上）
                notations = []
                if n.slur:
                    notations.append(f'<slur type="{n.slur}" number="1"/>')
                if n.tie:
                    notations.append(f'<tied type="{n.tie}"/>')
                if n.fermata:
                    notations.append('<fermata type="upright"/>')
                if n.articulations:
                    notations.append(
                        "<articulations>" + "".join(f"<{a}/>" for a in n.articulations)
                        + "</articulations>"
                    )
                if notations:
                    out.append("        <notations>" + "".join(notations) + "</notations>")
                for verse, text in n.lyrics:
                    out.append(f'        <lyric number="{verse}"><syllabic>single</syllabic>'
                               f"<text>{escape(text)}</text></lyric>")
            out.append(f"        <staff>{n.staff}</staff>")
            out.append("      </note>")

    def _emit(self, out: list):
        out.append(f'    <measure number="{self.number}">')
        if self.new_page:
            out.append('      <print new-page="yes"/>')
        elif self.new_system:
            out.append('      <print new-system="yes"/>')

        if self.number == 1:
            out.append("      <attributes>")
            out.append(f"        <divisions>{DIVS_PER_QUARTER}</divisions>")
            out.append(f"        <key><fifths>{self.part.score.key}</fifths></key>")
            beats, beat_type = self.part.score.time
            out.append(f"        <time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>")
            if self.part.staves > 1:
                out.append(f"        <staves>{self.part.staves}</staves>")
            for idx, (sign, line) in enumerate(self.part.clefs, start=1):
                num = f' number="{idx}"' if self.part.staves > 1 else ""
                out.append(f"        <clef{num}><sign>{sign}</sign><line>{line}</line></clef>")
            out.append("      </attributes>")
            if self.part.score.tempo:
                bpm = self.part.score.tempo
                out.append(
                    '      <direction placement="above"><direction-type>'
                    "<metronome><beat-unit>quarter</beat-unit>"
                    f"<per-minute>{bpm}</per-minute></metronome></direction-type>"
                    f'<sound tempo="{bpm}"/></direction>'
                )
        elif self.attributes:
            out.append("      <attributes>" + "".join(self.attributes) + "</attributes>")

        if self.tempo and self.number != 1:
            out.append(
                '      <direction placement="above"><direction-type>'
                "<metronome><beat-unit>quarter</beat-unit>"
                f"<per-minute>{self.tempo}</per-minute></metronome></direction-type>"
                f'<sound tempo="{self.tempo}"/></direction>'
            )
        for staff, dyn in self.dynamics:
            out.append(
                f'      <direction placement="below"><direction-type>'
                f"<dynamics><{dyn}/></dynamics></direction-type>"
                f"<staff>{staff}</staff></direction>"
            )
        if self.rehearsal:
            out.append(
                '      <direction placement="above"><direction-type>'
                f'<rehearsal>{escape(self.rehearsal)}</rehearsal></direction-type></direction>'
            )

        if self.repeat == "start":
            out.append('      <barline location="left"><repeat direction="forward"/></barline>')

        prev_total = None
        for (staff, voice) in sorted(self.streams):
            notes = self.streams[(staff, voice)]
            if prev_total is not None:
                out.append(f"      <backup><duration>{prev_total}</duration></backup>")
            total = sum(n.units for n in notes)
            for n in notes:
                self._emit_note(n, out)
            prev_total = total

        if self.repeat == "end":
            out.append('      <barline location="right"><repeat direction="backward"/></barline>')
        if self.coda:
            out.append('      <direction placement="above"><direction-type>'
                       "<coda/></direction-type></direction>")
        if self.segno:
            out.append('      <direction placement="above"><direction-type>'
                       "<segno/></direction-type></direction>")
        for style in self.barlines:
            out.append(f'      <barline location="right"><bar-style>{style}</bar-style></barline>')
        out.append("    </measure>")


class Part:
    def __init__(self, score, ident, name, program=1, staves=1, clefs=(("G", 2),), part_name=None):
        self.score = score
        self.ident = ident
        self.name = name
        self.program = program
        self.staves = staves
        self.clefs = list(clefs)
        self.part_name = part_name or name
        self.measures = []

    def add_measure(self) -> Measure:
        m = Measure(self, len(self.measures) + 1)
        self.measures.append(m)
        return m

    def measures_range(self, count):
        """连续加 count 个小节，返回列表。"""
        return [self.add_measure() for _ in range(count)]

    def _part_list_xml(self):
        out = ["    <score-part id=%s>" % quoteattr(self.ident)]
        out.append(f"      <part-name>{escape(self.part_name)}</part-name>")
        out.append(f'      <score-instrument id="{self.ident}-I1">'
                   f"<instrument-name>{escape(self.name)}</instrument-name></score-instrument>")
        out.append(f'      <midi-instrument id="{self.ident}-I1">'
                   f"<midi-channel>1</midi-channel><midi-program>{self.program}</midi-program>"
                   "</midi-instrument>")
        out.append("    </score-part>")
        return out


class Score:
    def __init__(self, title="", composer="", key=0, time=(4, 4), tempo=None, subtitle=""):
        self.title = title
        self.subtitle = subtitle
        self.composer = composer
        self.key = key            # fifths：0=C, 1=G, -1=F, 2=D, -2=Bb ...
        self.time = time
        self.tempo = tempo
        self.parts = []
        self._next_part = 1
        self.group = None         # {"symbol": "bracket"|"brace"|"line"|"square", "barline": bool}

    def group_parts(self, symbol="bracket", barline=True):
        """把多个 part 归到一个括号组里。

        多声部/合奏谱必须调用：否则 MuseScore 导入后虽然还是同一页，
        但谱表之间不会连括号、小节线不对齐，看起来像各弹各的。
        """
        self.group = {"symbol": symbol, "barline": barline}
        return self

    def add_part(self, name="Piano", program=1, staves=1, clefs=None, part_name=None) -> Part:
        """staves=2 时会按 clefs 依次输出多谱号，默认高音+低音。"""
        if staves == 1:
            clefs = clefs or (("G", 2),)
        else:
            clefs = clefs or (("G", 2), ("F", 4))
        ident = f"P{self._next_part}"
        self._next_part += 1
        part = Part(self, ident, name, program=program, staves=staves,
                    clefs=clefs, part_name=part_name)
        self.parts.append(part)
        return part

    def to_xml(self) -> str:
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
               '"http://www.musicxml.org/dtds/partwise.dtd">',
               '<score-partwise version="4.0">']
        if self.title or self.composer:
            out.append("  <work><work-title>" + escape(self.title) + "</work-title></work>")
        out.append("  <identification>")
        if self.composer:
            out.append(f'    <creator type="composer">{escape(self.composer)}</creator>')
        out.append("    <encoding><software>mxml.py (DSH musescore-score skill)</software></encoding>")
        out.append("  </identification>")
        out.append("  <part-list>")
        if self.group and len(self.parts) > 1:
            out.append('    <part-group type="start" number="1">')
            out.append(f"      <group-symbol>{self.group['symbol']}</group-symbol>")
            if self.group["barline"]:
                out.append("      <group-barline>yes</group-barline>")
            out.append("    </part-group>")
        for p in self.parts:
            out.extend(p._part_list_xml())
        if self.group and len(self.parts) > 1:
            out.append('    <part-group type="stop" number="1"/>')
        out.append("  </part-list>")
        for p in self.parts:
            out.append(f'  <part id="{p.ident}">')
            for m in p.measures:
                m._emit(out)
            out.append("  </part>")
        out.append("</score-partwise>")
        return "\n".join(out) + "\n"

    def write(self, path):
        xml = self.to_xml()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(xml)
        return path


# --------------------------------------------------------------------------- #
# 内置示例：双谱表钢琴小品（也是 selfcheck 的素材之一）
# --------------------------------------------------------------------------- #
def demo() -> Score:
    s = Score(title="秋日小品", composer="DSH agent", tempo=96)
    p = s.add_part("Piano", program=1, staves=2, clefs=(("G", 2), ("F", 4)))

    bars = [
        ("E4:1 G4:1 C5:2", ["C3", "E3", "G3"]),
        ("B4:1 C5:1 A4:2", ["G2", "C3", "E3"]),
        ("G4:1 A4:1 B4:2", ["A2", "C3", "E3"]),
        ("C5:1 D5:1 E5:2", ["F2", "A2", "C3"]),
        ("D5:1 C5:1 B4:2", ["G2", "B2", "D3"]),
        ("A4:1 G4:1 F4:2", ["F2", "A2", "C3"]),
        ("E4:1 F4:1 G4:2", ["C3", "E3", "G3"]),
        ("C5:4", ["C3", "E3", "G3"]),
    ]
    for i, (rh, lh) in enumerate(bars, start=1):
        m = p.add_measure()
        ns = m.line(rh, staff=1)
        if i == 1:
            m.dynamic("mp")
        if i == 3:
            ns[0].slur = "start"
            ns[-1].slur = "stop"
        if i == 8:
            ns[0].fermata = True
            m.barlines.append("light-heavy")
        # 左手：整小节拆成两个二分音符和弦，比全音符更有推动感
        m.chord(lh, dur=2, staff=2, voice=2)
        m.chord(lh, dur=2, staff=2, voice=2)
    return s


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "demo.musicxml"
    demo().write(out)
    print(f"wrote {out}")
