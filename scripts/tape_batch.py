#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Several different tape labels as ONE job on a P-touch bridge (POST /print-batch), so the ~25 mm leader is paid once.

  tape_batch.py LABEL [LABEL ...] [--preview out.png] [--max-mm 45] [--bridge URL] [--tape 24]

LABEL is "text" or "text::copies"; "\\n" breaks lines, the first line is the heading (bold), the rest are smaller. One short line is
set at a moderate size instead of filling the tape. --preview renders and prints the lengths only. The bridge URL comes from
--bridge, $PTOUCH_BRIDGE or "ptouch_bridge" in the plugin data dir's hub.json. The loaded tape must match --tape (default 24).
"""
import argparse, base64, glob, io, json, os, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DPI = 180


def font(size, bold=True):
    names = ["IBMPlexSans-Bold", "DejaVuSans-Bold"] if bold else ["IBMPlexSans-Medium", "IBMPlexSans-Regular", "DejaVuSans"]
    for n in names:
        hit = glob.glob(f"/usr/share/fonts/**/{n}.?tf", recursive=True)
        if hit: return ImageFont.truetype(hit[0], size)
    return ImageFont.load_default(size)


def bridge_url(arg):
    if arg or os.environ.get("PTOUCH_BRIDGE"): return (arg or os.environ["PTOUCH_BRIDGE"]).rstrip("/")
    for d in (os.environ.get("CLAUDE_USER_DATA"), str(Path.home() / ".claude-user-data")):
        p = Path(d or "") / "lan-print-scan/hub.json"
        if d and p.exists():
            u = json.loads(p.read_text()).get("ptouch_bridge")
            if u: return u.rstrip("/")
    sys.exit("no bridge: pass --bridge, set $PTOUCH_BRIDGE or add ptouch_bridge to hub.json")


def call(url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"content-type": "application/json"})
    with urllib.request.urlopen(r, timeout=300 if body else 15) as f: return json.load(f)


def render(text, h, max_mm):
    lines = [x.strip() for x in text.replace("\\n", "\n").split("\n") if x.strip()]
    if not lines: sys.exit("empty label")
    ratios, pad = [1.0] + [0.78] * (len(lines) - 1), max(6, h // 16)
    max_w = int(max_mm / 25.4 * DPI) - 4 * pad
    size = int(h * (0.48 if len(lines) == 1 else 0.60))
    while size > 14:
        fs = [font(int(size * r), i == 0) for i, r in enumerate(ratios)]
        boxes = [f.getbbox(x) for f, x in zip(fs, lines)]
        gap = max(4, int(size * 0.16))
        w, th = max(b[2] - b[0] for b in boxes), sum(b[3] - b[1] for b in boxes) + gap * (len(lines) - 1)
        if th <= h - 2 * pad and w <= max_w: break
        size -= 1
    img = Image.new("L", (w + 4 * pad, h), 255); d = ImageDraw.Draw(img); y = (h - th) // 2
    for x, f, b in zip(lines, fs, boxes):
        d.text(((img.width - (b[2] - b[0])) // 2 - b[0], y - b[1]), x, font=f, fill=0); y += b[3] - b[1] + gap
    return img.point(lambda v: 255 if v > 127 else 0)


def main():
    a = argparse.ArgumentParser(); a.add_argument("labels", nargs="+"); a.add_argument("--preview"); a.add_argument("--max-mm", type=float, default=45)
    a.add_argument("--bridge"); a.add_argument("--tape", type=int, default=24); a = a.parse_args()
    url = bridge_url(a.bridge); hp = call(url + "/health")
    if not hp.get("ok"): sys.exit(f"printer not ready: {hp}")
    if hp.get("tapeMm") != a.tape: sys.exit(f"loaded tape is {hp.get('tapeMm')} mm, expected {a.tape}: ask, then pass --tape")
    jobs = []
    for l in a.labels:
        t, sep, n = l.rpartition("::")
        t, n = (t, int(n)) if sep and n.isdigit() else (l, 1)
        jobs.append((t, n, render(t, int(hp["maxPx"]), a.max_mm)))
    out = {"tapeMm": hp["tapeMm"], "labels": [{"text": t, "copies": n, "mm": round(i.width / DPI * 25.4, 1)} for t, n, i in jobs]}
    if a.preview:
        s = Image.new("L", (max(i.width for *_, i in jobs), sum(i.height + 8 for *_, i in jobs)), 160); y = 0
        for *_, i in jobs: s.paste(i, (0, y)); y += i.height + 8
        s.save(a.preview)
    else:
        if not hp.get("batchPages"): print("warning: this bridge has no batchPages, one leader per label", file=sys.stderr)
        def png(i):
            b = io.BytesIO(); i.save(b, "PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
        out["result"] = call(url + "/print-batch", {"labels": [{"imageDataUrl": png(i), "copies": n} for _, n, i in jobs]})
    print(json.dumps(out))


main()
