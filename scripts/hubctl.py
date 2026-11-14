#!/usr/bin/env python3
"""hubctl: client for a LAN Print Hub (print queue) and a LAN Network Scanner (eSCL scan service).

Stdlib only. Every command prints JSON.

  hubctl.py targets                                   printers the hub knows, with live health
  hubctl.py label  [-p TARGET] -t "L1\\nL2" [-i ICON] [-n N] [--png FILE] [--preview OUT.png] [--opt k=v ...]
  hubctl.py print  FILE [-p TARGET] [-n N] [--sides one|long|short] [--mono] [--pages 1-3] [--media A4] [--fit]
  hubctl.py jobs   [-l 20] [-p TARGET]                  job history;  hubctl.py job ID
  hubctl.py scan   [--format pdf|png|jpeg] [--resolution 300] [--color color|gray|bw] [--name N] [-o FILE]
  hubctl.py scans                                     list scans on the scanner service

Endpoints: $PRINT_HUB / $NETWORK_SCANNER, else hub.json in the plugin data dir
({"print_hub": "http://host:9190", "network_scanner": "http://host:9191"}).
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from printctl import VAULT  # noqa: E402  (plugin data dir)


def cfg(key, env):
    if os.environ.get(env):
        return os.environ[env].rstrip("/")
    try:
        v = json.loads((VAULT / "hub.json").read_text()).get(key)
    except FileNotFoundError:
        v = None
    if not v:
        sys.exit(json.dumps({"ok": False, "error": f"set ${env} or '{key}' in {VAULT / 'hub.json'}"}))
    return v.rstrip("/")


def out(obj, code=0):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    sys.exit(code)


def call(url, data=None, headers=None, method=None, timeout=300, raw=False):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return (body, dict(r.headers)) if raw else json.loads(body or b"{}")
    except urllib.error.HTTPError as e:
        out({"ok": False, "status": e.code, "error": e.read().decode(errors="replace")[:500], "url": url}, 1)
    except urllib.error.URLError as e:
        out({"ok": False, "error": f"unreachable: {e.reason}", "url": url}, 1)


def jpost(url, body, **k):
    return call(url, json.dumps(body).encode(), {"Content-Type": "application/json"}, **k)


def settle(job):
    """Hub job -> exit code: 0 done, 1 failed, 0 still queued (reported as such)."""
    out({"ok": job.get("state") == "done", **job}, 1 if job.get("state") == "failed" else 0)


def cmd_targets(a):
    out(call(cfg("print_hub", "PRINT_HUB") + "/targets"))


def cmd_label(a):
    hub = cfg("print_hub", "PRINT_HUB")
    body = {"text": a.text, "copies": a.copies}
    if a.printer:
        body["target"] = a.printer
    if a.icon:
        body["icon"] = a.icon
    if a.png:
        body["png"] = base64.b64encode(Path(a.png).read_bytes()).decode()
    for kv in a.opt or []:
        k, v = kv.split("=", 1)
        try:
            body[k] = json.loads(v)  # numbers, true/false, lists
        except ValueError:
            body[k] = v
    if a.preview:
        png, hdr = call(hub + "/preview", json.dumps(body).encode(), {"Content-Type": "application/json"}, raw=True)
        Path(a.preview).write_bytes(png)
        out({"ok": True, "preview": a.preview, "target": hdr.get("X-Target") or hdr.get("x-target"),
             "size_px": hdr.get("X-Size-Px") or hdr.get("x-size-px")})
    settle(jpost(hub + "/jobs?wait=true", body))


def multipart(fields: dict, file_field: str, path: Path):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        if v is None or v is False:
            continue
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n".encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={b}"}


def cmd_print(a):
    p = Path(a.file).expanduser()
    if not p.is_file():
        out({"ok": False, "error": f"no such file: {p}"}, 1)
    data, hdr = multipart({"target": a.printer, "copies": a.copies, "sides": a.sides, "mono": "true" if a.mono else None,
                           "pages": a.pages, "media": a.media, "fit": "true" if a.fit else None}, "file", p)
    settle(call(cfg("print_hub", "PRINT_HUB") + "/jobs?wait=true", data, hdr))


def cmd_jobs(a):
    q = {"limit": a.limit}
    if a.printer:
        q["target"] = a.printer
    out(call(cfg("print_hub", "PRINT_HUB") + "/jobs?" + urllib.parse.urlencode(q)))


def cmd_job(a):
    out(call(cfg("print_hub", "PRINT_HUB") + "/jobs/" + a.id))


def cmd_scan(a):
    sc = cfg("network_scanner", "NETWORK_SCANNER")
    body = {"format": a.format, "resolution": a.resolution, "color": a.color}
    if a.name:
        body["name"] = a.name
    res = jpost(sc + "/scan", body, timeout=180)
    if a.output and res.get("url"):
        blob, _ = call(sc + res["url"], raw=True)
        Path(a.output).expanduser().write_bytes(blob)
        res["saved"] = str(Path(a.output).expanduser())
        if a.delete:
            call(sc + res["url"], method="DELETE")
            res["deleted_on_server"] = True
    out(res)


def cmd_scans(a):
    out(call(cfg("network_scanner", "NETWORK_SCANNER") + "/scans"))


def main():
    ap = argparse.ArgumentParser(prog="hubctl")
    sub = ap.add_subparsers(required=True)
    sub.add_parser("targets").set_defaults(fn=cmd_targets)

    s = sub.add_parser("label", help="print a label (text/icon rendered on the hub, or a PNG)")
    s.add_argument("-p", "--printer", "--target", dest="printer", help="target id or alias (default: hub's default label printer)")
    s.add_argument("-t", "--text", default="")
    s.add_argument("-i", "--icon")
    s.add_argument("--png")
    s.add_argument("-n", "--copies", type=int, default=1)
    s.add_argument("--preview", metavar="OUT.png", help="render only, save the PNG, print nothing")
    s.add_argument("--opt", action="append", metavar="k=v", help="extra job field, e.g. layout=left margin_mm=1.5 invert=true")
    s.set_defaults(fn=cmd_label)

    s = sub.add_parser("print", help="print a document through the hub")
    s.add_argument("file")
    s.add_argument("-p", "--printer", "--target", dest="printer")
    s.add_argument("-n", "--copies", type=int, default=1)
    s.add_argument("--sides", choices=["one", "long", "short"])
    s.add_argument("--mono", action="store_true")
    s.add_argument("--pages")
    s.add_argument("--media")
    s.add_argument("--fit", action="store_true")
    s.set_defaults(fn=cmd_print)

    s = sub.add_parser("jobs")
    s.add_argument("-l", "--limit", type=int, default=20)
    s.add_argument("-p", "--printer", "--target", dest="printer")
    s.set_defaults(fn=cmd_jobs)
    s = sub.add_parser("job")
    s.add_argument("id")
    s.set_defaults(fn=cmd_job)

    s = sub.add_parser("scan", help="scan one flatbed page on the network scanner")
    s.add_argument("--format", choices=["pdf", "png", "jpeg"], default="pdf")
    s.add_argument("--resolution", type=int, choices=[150, 300, 600], default=300)
    s.add_argument("--color", choices=["color", "gray", "bw"], default="color")
    s.add_argument("--name")
    s.add_argument("-o", "--output", help="download the scan to this path")
    s.add_argument("--delete", action="store_true", help="with -o: delete the server copy after download")
    s.set_defaults(fn=cmd_scan)
    sub.add_parser("scans").set_defaults(fn=cmd_scans)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
