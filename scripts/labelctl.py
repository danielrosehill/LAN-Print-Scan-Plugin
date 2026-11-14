#!/usr/bin/env -S uv run -q --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10", "cairosvg>=2.7"]
# ///
"""labelctl: print a label on any registered label printer, chosen by --target.

Label printers are registry entries (printers.json, same file printctl.py uses) with
kind "label" and a "driver":

  niimblue       NIIMBOT via a niimblue-node REST bridge. Delegated to the niimbot-labels
                 plugin's niimlabel.py (registry field "client"), which owns rendering,
                 media sizes and print-position calibration.
  ptouch-bridge  Brother P-touch via a ptouch-print HTTP bridge (GET /health,
                 POST /print {imageDataUrl, copies}). Rendered here: a landscape PNG whose
                 height is the tape's printable width (the bridge reports maxPx).

Commands (all print JSON):
  labelctl.py targets                       label printers in the registry, with bridge health
  labelctl.py print -p ID -t "Text" [-i ICON] [-n N] [--dry-run -o out.png]
  labelctl.py print -p ID --png FILE        print an existing image

Registry entry fields used: id, kind=label, driver, bridge, client (niimblue only),
default (true on the one to use without -p).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from printctl import REGISTRY  # noqa: E402  (stdlib-only, safe to import)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/ibm-plex/IBMPlexSans-Bold.ttf",
    "/usr/share/fonts/opentype/ibm-plex/IBMPlexSans-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
UA = {"User-Agent": "labelctl/0.1"}


def out(obj, code=0):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    sys.exit(code)


def labels() -> list[dict]:
    try:
        reg = json.loads(REGISTRY.read_text())
    except FileNotFoundError:
        out({"ok": False, "error": f"no registry at {REGISTRY}"}, 1)
    return [p for p in reg.get("printers", []) if p.get("kind") == "label"]


def resolve(target: str | None) -> dict:
    ps = labels()
    if target:
        for p in ps:
            if target in (p["id"], p.get("name")):
                return p
        out({"ok": False, "error": f"unknown label target {target}", "targets": [p["id"] for p in ps]}, 1)
    dflt = [p for p in ps if p.get("default")] or ps[:1]
    if not dflt:
        out({"ok": False, "error": "no label printers registered"}, 1)
    return dflt[0]


def http(url, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return {"ok": False, "status": e.code, **json.loads(e.read())}
        except Exception:  # noqa: BLE001
            return {"ok": False, "status": e.code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def health(p: dict) -> dict:
    if p.get("driver") == "ptouch-bridge":
        return http(p["bridge"].rstrip("/") + "/health", timeout=8)
    if p.get("driver") == "niimblue":
        r = subprocess.run(["uv", "run", "-q", "--script", p["client"], "status"],
                           capture_output=True, text=True, timeout=40,
                           env={**os.environ, "NIIMBOT_BRIDGE": p["bridge"]})
        try:
            return json.loads(r.stdout)
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": (r.stderr or r.stdout).strip()[-300:]}
    return {"ok": False, "error": f"unknown driver {p.get('driver')}"}


# ---------- P-touch rendering ----------

def font_path():
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    sys.exit("no bold font found")


def icon_img(icon: str, size: int):
    from PIL import Image
    import cairosvg
    if ":" not in icon:
        icon = "material-symbols:" + icon
    prefix, name = icon.split(":", 1)
    svg = urllib.request.urlopen(urllib.request.Request(
        f"https://api.iconify.design/{prefix}/{name}.svg?height={size}", headers=UA), timeout=15).read()
    png = cairosvg.svg2png(bytestring=svg, output_width=size, output_height=size)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("L")


def render_ptouch(text: str, icon: str | None, h: int):
    """Landscape label: height = printable tape width in px, length grows with the text."""
    from PIL import Image, ImageDraw, ImageFont
    lines = [ln for ln in text.replace("\\n", "\n").split("\n") if ln.strip()]
    pad = max(2, h // 16)
    inner = h - 2 * pad
    fp = font_path()
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    gap_ratio = 0.12
    # largest size whose stacked lines fit the tape height
    size = inner
    while size > 6:
        f = ImageFont.truetype(fp, size)
        hs = [tmp.textbbox((0, 0), ln, font=f) for ln in lines]
        tot = sum(b[3] - b[1] for b in hs) + int(size * gap_ratio) * (len(lines) - 1)
        if tot <= inner:
            break
        size -= 1
    f = ImageFont.truetype(fp, size)
    boxes = [tmp.textbbox((0, 0), ln, font=f) for ln in lines]
    tw = max((b[2] - b[0]) for b in boxes) if lines else 0
    isz = inner if icon else 0
    igap = pad * 2 if icon and lines else 0
    w = pad + isz + igap + tw + pad
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    if icon:
        img.paste(icon_img(icon, isz), (pad, pad))
    tot = sum(b[3] - b[1] for b in boxes) + int(size * gap_ratio) * (len(lines) - 1)
    y = pad + (inner - tot) // 2
    x0 = pad + isz + igap
    for ln, b in zip(lines, boxes):
        d.text((x0 + (tw - (b[2] - b[0])) // 2 - b[0], y - b[1]), ln, font=f, fill=0)
        y += (b[3] - b[1]) + int(size * gap_ratio)
    return img.point(lambda v: 0 if v < 128 else 255)


def cmd_targets(a):
    res = []
    for p in labels():
        res.append({"id": p["id"], "name": p.get("name"), "driver": p.get("driver"),
                    "bridge": p.get("bridge"), "default": bool(p.get("default")),
                    "location": p.get("description"), "health": health(p)})
    out({"ok": True, "registry": str(REGISTRY), "targets": res})


def cmd_print(a):
    p = resolve(a.printer)
    drv = p.get("driver")
    if drv == "niimblue":
        if a.png:
            args = ["print-png", a.png]
        else:
            args = ["render" if a.dry_run else "print", "-t", a.text]
            if a.icon:
                args += ["-i", a.icon]
            args += a.extra or []
            if a.dry_run:
                args += ["-o", a.output or "/tmp/label-preview.png"]
        if not a.dry_run:
            args += ["-n", str(a.copies)]
        r = subprocess.run(["uv", "run", "-q", "--script", p["client"], *args],
                           capture_output=True, text=True, timeout=240,
                           env={**os.environ, "NIIMBOT_BRIDGE": p["bridge"]})
        try:
            res = json.loads(r.stdout)
        except Exception:  # noqa: BLE001
            res = {"ok": False, "error": (r.stderr or r.stdout).strip()[-500:]}
        out({"target": p["id"], "driver": drv, **res}, 0 if r.returncode == 0 else 1)
    if drv == "ptouch-bridge":
        h = health(p)
        max_px = h.get("maxPx") or a.height
        if not max_px:
            out({"ok": False, "target": p["id"], "error": "bridge gave no tape height", "health": h}, 1)
        if a.png:
            from PIL import Image
            img = Image.open(a.png).convert("L")
        else:
            img = render_ptouch(a.text, a.icon, int(max_px))
        if a.dry_run:
            path = a.output or "/tmp/label-preview.png"
            img.save(path)
            out({"ok": True, "dry_run": True, "target": p["id"], "preview": path,
                 "size_px": list(img.size), "tapeMm": h.get("tapeMm")})
        buf = io.BytesIO()
        img.save(buf, "PNG")
        url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        res = http(p["bridge"].rstrip("/") + "/print", {"imageDataUrl": url, "copies": a.copies}, timeout=180)
        out({"target": p["id"], "driver": drv, **res}, 0 if res.get("ok") else 1)
    out({"ok": False, "error": f"unknown driver {drv} on {p['id']}"}, 1)


def main():
    ap = argparse.ArgumentParser(prog="labelctl")
    sub = ap.add_subparsers(required=True)
    s = sub.add_parser("targets", help="registered label printers + bridge health")
    s.set_defaults(fn=cmd_targets)
    s = sub.add_parser("print")
    s.add_argument("-p", "--printer", "--target", dest="printer", help="registry id (default: the one marked default)")
    s.add_argument("-t", "--text", default="")
    s.add_argument("-i", "--icon", help="Iconify id; bare name = material-symbols")
    s.add_argument("--png", help="print an existing image instead")
    s.add_argument("-n", "--copies", type=int, default=1)
    s.add_argument("--height", type=int, help="P-touch: px height if the bridge can't report it")
    s.add_argument("--dry-run", action="store_true", help="render a preview, print nothing")
    s.add_argument("-o", "--output", help="preview path for --dry-run")
    s.add_argument("extra", nargs="*", help="NIIMBOT only: extra niimlabel.py flags after --, e.g. -- --margin 1")
    s.set_defaults(fn=cmd_print)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
