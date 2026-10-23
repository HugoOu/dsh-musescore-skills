#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例 1：单旋律 + 歌词（最常用的「写一首歌」形态）。

运行：
    python twinkle.py out.musicxml
    python ../scripts/mscore.py convert out.musicxml out.pdf
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from mxml import Score  # noqa: E402

s = Score(title="小星星", composer="Traditional", key=0, time=(4, 4), tempo=100)
p = s.add_part("Piano", program=1)

phrase = "C4:1 C4:1 G4:1 G4:1 A4:1 A4:1 G4:2"
syllables = ["一", "闪", "一", "闪", "亮", "晶", "晶"]

m = p.add_measure()
notes = m.line(phrase)
for n, txt in zip(notes, syllables):
    n.lyric(txt)

m2 = p.add_measure()
notes = m2.line("F4:1 F4:1 E4:1 E4:1 D4:1 D4:1 C4:2")
for n, txt in zip(notes, ["满", "天", "都", "是", "小", "星", "星"]):
    n.lyric(txt)
m2.barlines.append("light-heavy")

out = sys.argv[1] if len(sys.argv) > 1 else "twinkle.musicxml"
s.write(out)
print(f"wrote {out}（{len(p.measures)} 小节）")
