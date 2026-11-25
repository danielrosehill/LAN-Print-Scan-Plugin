#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Several different tape labels as ONE job on a P-touch bridge (POST /print-batch), so the ~25 mm leader is paid once.

  tape_batch.py LABEL [LABEL ...] [--preview out.png] [--max-mm 45] [--bridge URL] [--tape 24]

LABEL is "text" or "text::copies"; "\\n" breaks lines, the first line is the heading (bold), the rest are smaller. One short line is
set at a moderate size instead of filling the tape. --preview renders and prints the lengths only. The bridge URL comes from
Every print is recorded first in tape-jobs/last.json of the plugin data dir, so a job cut short (tape ran out, jam) can continue:

  tape_batch.py --resume-from "USB-C" [--copy 2] [--preview out.png]   # that label (and copy of it) onwards; one match required
  tape_batch.py --list                                                 # the recorded job, with label numbers
  tape_batch.py --record-only LABEL ...                                # record a job printed some other way, print nothing

--resume-from takes a label number from --list, or part of its text. The bridge cannot tell how many labels came out, so a person
says which label is the first one to print again. --bridge, $PTOUCH_BRIDGE or "ptouch_bridge" in the plugin data dir's hub.json. The loaded tape must match --tape (default 24).
"""
import argparse, base64, glob, io, json, os, sys, time, urllib.request
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


def state_file():
    return Path(os.environ.get("CLAUDE_USER_DATA") or Path.home() / ".claude-user-data") / "lan-print-scan/tape-jobs/last.json"


def save(labels, tape, status):
    p = state_file(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "status": status, "tapeMm": tape, "labels": labels}, indent=1))


def resume(key, copy):
    if not state_file().exists(): sys.exit("no recorded job to resume")
    labels = json.loads(state_file().read_text())["labels"]
    flat = lambda s: " ".join(s.replace("\\n", " ").split()).lower()
    hits = [int(key) - 1] if key.isdigit() and 1 <= int(key) <= len(labels) else [i for i, (t, _) in enumerate(labels) if flat(key) in flat(t)]
    if len(hits) != 1: sys.exit(f"{len(hits)} labels match {key!r}; use its number from --list")
    t, n = labels[hits[0]]
    if not 1 <= copy <= n: sys.exit(f"{t!r} has {n} copies")
    return [[t, n - copy + 1], *labels[hits[0] + 1:]]


def parse(l):
    t, sep, n = l.rpartition("::")
    return [t, int(n)] if sep and n.isdigit() else [l, 1]


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
    a = argparse.ArgumentParser(); a.add_argument("labels", nargs="*"); a.add_argument("--preview"); a.add_argument("--max-mm", type=float, default=45)
    a.add_argument("--bridge"); a.add_argument("--tape", type=int, default=24)
    a.add_argument("--resume-from"); a.add_argument("--copy", type=int, default=1); a.add_argument("--list", action="store_true")
    a.add_argument("--record-only", action="store_true"); a = a.parse_args()
    if a.list:
        s = json.loads(state_file().read_text()) if state_file().exists() else sys.exit("no recorded job")
        s["labels"] = [{"n": i + 1, "text": t, "copies": n} for i, (t, n) in enumerate(s["labels"])]; print(json.dumps(s, indent=1)); return
    if bool(a.labels) == bool(a.resume_from): sys.exit("give labels, or --resume-from")
    labels = resume(a.resume_from, a.copy) if a.resume_from else [parse(l) for l in a.labels]
    if a.record_only:
        save(labels, a.tape, "recorded"); print(json.dumps({"recorded": len(labels)})); return
    url = bridge_url(a.bridge); hp = call(url + "/health")
    if not hp.get("ok"): sys.exit(f"printer not ready: {hp}")
    if hp.get("tapeMm") != a.tape: sys.exit(f"loaded tape is {hp.get('tapeMm')} mm, expected {a.tape}: ask, then pass --tape")
    jobs = []
    for t, n in labels:
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
        save(labels, a.tape, "sent")  # before sending: a job that dies half way must be resumable
        out["result"] = call(url + "/print-batch", {"labels": [{"imageDataUrl": png(i), "copies": n} for _, n, i in jobs]})
        if not out["result"].get("ok", True): sys.exit(json.dumps(out))
        save(labels, a.tape, "bridge reported success")  # not proof: check the tape
    print(json.dumps(out))


main()
