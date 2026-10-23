#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck.py — 端到端自检：确认这台机器上「写 MusicXML → MuseScore 排版 → 导出 → 校验」全链路可用。

它会
  1. 找到 MuseScore 并打印版本；
  2. 用 mxml 写一首覆盖主要记谱元素的自检谱
     （G 大调、双谱表、和弦、跨小节延音线、圆滑线、力度、歌词、跳房子/反复、延长记号、系统断行）；
  3. 依次导出 .mscz / .pdf / .png / .mid / .mp3，逐个校验 magic bytes 与大小；
  4. 用 --score-meta 读回小节数、调号、标题，确认内容没被吞掉；
  5. 打印 PASS/FAIL 汇总，失败返回非零退出码。

用法
----
    python selfcheck.py               # 默认在 ./.ms-selfcheck 下跑全套
    python selfcheck.py --out D:/tmp/x --no-audio
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mxml          # noqa: E402
import mscore        # noqa: E402

RESULTS = []


def record(ok, name, detail=""):
    RESULTS.append((ok, name, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  — {detail}" if detail else ""))
    return ok


def build_score(path):
    """自检谱：尽量把容易写错的元素都串一遍。"""
    s = mxml.Score(title="自检曲", composer="musescore-score skill",
                   key=1, time=(4, 4), tempo=100)   # key=1 → G 大调
    p = s.add_part("Piano", program=1, staves=2, clefs=(("G", 2), ("F", 4)))

    m1 = p.add_measure()
    rh = m1.line("G4:1 A4:1 B4:2", staff=1)
    rh[0].lyric("自")
    rh[1].lyric("检")
    rh[2].lyric("曲")
    rh[2].tie = "start"                     # 跨小节延音线
    m1.dynamic("mf")
    m1.mark("A")                            # 排练记号
    m1.repeat = "start"
    for _ in range(2):
        m1.chord(["G2", "B2", "D3"], dur=2, staff=2, voice=2)

    m2 = p.add_measure()
    rh2 = m2.line("B4:2 A4:1 G4:1", staff=1)
    rh2[0].tie = "stop"
    rh2[1].slur = "start"                   # 圆滑线
    rh2[2].slur = "stop"
    rh2[2].articulations.append("staccato")
    rh2[2].fermata = True
    m2.repeat = "end"
    m2.barlines.append("light-heavy")
    m2.system_break()
    for _ in range(2):
        m2.chord(["G2", "B2", "D3"], dur=2, staff=2, voice=2)

    s.write(path)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.getcwd(), ".ms-selfcheck"))
    ap.add_argument("--no-audio", action="store_true", help="跳过 mp3（较慢）")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    print(f"输出目录: {out}\n")

    # 1. 环境
    try:
        exe = mscore.find_exe()
        rc, so, se = mscore.run_musescore(exe, ["--version"], timeout=120)
        ver = (so or se).strip().splitlines()
        record(rc == 0, "找到 MuseScore", f"{exe}｜{ver[0] if ver else '版本未知'}")
    except Exception as e:                                    # noqa: BLE001
        record(False, "找到 MuseScore", str(e))
        return summary()

    # 2. 写谱
    xml = os.path.join(out, "selfcheck.musicxml")
    try:
        build_score(xml)
        size = os.path.getsize(xml)
        record(size > 2000, "生成 MusicXML", f"{size} B")
    except Exception as e:                                    # noqa: BLE001
        record(False, "生成 MusicXML", str(e))
        return summary()

    # 3. 导出
    targets = [("mscz", None), ("pdf", None), ("png", {"dpi": 120}), ("mid", None)]
    if not args.no_audio:
        targets.append(("mp3", {"bitrate": 128}))
    src = xml
    produced = {}
    for ext, opts in targets:
        dst = os.path.join(out, f"selfcheck.{ext}")
        try:
            rc, err, outs = mscore.convert(src, dst, **(opts or {}))
            if rc != 0 or not outs:
                record(False, f"导出 {ext}", (err or "无产物").splitlines()[0] if err else "无产物")
                continue
            ok = all(mscore.check_output(o)[0] for o in outs)
            record(ok, f"导出 {ext}", ", ".join(mscore.check_output(o)[1] for o in outs))
            produced[ext] = outs
        except Exception as e:                                # noqa: BLE001
            record(False, f"导出 {ext}", str(e))

    # 4. 回读元数据（证明内容真的进了谱子，而不是空壳）
    try:
        rc, so, se = mscore.run_musescore(
            exe, ["--score-meta", produced["mscz"][0]], timeout=120)
        meta = json.loads(so)["metadata"]
        checks = {
            "小节数": (meta.get("measures"), 2),
            "调号": (meta.get("keysig"), 1),
            "标题": (meta.get("title"), "自检曲"),
            "拍号": (meta.get("timesig"), "4/4"),
        }
        for name, (got, want) in checks.items():
            record(got == want, f"回读 {name}", f"{got!r}（期望 {want!r}）")
    except Exception as e:                                    # noqa: BLE001
        record(False, "回读元数据", str(e))

    # 5. PDF 体积下限：单页谱正常在 15KB 以上，过小多半是空谱
    try:
        pdf = produced["pdf"][0]
        record(os.path.getsize(pdf) > 12000, "PDF 体积合理", f"{os.path.getsize(pdf)} B")
    except Exception:                                         # noqa: BLE001
        record(False, "PDF 体积合理", "没有 PDF 产物")

    return summary()


def summary():
    print()
    bad = [r for r in RESULTS if not r[0]]
    print(f"合计 {len(RESULTS)} 项，通过 {len(RESULTS) - len(bad)}，失败 {len(bad)}")
    if bad:
        print("失败项：" + "；".join(n for _, n, _ in bad))
        return 1
    print("PASS — 全链路可用，可以直接开始写谱。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
