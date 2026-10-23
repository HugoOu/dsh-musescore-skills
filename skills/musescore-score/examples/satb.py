#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例 2：四声部合唱（SATB）——演示多 part、每 part 独立谱号。

运行：
    python satb.py out.musicxml
    python ../scripts/mscore.py convert out.musicxml out.pdf
    python ../scripts/mscore.py convert out.musicxml out.png --dpi 130
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from mxml import Score  # noqa: E402

# program: 53 = Choir Aahs
s = Score(title="四声部圣咏", composer="musescore-score skill", key=0, time=(4, 4), tempo=72)
s.group_parts("bracket")          # 多声部必须归组，否则谱表不连括号、小节线不对齐

parts = {
    "Soprano": (s.add_part("Soprano", program=53, clefs=(("G", 2),)), ["C5", "F5", "D5", "C5"]),
    "Alto":    (s.add_part("Alto",    program=53, clefs=(("G", 2),)), ["G4", "A4", "B4", "G4"]),
    "Tenor":   (s.add_part("Tenor",   program=53, clefs=(("F", 4),)), ["E4", "F4", "G4", "E4"]),
    "Bass":    (s.add_part("Bass",    program=53, clefs=(("F", 4),)), ["C3", "F3", "G3", "C3"]),
}

for name, (part, pitches) in parts.items():
    for i, pitch in enumerate(pitches):
        m = part.add_measure()
        n = m.note(pitch, dur=4)          # 全音符
        if i == 0:
            m.dynamic("p")
        if i == 3:
            m.barlines.append("light-heavy")
            n.fermata = True

out = sys.argv[1] if len(sys.argv) > 1 else "satb.musicxml"
s.write(out)
print(f"wrote {out}（{len(parts)} 声部 × 4 小节）")
