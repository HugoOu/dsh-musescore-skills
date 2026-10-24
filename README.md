<div align="center">

# 🎼 MuseScore Skills for DeepSeek Harness

**Compose, engrave and digitise sheet music from an AI agent — no GUI, no plugins, no cloud.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![MuseScore](https://img.shields.io/badge/MuseScore-4.x-1a7fbf.svg)](https://musescore.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#compatibility)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](#roadmap)

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

Two [Agent Skills](https://github.com/HugoOu/dsh-musescore-skills) for **DeepSeek Harness** that drive [MuseScore Studio 4](https://musescore.org) from the command line. The agent writes **MusicXML**, MuseScore engraves it headless, and you get a real, editable score — `.mscz`, PDF, PNG, MIDI or MP3.

This is not "AI-generated music images". It is a deterministic notation pipeline: the model owns the musical content, MuseScore owns the engraving.

## Demo

![A 12-bar piece composed and engraved by the skill](docs/images/demo-compose.png)

*A violin + piano piece composed and engraved end-to-end by `musescore-score`: MusicXML → MuseScore CLI → `.mscz` / PDF / PNG / MP3 / MIDI. Take a closer look at [the text](skills/musescore-score/SKILL.md) the agent follows.*

## What's inside

| Skill | What it does | Extra requirements |
|---|---|---|
| [`musescore-score`](skills/musescore-score/SKILL.md) | **Write music.** Describe a score in MusicXML (melody, chords, two staves, lyrics, ties, slurs, repeats, dynamics, tempo, system breaks) and export `.mscz` / PDF / PNG / MP3 / MIDI. Also handles transposition (at generation time), part extraction and metadata checks. | MuseScore 4, Python 3.10+ |
| [`scan-score-to-musescore`](skills/scan-score-to-musescore/SKILL.md) | **Digitise sheet music.** Scanned pages or bitmap PDFs → staff-line fitting → notehead detection → pitch mapping → human-in-the-loop rhythm verification → MusicXML → engraved score. Best for single-line melodies and lead sheets. | + numpy, Pillow, poppler |

The two compose: `scan-score-to-musescore` only produces MusicXML, then hands off to `musescore-score`'s `scripts/mscore.py` for engraving.

> **The scan half also has a dedicated repository:** [HugoOu/scan-score-to-musescore](https://github.com/HugoOu/scan-score-to-musescore). It carries the long-form walkthrough of the geometry, the public-domain *Ode to Joy* example and the `--annotate` debug overlay — read the pipeline there, install from this bundle. The toolkit is the same; here `mxml_ext.py` reuses `mxml.py` from `musescore-score` instead of shipping its own copy.

## How it works

```
        ┌─────────────────────────┐
 scan → │ scan-score-to-musescore │ → score.json → MusicXML ─┐
        └─────────────────────────┘                           │
                                                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │  mscore.py  ──▶  MuseScore 4 CLI (headless)              │
        │                 └─▶ .mscz · PDF · PNG · MP3 · MIDI       │
        └──────────────────────────────────────────────────────────┘
                                                              ▲
        ┌─────────────────────────┐                           │
 idea → │    musescore-score      │ → MusicXML ───────────────┘
        └─────────────────────────┘
```

Scanning is only half the job — the pipeline **always renders a PNG and looks at it** before declaring success, because MuseScore silently drops content from invalid MusicXML instead of failing.

![Synthetic scan input](docs/images/scan-input.png)
![Engraved output](docs/images/scan-output.png)

*Left: a synthetic "scan" used by the digitising workflow. Right: the engraved, editable result. (Sample above is generated from the repo's self-made `example_score.json` — no third-party sheet music is shipped.)*

## Quick start

```powershell
git clone https://github.com/HugoOu/dsh-musescore-skills.git
Copy-Item .\dsh-musescore-skills\skills\* "$env:USERPROFILE\.dsh\skills\" -Recurse
```

`DSH_HOME` is not `~/.dsh`? Copy into `$env:DSH_HOME\skills\` instead. Skills are plain text + Python, nothing to `pip install` for `musescore-score`.

Verify the toolchain in ~25 seconds:

```powershell
python "$env:USERPROFILE\.dsh\skills\musescore-score\scripts\selfcheck.py" --out .\ms-selfcheck
# 12/12 PASS — MuseScore 4.7.5 detected, MusicXML → mscz/pdf/png/mid/mp3 all valid
```

## Usage

### Compose a score

Just ask. The skill's description is the routing signal:

> Write an 8-bar piano piece in C major, melody in the right hand, broken chords in the left, export PDF and MP3.

Or drive it explicitly with the builder API:

```python
import sys; sys.path.insert(0, r"~/.dsh/skills/musescore-score/scripts")
from mxml import Score

s = Score(title="Morning Mist", composer="you", key=1, time=(3, 4), tempo=66)
s.group_parts("bracket")
vln = s.add_part("Violin", program=41)
pno = s.add_part("Piano", program=1, staves=2)

m = vln.add_measure()
notes = m.line("D5:2 B4:1")          # pitch:duration (in quarter notes)
notes[0].slur = "start"
pno.add_measure().line("G2:1 D3:1 B3:1", staff=2, voice=2)

s.write("morning-mist.musicxml")
```

```powershell
python scripts/mscore.py convert morning-mist.musicxml morning-mist.mscz
python scripts/mscore.py convert morning-mist.mscz morning-mist.pdf
python scripts/mscore.py render morning-mist.mscz --dpi 150     # morning-mist-1.png
python scripts/mscore.py meta morning-mist.mscz                 # verify what landed
```

### Digitise a scan

```powershell
python scripts/pdf_scan.py score.pdf pages/                 # pages + staff systems
python scripts/pitchmap.py pages --clef treble --key -1     # notehead candidates
python scripts/probe.py pages/page-1.png 240 820 420 950 --ascii   # verify line/space
python scripts/score_from_json.py score.json score.musicxml # hand-checked JSON → XML
python scripts/verify.py score.musicxml out --pdf --dpi 130 # engrave + render + meta
```

The scan skill is **semi-automatic by design**: geometry is scripted, rhythm and phrasing are confirmed by looking at the image. It tells you when a scan is too poor to automate instead of guessing.

### Use them together

The split is at MusicXML, so the hand-off is just a file:

| Starting point | Route |
|---|---|
| An idea or a text brief | `musescore-score` → MusicXML → `mscore.py convert` / `render` |
| A scan or bitmap PDF | `scan-score-to-musescore` → `score.json` → MusicXML → `verify.py` (which calls `mscore.py`) |
| A hand-checked `score.json` | `score_from_json.py` → `mscore.py` |
| An existing `.musicxml` | `mscore.py convert` / `render` / `meta` |

Both skills are installed together by the quick start, so no extra wiring: the scan skill finds `mxml.py` and `mscore.py` in the sibling `musescore-score` skill. If you install only the scan skill, keep `musescore-score` next to it — its import path assumes `~/.dsh/skills/musescore-score/scripts` (for `verify.py`, override with `--mscore`).

## Repository layout

```
dsh-musescore-skills/
├── README.md                     ← you are here
├── README.zh-CN.md               ← 简体中文
├── LICENSE                       ← MIT
├── docs/
│   ├── legal.md                  ← copyright / trademark / dependencies
│   └── images/                   ← demo screenshots
└── skills/
    ├── musescore-score/
    │   ├── SKILL.md              ← workflow, acceptance criteria, gotchas
    │   ├── scripts/  mxml.py · mscore.py · selfcheck.py
    │   ├── references/  musicxml-cheatsheet · musescore-cli · notation-recipes
    │   └── assets/examples/  twinkle.py · satb.py
    └── scan-score-to-musescore/
        ├── SKILL.md
        ├── scripts/  pdf_scan · pitchmap · probe · score_from_json · verify · mxml_ext
        └── references/notation-mapping.md · assets/example_score.json
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `MSCORE_PATH` | auto-detected | Path to `MuseScore4.exe` / `mscore` when installed in a non-standard location |
| `DSH_HOME` | `~/.dsh` | Where DSH looks for `skills/` |

Everything runs locally. No API keys, no telemetry, no network calls.

## Compatibility

| Component | Tested | Notes |
|---|---|---|
| MuseScore Studio | **4.7.5** (Windows 11) | The CLI surface (`-o`, `-r`, `--score-meta`, `--page`) is stable across 4.x; older 4.0–4.3 may differ |
| Python | 3.12 / 3.14 | `musescore-score` is stdlib-only |
| OS | Windows 11 | `mscore.py` has macOS/Linux discovery paths but is **untested** there |
| poppler | TeX Live build | Only needed by the scan skill |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `failed open log file …LocalLow` on stderr | Harmless: MuseScore cannot write its log. Export still succeeds. |
| Empty staves after import | A chord was written as one `<note>` with several `<pitch>` — it must be several `<note>`s, each after the first carrying `<chord/>` |
| Parts not bracketed / barlines misaligned | Missing `<part-group>` in `<part-list>` (the API call is `Score.group_parts()`) |
| `out.png` not found | MuseScore names image exports `out-1.png`, `out-2.png`, … |
| Thick black blobs instead of chords | Low-DPI rendering of adjacent thirds. Re-render at 300 dpi before "fixing" anything |
| Can't launch a plugin | MuseScore 4 removed `-p`; live GUI editing is out of scope |

More in [`references/musescore-cli.md`](skills/musescore-score/references/musescore-cli.md) and [`references/musicxml-cheatsheet.md`](skills/musescore-score/references/musicxml-cheatsheet.md).

## Why a Skill and not a prompt?

Measured on the same task (8-bar piano piece, export PDF + MP3): **6 min 11 s with the skill vs 12 min 30 s without**, and the unaided run had to hand-write a 7.7 KB MusicXML generator from scratch. Routing was validated with a 20-query trigger eval (3 runs each) plus real-session positive/negative tests.

The skill encodes what actually breaks: silent content loss, chord encoding, `<backup>` accounting, `part-group`, low-DPI misreading. Those are not things you re-derive every time.

## Legal

This repository contains **tooling only** — no sheet music, scans or audio of third-party works. Examples are self-generated or public-domain (e.g. *Twinkle, Twinkle*).

You are responsible for the rights of whatever you process: transcribing or distributing copyrighted music requires a licence, and "personal study" does not cover publishing. These tools do not break DRM or scrape streaming/catalogue sites. MuseScore is an independent GPL-3.0 program; this project only invokes its CLI and is **not affiliated with Muse Group**.

See [docs/legal.md](docs/legal.md) for the full analysis.

## Contributing

Issues and PRs welcome — especially: MuseScore 4.x version quirks, macOS/Linux verification, and better OMR for chordal/dense scores. Please keep examples self-made or public domain.

## License

[MIT](LICENSE) © 2026 Yuhao Ou

## Acknowledgements

- [MuseScore Studio](https://musescore.org) — engraving engine and CLI
- [MusicXML](https://www.w3.org/community/musicxml/) — the interchange format that makes this possible
- [DeepSeek Harness](https://github.com/deepseek-ai) — the agent runtime these skills plug into
