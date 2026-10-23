#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mscore.py — MuseScore 4 命令行封装（无头排版 / 导出 / 元数据 / 产物校验）。

为什么要有这一层（直接调 MuseScore4.exe 的坑，这里都处理了）：
  * 可执行文件位置不固定 —— 按 MSCORE_PATH → 常见安装路径 → PATH 依次查找。
  * MuseScore 往 stderr 打一行无害的 `failed open log file: ...LocalLow...`，
    还会有 Qt 警告；直接看 stderr 会误判为失败，这里过滤掉，只看退出码和产物。
  * `-o out.png` 实际生成 `out-1.png`（多页则 out-2.png …），路径要自己 glob。
  * 同样的路径写法在 PowerShell 里容易因为引号/空格出错，这里用 argv 列表传参。
  * 产物可能「命令成功但文件是 0 字节」，所以统一做 magic bytes 校验。

用法
----
    python mscore.py check                      # 打印 exe 路径和版本
    python mscore.py convert in.musicxml out.mscz
    python mscore.py convert in.mscz out.pdf --force
    python mscore.py convert in.mscz out.png --dpi 150
    python mscore.py convert in.mscz out.mp3 --bitrate 192
    python mscore.py convert in.mscz out.mid
    python mscore.py render in.mscz --dpi 130   # PNG 快捷方式，自动列出 out-1.png…
    python mscore.py meta in.mscz               # --score-meta 的 JSON
    python mscore.py elements in.mscz           # --score-elements 的 JSON（很大，建议 --out）
    python mscore.py media in.mscz --out m.json # --score-media：整份谱的媒体 JSON
    python mscore.py verify out.pdf out.mscz    # 校验 magic bytes 与大小

退出码：0 成功；1 失败（参数/找不到 exe/转换失败/产物异常）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

NOISE = (
    "failed open log file",
    "Qt: Could not",
    "QML",
    "qt.qpa",
    "Fontconfig",
)


def find_exe() -> str:
    """按 MSCORE_PATH -> 常见安装路径 -> PATH 的顺序找 MuseScore 可执行文件。"""
    for env in ("MSCORE_PATH", "MUSESCORE_PATH"):
        p = os.environ.get(env)
        if p and os.path.isfile(p):
            return p

    candidates = []
    if sys.platform.startswith("win"):
        for base in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if base:
                candidates.append(os.path.join(base, "MuseScore 4", "bin", "MuseScore4.exe"))
                candidates.append(os.path.join(base, "Programs", "MuseScore 4", "bin", "MuseScore4.exe"))
    elif sys.platform == "darwin":
        candidates.append("/Applications/MuseScore 4.app/Contents/MacOS/mscore")
    else:
        candidates += ["/usr/bin/musescore4", "/usr/bin/mscore", "/usr/local/bin/musescore4"]

    for c in candidates:
        if c and os.path.isfile(c):
            return c
    for name in ("mscore", "musescore", "MuseScore4", "musescore4"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        "找不到 MuseScore 可执行文件。请安装 MuseScore 4，"
        "或设置环境变量 MSCORE_PATH 指向 mscore/MuseScore4.exe。"
    )


def _clean_stderr(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    kept = [ln for ln in lines if not any(n.lower() in ln.lower() for n in NOISE)]
    return "\n".join(kept)


def run_musescore(exe: str, args, timeout=300):
    """跑一次 MuseScore CLI，返回 (returncode, stdout, 过滤后的 stderr)。

    注意只启动一次进程：MuseScore 冷启动就要几秒，重复跑会明显变慢。
    """
    proc = subprocess.run(
        [exe] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or ""), _clean_stderr(proc.stderr or "")


MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".mscz": (b"PK\x03\x04", b"PK\x05\x06"),
    ".mxl": (b"PK\x03\x04", b"PK\x05\x06"),
    ".mid": (b"MThd",),
    ".midi": (b"MThd",),
    ".mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    ".svg": (b"<?xml", b"<svg"),
}


def check_output(path: str):
    """产物存在 + 非空 + magic 对得上；返回 (ok, 描述)。"""
    if not os.path.isfile(path):
        return False, f"缺失 {path}"
    size = os.path.getsize(path)
    if size == 0:
        return False, f"0 字节 {path}"
    ext = os.path.splitext(path)[1].lower()
    expected = MAGIC.get(ext)
    if expected:
        with open(path, "rb") as f:
            head = f.read(16)
        if not any(head.startswith(m) for m in expected):
            return False, f"magic 不符 {path}（{ext} 开头是 {head[:8]!r}）"
    return True, f"{os.path.basename(path)} {size} B"


def _collect_outputs(dst: str):
    """MuseScore 对 png/svg 会生成 `name-1.png`；其他格式就是原路径。"""
    ext = os.path.splitext(dst)[1].lower()
    if ext in (".png", ".svg"):
        stem, suffix = os.path.splitext(dst)
        found = []
        i = 1
        while True:
            p = f"{stem}-{i}{suffix}"
            if not os.path.isfile(p):
                break
            found.append(p)
            i += 1
        if found:
            return found
    return [dst] if os.path.isfile(dst) else []


def convert(src, dst, dpi=None, bitrate=None, trim=None, force=False,
            page=None, style=None, timeout=300):
    exe = find_exe()
    args = []
    if force:
        args.append("-f")
    if dpi:
        args += ["-r", str(dpi)]
    if bitrate:
        args += ["-b", str(bitrate)]
    if trim is not None:
        args += ["-T", str(trim)]
    if page:
        args += ["--page", str(page)]
    if style:
        args += ["-S", style]
    args += ["-o", dst, src]
    rc, _out, err = run_musescore(exe, args, timeout=timeout)
    if rc != 0:
        return rc, err, []
    outs = _collect_outputs(dst)
    return rc, err, outs


# --------------------------------------------------------------------------- #
def cmd_check(_args):
    exe = find_exe()
    rc, out, err = run_musescore(exe, ["--version"], timeout=120)
    version = (out or err).strip()
    print(f"exe: {exe}")
    if rc == 0 and version:
        print(f"version: {version.splitlines()[0]}")
    else:
        print("version: (无法读取 --version，但 exe 存在)")
    print("提示: 转换时 stderr 里的 'failed open log file' 是沙箱/权限导致的无害警告。")
    return 0


def cmd_convert(args):
    if not os.path.isfile(args.src):
        print(f"ERROR: 源文件不存在: {args.src}", file=sys.stderr)
        return 1
    parent = os.path.dirname(os.path.abspath(args.dst))
    os.makedirs(parent, exist_ok=True)
    rc, err, outs = convert(
        args.src, args.dst, dpi=args.dpi, bitrate=args.bitrate, trim=args.trim,
        force=args.force, page=args.page, style=args.style, timeout=args.timeout,
    )
    if rc != 0:
        print(f"ERROR: MuseScore 退出码 {rc}", file=sys.stderr)
        if err:
            print(err, file=sys.stderr)
        return 1
    if not outs:
        print(f"ERROR: 命令成功但没有产物: {args.dst}", file=sys.stderr)
        return 1
    bad = 0
    for p in outs:
        ok, desc = check_output(p)
        print(("OK  " if ok else "BAD ") + desc)
        bad += 0 if ok else 1
    if err:
        print(f"(stderr 摘要) {err.splitlines()[0]}")
    return 0 if bad == 0 else 1


def cmd_render(args):
    stem = args.out or os.path.splitext(args.src)[0]
    dst = stem + ".png"
    args.dst = dst
    args.dpi = args.dpi or 130
    args.bitrate = None
    args.trim = args.trim
    args.page = None
    args.style = None
    args.force = False
    return cmd_convert(args)


def _dump_stdout_json(args, flag):
    """--score-meta / --score-elements / --score-media 都是把 JSON 打到 stdout。"""
    exe = find_exe()
    if not os.path.isfile(args.src):
        print(f"ERROR: 文件不存在: {args.src}", file=sys.stderr)
        return 1
    rc, out, err = run_musescore(exe, [flag, args.src], timeout=args.timeout)
    if rc != 0:
        print(f"ERROR: MuseScore 退出码 {rc}: {err}", file=sys.stderr)
        return 1
    text = (out or "").strip()
    if not text:
        print("ERROR: 没有拿到 JSON 输出", file=sys.stderr)
        if err:
            print(err, file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"OK  {args.out} {len(text)} chars")
    else:
        print(text)
    return 0


def cmd_meta(args):
    return _dump_stdout_json(args, "--score-meta")


def cmd_elements(args):
    return _dump_stdout_json(args, "--score-elements")


def cmd_media(args):
    return _dump_stdout_json(args, "--score-media")


def cmd_verify(args):
    bad = 0
    for p in args.files:
        ok, desc = check_output(p)
        print(("OK  " if ok else "BAD ") + desc)
        bad += 0 if ok else 1
    return 0 if bad == 0 else 1


def build_parser():
    ap = argparse.ArgumentParser(description="MuseScore 4 CLI 封装")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="打印 exe 路径与版本")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("convert", help="转换/导出到任意受支持格式")
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--dpi", type=int, help="PNG/SVG 分辨率，默认 300；论文插图常用 150-200")
    p.add_argument("--bitrate", type=int, help="MP3 码率 kbps，默认 128")
    p.add_argument("--trim", type=int, help="PNG/SVG 裁边像素")
    p.add_argument("--force", action="store_true", help="源文件有警告时强制导出")
    p.add_argument("--page", help='只导出指定页，如 "1" 或 "1-3"')
    p.add_argument("--style", help=".mss 样式文件")
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("render", help="PNG 快捷方式（自动列出 out-1.png …）")
    p.add_argument("src")
    p.add_argument("--out", help="输出前缀，默认与源文件同名")
    p.add_argument("--dpi", type=int, default=130)
    p.add_argument("--trim", type=int)
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(func=cmd_render)

    for name, func, hlp in (
        ("meta", cmd_meta, "--score-meta：标题/作曲/调号/拍号/页数/声部等 JSON"),
        ("elements", cmd_elements, "--score-elements：全谱元素 JSON（很大）"),
        ("media", cmd_media, "--score-media：整份谱的媒体 JSON（大）"),
    ):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("src")
        p.add_argument("--out", help="写入文件而不是打印")
        p.add_argument("--timeout", type=int, default=300)
        p.set_defaults(func=func)

    p = sub.add_parser("verify", help="校验产物（存在/非空/magic bytes）")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_verify)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("ERROR: MuseScore 超时（大谱/首次启动会慢，可调大 --timeout）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
