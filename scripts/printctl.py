#!/usr/bin/env python3
"""printctl — discover, profile, install and print to ordinary (document) printers.

Everything prints JSON to stdout so a skill can read it back. Shells out to the
CUPS client tools (lpstat, lpadmin, lp, ipptool) and avahi-browse; no Python
dependencies beyond the standard library.

Registry: machine-local, printers.json in the data dir (see README).
It holds LAN addresses that are true on one network only, so it is never committed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path



def data_dir() -> Path:
    """Env override, then the user-data root if there is one, then XDG."""
    if os.environ.get("LAN_PRINT_SCAN_DIR"):
        return Path(os.environ["LAN_PRINT_SCAN_DIR"]).expanduser()
    if os.environ.get("CLAUDE_USER_DATA"):
        return Path(os.environ["CLAUDE_USER_DATA"]).expanduser() / "lan-print-scan"
    root = Path.home() / ".claude-user-data"
    if root.is_dir():
        return root / "lan-print-scan"
    xdg = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return xdg / "claude-plugins" / "lan-print-scan"


VAULT = data_dir()
REGISTRY = VAULT / "printers.json"
MAX_COPIES = int(os.environ.get("LAN_PRINT_SCAN_MAX_COPIES", "20"))
# HP reports marker-low-levels=1, i.e. it only warns when empty. Warn earlier.
LOW_INK = int(os.environ.get("LAN_PRINT_SCAN_LOW_INK", "15"))

# mDNS service types worth asking about. _uscan(s) = eSCL scanner, _printer = LPD.
SERVICES = ["_ipp._tcp", "_ipps._tcp", "_pdl-datastream._tcp", "_printer._tcp", "_uscan._tcp", "_uscans._tcp"]

# USB vendor ids for printer makers, for the lsusb probe.
USB_VENDORS = {"03f0": "HP", "04b8": "Epson", "04f9": "Brother", "04a9": "Canon",
               "04e8": "Samsung", "043d": "Lexmark", "0924": "Xerox", "0482": "Kyocera"}

# Models that are label printers: discovered, but belong to the label-printer plugin.
LABEL_MODEL = re.compile(r"\b(QL-\d|PT-|P-touch|TD-\d|Zebra|DYMO|LabelWriter)", re.I)


def out(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def die(msg: str, code: int = 1) -> None:
    out({"ok": False, "error": msg})
    sys.exit(code)


def run(cmd: list[str], timeout: int = 20, check: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ, LC_ALL="C")
    env.pop("LD_PRELOAD", None)  # NoMachine's preload spams stderr on every child
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and p.returncode != 0:
        die(f"{' '.join(cmd)} failed ({p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    return p


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- registry

def load_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {"version": 1, "printers": []}


def save_registry(reg: dict) -> None:
    VAULT.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


def find_printer(reg: dict, ident: str) -> dict | None:
    for p in reg["printers"]:
        if ident in (p["id"], p.get("cups_queue")):
            return p
    return None


# ---------------------------------------------------------------- probes

def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve(host: str) -> str | None:
    # An absent .local name makes nss-mdns wait out its full timeout rather than fail.
    try:
        p = run(["getent", "hosts", host], timeout=4)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout.split()[0] if p.returncode == 0 and p.stdout.strip() else None


def unescape_avahi(s: str) -> str:
    # avahi-browse -p escapes as \DDD (decimal)
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), s)


def parse_txt(fields: str) -> dict:
    return {k: v for k, v in (t.split("=", 1) for t in re.findall(r'"([^"]*)"', fields) if "=" in t)}


def mdns_discover(timeout: int) -> list[dict]:
    if not shutil.which("avahi-browse"):
        return []
    devices: dict[str, dict] = {}
    for svc in SERVICES:
        try:
            p = run(["avahi-browse", "-rtp", svc], timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        for line in p.stdout.splitlines():
            parts = line.split(";", 9)
            if len(parts) < 9 or parts[0] != "=" or parts[2] != "IPv4":
                continue
            _, iface, _, name, _, _, host, addr, port = parts[:9]
            txt = parse_txt(parts[9] if len(parts) > 9 else "")
            key = txt.get("UUID") or host
            d = devices.setdefault(key, {
                "service_name": unescape_avahi(name), "host": host, "ip": addr, "interface": iface,
                "uuid": txt.get("UUID"), "services": {}, "txt": {},
            })
            d["services"][svc] = int(port)
            # IPP is browsed first and its TXT is the authoritative one; scanner and
            # raw-socket records reuse keys like rp/pdl/adminurl with other meanings.
            for k, v in txt.items():
                if v:
                    d["txt"].setdefault(k, v)
    result = []
    for d in devices.values():
        t, s = d.pop("txt"), d["services"]
        model = t.get("ty") or t.get("usb_MDL") or d["service_name"]
        rp = t.get("rp", "ipp/print")
        quoted = urllib.parse.quote(d["service_name"], safe="()")  # same form lpinfo -v emits
        d.update({
            "make_model": model,
            "kind": "label" if LABEL_MODEL.search(model) else "document",
            "mac": t.get("mac"),
            "uris": {
                "ipps": f"ipps://{d['host']}:{s['_ipps._tcp']}/{rp}" if "_ipps._tcp" in s else None,
                "ipp": f"ipp://{d['host']}:{s['_ipp._tcp']}/{rp}" if "_ipp._tcp" in s else None,
                # Survives DHCP changes: CUPS re-resolves the service name each job.
                "dnssd": f"ipps://{quoted}._ipps._tcp.local/" if "_ipps._tcp" in s
                         else (f"ipp://{quoted}._ipp._tcp.local/" if "_ipp._tcp" in s else None),
                "socket": f"socket://{d['ip']}:{s['_pdl-datastream._tcp']}" if "_pdl-datastream._tcp" in s else None,
            },
            "capabilities": {
                "color": t.get("Color") == "T", "duplex": t.get("Duplex") == "T",
                "scan": t.get("Scan") == "T" or "_uscan._tcp" in s or "_uscans._tcp" in s,
                "fax": t.get("Fax") == "T", "paper_max": t.get("PaperMax"),
                "pdl": t.get("pdl", "").split(",") if t.get("pdl") else [],
                "airprint": "URF" in t,
            },
            "admin_url": t.get("adminurl"),
            "suggested_id": slug(model),
        })
        result.append(d)
    return result


def slug(s: str) -> str:
    s = re.sub(r"\b(series|printer|inc|co)\b", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def uri_host_port(uri: str) -> tuple[str | None, int]:
    u = urllib.parse.urlparse(uri)
    if u.scheme in ("usb", "file", "") or u.hostname is None:
        return None, 0
    default = {"ipp": 631, "ipps": 631, "socket": 9100, "lpd": 515, "http": 631, "https": 631}.get(u.scheme, 631)
    return u.hostname, u.port or default


def queue_reachable(uri: str) -> tuple[bool | None, str]:
    u = urllib.parse.urlparse(uri)
    if u.scheme == "usb":
        model = urllib.parse.unquote(u.path.strip("/"))
        p = run(["lsusb"], timeout=5)
        vendor = urllib.parse.unquote(u.netloc)
        hit = any(vendor.lower() in l.lower() and model.split()[0].lower() in l.lower() for l in p.stdout.splitlines())
        return hit, "USB device present" if hit else "USB device not attached"
    if u.scheme == "dnssd" or (u.hostname or "").endswith("._tcp.local"):
        # ipptool resolves DNS-SD service names itself; a TCP check would need the host first.
        if u.scheme == "dnssd":
            return None, "dnssd:// backend; resolved by CUPS at print time"
        try:
            ok = run(["ipptool", "-q", "-T", "5", uri, "get-printer-attributes.test"], timeout=10).returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        return ok, "DNS-SD service answered IPP" if ok else "DNS-SD service did not answer (off, asleep or not on this network)"
    host, port = uri_host_port(uri)
    if not host:
        return None, "unknown backend"
    ip = resolve(host) if host.endswith(".local") else host
    if not ip:
        return False, f"{host} does not resolve (not on this network?)"
    return (tcp_open(ip, port), f"{ip}:{port}")


def cups_queues() -> list[dict]:
    if not shutil.which("lpstat"):
        return []
    p = run(["lpstat", "-v"], timeout=10)
    default = run(["lpstat", "-d"], timeout=10).stdout
    states = {m.group(1): m.group(2) for m in re.finditer(r"^printer (\S+) (?:is )?(\w+)", run(["lpstat", "-p"], timeout=10).stdout, re.M)}
    queues = []
    for m in re.finditer(r"^device for (\S+): (\S+)", p.stdout, re.M):
        name, uri = m.group(1), m.group(2)
        reachable, detail = queue_reachable(uri)
        queues.append({"queue": name, "uri": uri, "state": states.get(name), "default": f": {name}" in default,
                       "reachable": reachable, "reachability_detail": detail})
    return queues


def usb_printers() -> list[dict]:
    if not shutil.which("lsusb"):
        return []
    found = []
    for line in run(["lsusb"], timeout=5).stdout.splitlines():
        m = re.search(r"ID ([0-9a-f]{4}):([0-9a-f]{4}) (.*)", line)
        if m and m.group(1) in USB_VENDORS:
            found.append({"usb_id": f"{m.group(1)}:{m.group(2)}", "vendor": USB_VENDORS[m.group(1)], "description": m.group(3).strip()})
    return found


def ipp_attributes(uri: str) -> dict:
    if not shutil.which("ipptool"):
        die("ipptool not installed (package cups-ipp-utils)")
    p = run(["ipptool", "-T", "10", "-j", uri, "get-printer-attributes.test"], timeout=20)
    # ipptool -j (CUPS 2.4) emits a trailing comma after the last member of an array of
    # collections (e.g. printer-resolution-supported), which is not valid JSON.
    text = re.sub(r",(\s*[\]}])", r"\1", p.stdout)
    try:
        groups = json.loads(text)
    except json.JSONDecodeError:
        die(f"no IPP answer from {uri}: {p.stderr.strip() or p.stdout.strip()[:300]}")
    attrs: dict = {}
    for g in groups:
        if g.get("group-tag") == "printer-attributes-tag":
            attrs.update(g)
    return attrs


PRINTER_STATES = {3: "idle", 4: "processing", 5: "stopped"}


def as_list(v) -> list:
    return v if isinstance(v, list) else ([] if v is None else [v])


def summarise_ipp(a: dict) -> dict:
    names, levels = as_list(a.get("marker-names")), as_list(a.get("marker-levels"))
    lows = as_list(a.get("marker-low-levels")) or [None] * len(names)
    return {
        "make_model": a.get("printer-make-and-model"),
        "info": a.get("printer-info"),
        "location": a.get("printer-location") or None,
        "state": PRINTER_STATES.get(a.get("printer-state"), a.get("printer-state")),
        "state_reasons": as_list(a.get("printer-state-reasons")),
        "state_message": a.get("printer-state-message") or None,
        "firmware": a.get("printer-firmware-string-version"),
        "uuid": (a.get("printer-uuid") or "").removeprefix("urn:uuid:") or None,
        "markers": [{"name": n, "level_percent": l, "low_at": lo, "low": l is not None and 0 <= l <= max(lo or 0, LOW_INK)}
                    for n, l, lo in zip(names, levels, lows)],
        "media_ready": as_list(a.get("media-ready")),
        "media_supported_count": len(as_list(a.get("media-supported"))),
        "sides_supported": as_list(a.get("sides-supported")),
        "color_supported": a.get("color-supported"),
        "color_modes": as_list(a.get("print-color-mode-supported")),
        "quality_supported": as_list(a.get("print-quality-supported")),
        "resolutions": as_list(a.get("printer-resolution-supported")),
        "formats": as_list(a.get("document-format-supported")),
        "uris": as_list(a.get("printer-uri-supported")),
        "admin_url": a.get("printer-more-info"),
        "queued_jobs": a.get("queued-job-count"),
    }


# ---------------------------------------------------------------- commands

def cmd_discover(args) -> None:
    net = mdns_discover(args.timeout)
    reg = load_registry()
    by_uuid = {p.get("uuid"): p["id"] for p in reg["printers"] if p.get("uuid")}
    for d in net:
        d["registered_as"] = by_uuid.get(d["uuid"])
    out({
        "ok": True, "at": now(),
        "network": net,
        "cups_queues": cups_queues(),
        "usb": usb_printers(),
        "tooling": {t: bool(shutil.which(t)) for t in ["avahi-browse", "lpstat", "lpadmin", "lp", "ipptool", "lsusb", "scanimage"]},
    })


def cmd_probe(args) -> None:
    target = args.target
    reg = load_registry()
    p = find_printer(reg, target)
    if p:
        target = p["uris"].get("ipps") or p["uris"].get("ipp")
    elif "://" not in target:
        target = f"ipp://{target}:631/ipp/print"
    out({"ok": True, "uri": target, "at": now(), **summarise_ipp(ipp_attributes(target))})


def cmd_registry(args) -> None:
    reg = load_registry()
    if args.action == "list":
        out({"ok": True, "registry": str(REGISTRY), "printers": reg["printers"]})
    elif args.action == "show":
        p = find_printer(reg, args.id) or die(f"no printer '{args.id}' in registry")
        out({"ok": True, "printer": p})
    elif args.action == "remove":
        before = len(reg["printers"])
        reg["printers"] = [p for p in reg["printers"] if p["id"] != args.id]
        if len(reg["printers"]) == before:
            die(f"no printer '{args.id}' in registry")
        save_registry(reg)
        out({"ok": True, "removed": args.id})
    elif args.action == "add":
        if find_printer(reg, args.id):
            die(f"'{args.id}' already registered — use `registry set` to change fields")
        entry = {"id": args.id, "name": args.name, "description": args.description, "site": args.site,
                 "kind": "document", "added_on": now()}
        if args.host:
            match = [d for d in mdns_discover(args.timeout) if args.host in (d["host"], d["ip"], d["uuid"])]
            if not match:
                die(f"'{args.host}' not found by mDNS — is it on and on this network?")
            d = match[0]
            entry.update({k: d[k] for k in ("make_model", "kind", "host", "ip", "mac", "uuid", "uris", "capabilities", "admin_url")})
            try:
                ipp = summarise_ipp(ipp_attributes(d["uris"]["ipp"] or d["uris"]["ipps"]))
                entry["profile"] = {k: ipp[k] for k in ("firmware", "markers", "media_ready", "sides_supported",
                                                        "color_modes", "quality_supported", "resolutions", "formats")}
                entry["profiled_on"] = now()
            except SystemExit:
                entry["profile"] = None
        elif args.cups_queue:
            q = next((q for q in cups_queues() if q["queue"] == args.cups_queue), None) or die(f"no CUPS queue '{args.cups_queue}'")
            entry.update({"make_model": args.model, "uris": {"cups_device": q["uri"]}})
        else:
            die("give --host (a discovered network printer) or --cups-queue (an existing local queue)")
        if args.cups_queue:
            entry["cups_queue"] = args.cups_queue
        if args.model:
            entry["make_model"] = args.model
        reg["printers"].append(entry)
        save_registry(reg)
        out({"ok": True, "registry": str(REGISTRY), "added": entry})
    elif args.action == "set":
        p = find_printer(reg, args.id) or die(f"no printer '{args.id}' in registry")
        for kv in args.field:
            k, _, v = kv.partition("=")
            p[k] = None if v == "" else v
        save_registry(reg)
        out({"ok": True, "printer": p})


def install_commands(p: dict, queue: str, default: bool, prefer: str) -> list[list[str]]:
    uris = p.get("uris", {})
    uri = uris.get(prefer) or uris.get("ipps") or uris.get("ipp") or uris.get("dnssd")
    if not uri:
        die(f"'{p['id']}' has no network URI to install from")
    cmds = [["lpadmin", "-p", queue, "-E", "-v", uri, "-m", "everywhere",
             "-D", p.get("name") or queue, "-L", p.get("description") or ""]]
    if default:
        cmds.append(["lpadmin", "-d", queue])
    return cmds


def cmd_install(args) -> None:
    reg = load_registry()
    p = find_printer(reg, args.id) or die(f"no printer '{args.id}' in registry — profile it first")
    queue = args.queue or p.get("cups_queue") or re.sub(r"[^A-Za-z0-9_-]", "_", p["id"])
    cmds = install_commands(p, queue, args.default, args.uri)
    shell = " && ".join(" ".join(_shq(c) for c in cmd) for cmd in cmds)
    if args.dry_run:
        out({"ok": True, "queue": queue, "commands": shell, "note": "run on any Linux/macOS host with CUPS on the same LAN"})
        return
    for c in cmds:
        r = run(c, timeout=60)
        if r.returncode != 0 and "Forbidden" in (r.stderr + r.stdout):
            r = run(["sudo", "-n", *c], timeout=60)
        if r.returncode != 0:
            die(f"{' '.join(c)} failed: {r.stderr.strip() or r.stdout.strip()}")
    p["cups_queue"] = queue
    p.setdefault("installed_on", {})[socket.gethostname()] = now()
    save_registry(reg)
    q = next((q for q in cups_queues() if q["queue"] == queue), None)
    out({"ok": True, "queue": queue, "installed": q, "commands": shell})


def _shq(s: str) -> str:
    return s if re.fullmatch(r"[A-Za-z0-9_./:=@%-]+", s) else "'" + s.replace("'", "'\\''") + "'"


def cmd_queues(args) -> None:
    reg = load_registry()
    qs = cups_queues()
    for q in qs:
        p = find_printer(reg, q["queue"])
        q["registered_as"] = p["id"] if p else None
        q["site"] = p.get("site") if p else None
    out({"ok": True, "host": socket.gethostname(), "queues": qs})


def cmd_remove_queue(args) -> None:
    r = run(["lpadmin", "-x", args.queue], timeout=30)
    if r.returncode != 0:
        r = run(["sudo", "-n", "lpadmin", "-x", args.queue], timeout=30)
    if r.returncode != 0:
        die(f"lpadmin -x {args.queue} failed: {r.stderr.strip()}")
    out({"ok": True, "removed_queue": args.queue})


SIDES = {"one": "one-sided", "long": "two-sided-long-edge", "short": "two-sided-short-edge"}


def resolve_queue(ident: str | None) -> str:
    reg = load_registry()
    if ident:
        p = find_printer(reg, ident)
        if p:
            if not p.get("cups_queue"):
                die(f"'{ident}' is registered but not installed on this machine — run `install {ident}` first")
            return p["cups_queue"]
        if any(q["queue"] == ident for q in cups_queues()):
            return ident
        die(f"'{ident}' is neither a registry id nor a CUPS queue here")
    d = re.search(r": (\S+)", run(["lpstat", "-d"]).stdout)
    if d:
        return d.group(1)
    if len(reg["printers"]) == 1 and reg["printers"][0].get("cups_queue"):
        return reg["printers"][0]["cups_queue"]
    die("no printer given and no system default — name one")


def cmd_print(args) -> None:
    queue = resolve_queue(args.printer)
    files = [Path(f).expanduser() for f in args.files]
    for f in files:
        if not f.is_file():
            die(f"no such file: {f}")
    if args.copies > MAX_COPIES:
        die(f"{args.copies} copies exceeds the cap of {MAX_COPIES} (LAN_PRINT_SCAN_MAX_COPIES)")
    cmd = ["lp", "-d", queue, "-n", str(args.copies), "-o", f"sides={SIDES[args.sides]}"]
    if args.mono:
        cmd += ["-o", "print-color-mode=monochrome"]
    if args.pages:
        cmd += ["-o", f"page-ranges={args.pages}"]
    if args.media:
        cmd += ["-o", f"media={args.media}"]
    if args.quality:
        cmd += ["-o", f"print-quality={ {'draft': 3, 'normal': 4, 'high': 5}[args.quality] }"]
    if args.fit:
        cmd += ["-o", "fit-to-page"]
    if args.title:
        cmd += ["-t", args.title]
    for o in args.option or []:
        cmd += ["-o", o]
    if args.ps:  # PDFs go as PostScript, past a print server whose pdftopdf mangles them (skill print)
        tmp = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "lan-print-scan"
        tmp.mkdir(parents=True, exist_ok=True)
        conv = []
        for f in files:
            if f.suffix.lower() == ".pdf":
                ps = tmp / (f.stem + ".ps")
                if not args.dry_run:
                    run(["pdftops", "-level3", "-paper", "match", str(f), str(ps)], timeout=120, check=True)
                conv.append(ps)
            else:
                conv.append(f)
        files = conv
    cmd += [str(f) for f in files]
    if args.dry_run:
        out({"ok": True, "dry_run": True, "queue": queue, "command": " ".join(_shq(c) for c in cmd)})
        return
    r = run(cmd, timeout=120, check=True)
    jobs = re.findall(r"request id is (\S+)", r.stdout)
    out({"ok": True, "queue": queue, "jobs": jobs, "files": [str(f) for f in files]})


def cmd_status(args) -> None:
    reg = load_registry()
    p = find_printer(reg, args.printer) if args.printer else None
    uri = None
    if p:
        uri = p["uris"].get("ipp") or p["uris"].get("ipps")
    elif args.printer and "://" in args.printer:
        uri = args.printer
    elif args.printer:
        q = next((q for q in cups_queues() if q["queue"] == args.printer), None) or die(f"unknown printer '{args.printer}'")
        uri = q["uri"]
    else:
        die("name a printer (registry id, queue or ipp:// URI)")
    result = {"ok": True, "printer": args.printer, "uri": uri, "at": now()}
    if uri.startswith(("ipp://", "ipps://")):
        result.update({k: v for k, v in summarise_ipp(ipp_attributes(uri)).items()
                       if k in ("make_model", "state", "state_reasons", "state_message", "markers", "media_ready", "queued_jobs")})
    queue = p.get("cups_queue") if p else args.printer
    if queue:
        result["local_jobs"] = run(["lpstat", "-o", queue], timeout=10).stdout.strip().splitlines()
    out(result)


def cmd_cancel(args) -> None:
    cmd = ["cancel", "-a", resolve_queue(args.printer)] if args.all else ["cancel", *args.job]
    run(cmd, timeout=20, check=True)
    out({"ok": True, "cancelled": args.job or "all"})


# ---------------------------------------------------------------- jobs (2026-11-13)
# A client queue that points at a CUPS print server (ipp://host:631/printers/NAME) has two job lists: this machine's, and the
# server's, where a job that fails in a filter sits "stopped" while the client queue looks fine or keeps "printing". `jobs`
# shows both plus the server's printer message; `clean-jobs` cancels stale ones on both. Remote cancel works for the job's
# own user from an allowed network (no /admin needed).

def upstream(queue: str) -> tuple[str, str] | None:
    """(host:port, server queue) when this queue forwards to another CUPS server, else None."""
    m = re.search(r"device for \S+: (ipps?)://([^/]+)/printers/([^/?\s]+)", run(["lpstat", "-v", queue], timeout=10).stdout)
    if not m:
        return None
    host = m.group(2) if ":" in m.group(2) else f"{m.group(2)}:631"
    return host, m.group(3)


def _jobs(queue: str, host: str | None = None, which: str = "not-completed") -> list[dict]:
    cmd = ["lpstat"] + (["-h", host] if host else []) + ["-W", which, "-o", queue]
    rows = []
    for line in run(cmd, timeout=15).stdout.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].startswith(queue + "-"):
            continue
        when = None
        for fmt in ("%a %b %d %H:%M:%S %Y", "%a %d %b %Y %H:%M:%S"):  # C locale, then a day-first locale
            try:
                when = dt.datetime.strptime(" ".join(parts[3:8]), fmt)
                break
            except ValueError:
                pass
        rows.append({"id": parts[0], "user": parts[1], "bytes": int(parts[2]) if parts[2].isdigit() else None,
                     "submitted": when.isoformat() if when else " ".join(parts[3:]),
                     "age_min": round((dt.datetime.now() - when).total_seconds() / 60, 1) if when else None})
    return rows


def _printer_message(queue: str, host: str | None = None) -> str:
    lines = run(["lpstat"] + (["-h", host] if host else []) + ["-l", "-p", queue], timeout=15).stdout.splitlines()
    return " | ".join(l.strip() for l in lines[:2] if l.strip())


def cmd_jobs(args) -> None:
    queue = resolve_queue(args.printer)
    which = "completed" if args.completed else "not-completed"
    result = {"ok": True, "queue": queue, "local": _jobs(queue, which=which), "local_printer": _printer_message(queue)}
    up = upstream(queue)
    if up:
        result["server"] = {"host": up[0], "queue": up[1], "jobs": _jobs(up[1], up[0], which), "printer": _printer_message(up[1], up[0])}
    if "filter failed" in json.dumps(result):
        result["hint"] = ("A filter failed on the print server. For a PDF, send PostScript instead: print --ps "
                          "(skill print, 'PDF stops with gstoraster filter failed').")
    out(result)


def cmd_clean_jobs(args) -> None:
    queue = resolve_queue(args.printer)
    stale = lambda j: args.all or (j["age_min"] is not None and j["age_min"] >= args.stale)
    plan = [{"where": "local", "id": j["id"], "age_min": j["age_min"]} for j in _jobs(queue) if stale(j)]
    up = upstream(queue)
    if up:
        plan += [{"where": up[0], "id": j["id"], "age_min": j["age_min"]} for j in _jobs(up[1], up[0]) if stale(j)]
    if args.dry_run:
        out({"ok": True, "dry_run": True, "queue": queue, "would_cancel": plan})
        return
    done = []
    for j in plan:
        r = run(["cancel"] + ([] if j["where"] == "local" else ["-h", j["where"]]) + [j["id"]], timeout=20)
        done.append({**j, "ok": r.returncode == 0, "error": r.stderr.strip() or None})
    out({"ok": all(d["ok"] for d in done), "queue": queue, "cancelled": done,
         "left": {"local": _jobs(queue), **({"server": _jobs(up[1], up[0])} if up else {})}})


# ---------------------------------------------------------------- documents

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"
USER_TEMPLATES = VAULT / "templates"  # private overlay: same file name wins
PANDOC_FONT = os.environ.get("LAN_PRINT_SCAN_FONT", "DejaVu Sans")
OFFICE = {".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp"}
NATIVE = {".pdf", ".ps", ".txt", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".pwg", ".urf"}


def cmd_topdf(args) -> None:
    src = Path(args.file).expanduser()
    if not src.is_file():
        die(f"no such file: {src}")
    ext = src.suffix.lower()
    dest = Path(args.out).expanduser() if args.out else src.with_suffix(".pdf")
    if ext in NATIVE:
        out({"ok": True, "pdf": None, "note": f"{ext} prints directly; no conversion needed", "file": str(src)})
        return
    if ext == ".typ":
        cmd = ["typst", "compile", str(src), str(dest)]
    elif ext in (".md", ".markdown", ".html", ".htm", ".rst", ".org"):
        # pandoc 3.7's typst template has no default font list; without mainfont it fails
        # with "font fallback list must not be empty".
        cmd = ["pandoc", str(src), "-o", str(dest), "--pdf-engine=typst",
               "-V", f"mainfont={PANDOC_FONT}", "-V", f"papersize={args.paper}", "-V", "margin.x=2cm", "-V", "margin.y=2cm"]
    elif ext in OFFICE:
        outdir = dest.parent
        cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)]
    else:
        die(f"don't know how to convert {ext}")
    if not shutil.which(cmd[0]):
        die(f"{cmd[0]} not installed")
    run(cmd, timeout=180, check=True)
    if ext in OFFICE and src.with_suffix(".pdf").name != dest.name:
        (dest.parent / src.with_suffix(".pdf").name).rename(dest)
    out({"ok": True, "pdf": str(dest), "pages": pdf_pages(dest)})


def pdf_pages(pdf: Path) -> int | None:
    if not shutil.which("pdfinfo"):
        return None
    m = re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", str(pdf)], timeout=20).stdout, re.M)
    return int(m.group(1)) if m else None


def cmd_render(args) -> None:
    if args.list:
        names = {t.stem for d in (USER_TEMPLATES, TEMPLATES) for t in d.glob("*.typ")}
        out({"ok": True, "templates": sorted(names)})
        return
    tpl = USER_TEMPLATES / f"{args.template}.typ"
    if not tpl.is_file():
        tpl = TEMPLATES / f"{args.template}.typ"
    if not tpl.is_file():
        die(f"no template '{args.template}' — see `render --list`")
    text = tpl.read_text()
    values = {"DATE": dt.datetime.now().strftime("%-d %B %Y, %H:%M"), "AGENT_NAME": "Claude Code"}
    for kv in args.var:
        k, _, v = kv.partition("=")
        values[k] = v
    if args.body_file:
        values["BODY"] = Path(args.body_file).expanduser().read_text()
    for k, v in values.items():
        text = text.replace(f"«{k}»", v)
    missing = sorted(set(re.findall(r"«([A-Z_]+)»", text)))
    if missing:
        die(f"unfilled template variables: {', '.join(missing)}")
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = args.name or f"{args.template}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    typ, pdf = outdir / f"{stem}.typ", outdir / f"{stem}.pdf"
    typ.write_text(text)
    run(["typst", "compile", str(typ), str(pdf)], timeout=120, check=True)
    out({"ok": True, "typ": str(typ), "pdf": str(pdf), "pages": pdf_pages(pdf)})


# ---------------------------------------------------------------- scanning

def scanner_device(p: dict | None) -> str:
    devices = re.findall(r"device `([^']+)' is a (.*)", run(["scanimage", "-L"], timeout=60).stdout)
    if not devices:
        die("scanimage -L found no scanners (is sane-airscan installed and the printer awake?)")
    if p:
        ip = p.get("ip")
        model = (p.get("make_model") or "").lower()
        for dev, desc in devices:
            if (ip and f"ip={ip}" in desc) or (model and model in desc.lower()):
                return dev
        die(f"no scanner matching '{p['id']}' among: {[d for d, _ in devices]}")
    net = [d for d, _ in devices if d.startswith(("airscan:", "escl:"))]
    if len(net) == 1:
        return net[0]
    die(f"several scanners; pick one with -p: {[d for d, _ in devices]}")


def cmd_scan(args) -> None:
    if not shutil.which("scanimage"):
        die("scanimage not installed (packages sane-utils, sane-airscan)")
    p = None
    if args.printer:
        p = find_printer(load_registry(), args.printer) or die(f"no printer '{args.printer}' in registry")
    dev = args.device or scanner_device(p)
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    dest = Path(args.out).expanduser() if args.out else outdir / f"scan-{dt.datetime.now():%Y%m%d-%H%M%S}.{args.format}"
    cmd = ["scanimage", "-d", dev, f"--format={args.format}", "--resolution", str(args.resolution),
           "--mode", args.mode, "--source", args.source, "-o", str(dest)]
    if args.area:  # A4 / Letter / WxH mm crop from top-left
        w, h = {"a4": (210, 297), "letter": (215.9, 279.4), "a5": (148, 210)}.get(args.area.lower(), (None, None))
        if w is None:
            w, h = (float(x) for x in args.area.lower().split("x"))
        cmd += ["-x", str(w), "-y", str(h)]
    r = run(cmd, timeout=300)
    if r.returncode != 0 or not dest.exists():
        die(f"scan failed: {r.stderr.strip()[-400:]}")
    out({"ok": True, "file": str(dest), "bytes": dest.stat().st_size, "device": dev,
         "resolution": args.resolution, "mode": args.mode})


def main() -> None:
    ap = argparse.ArgumentParser(prog="printctl")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover", help="mDNS + CUPS + USB sweep")
    s.add_argument("--timeout", type=int, default=8)
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("probe", help="full IPP attribute summary for a printer")
    s.add_argument("target", help="registry id, host/IP, or ipp(s):// URI")
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("registry")
    s.add_argument("action", choices=["list", "show", "add", "remove", "set"])
    s.add_argument("--id")
    s.add_argument("--name")
    s.add_argument("--description")
    s.add_argument("--site", default="home")
    s.add_argument("--host", help="mDNS host, IP or UUID from discover")
    s.add_argument("--cups-queue")
    s.add_argument("--model")
    s.add_argument("--field", action="append", default=[], help="key=value for `set`")
    s.add_argument("--timeout", type=int, default=8)
    s.set_defaults(fn=cmd_registry)

    s = sub.add_parser("install", help="add a registered printer as a CUPS queue (driverless IPP Everywhere)")
    s.add_argument("id")
    s.add_argument("--queue")
    s.add_argument("--default", action="store_true")
    # ipps by default: the .local hostname is MAC-derived on HP/Epson/Brother and survives
    # both DHCP changes and the printer renaming its mDNS service ("… (2)") after a reset.
    s.add_argument("--uri", choices=["dnssd", "ipps", "ipp"], default="ipps")
    s.add_argument("--dry-run", action="store_true", help="print the commands for another machine instead")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("queues", help="local CUPS queues with reachability")
    s.set_defaults(fn=cmd_queues)

    s = sub.add_parser("remove-queue")
    s.add_argument("queue")
    s.set_defaults(fn=cmd_remove_queue)

    s = sub.add_parser("print")
    s.add_argument("files", nargs="+")
    s.add_argument("-p", "--printer", help="registry id or CUPS queue (default: system default)")
    s.add_argument("-n", "--copies", type=int, default=1)
    s.add_argument("--sides", choices=list(SIDES), default="one")
    s.add_argument("--mono", action="store_true")
    s.add_argument("--pages", help="e.g. 1-3,5")
    s.add_argument("--media", help="e.g. A4, Letter, iso_a5_148x210mm")
    s.add_argument("--quality", choices=["draft", "normal", "high"])
    s.add_argument("--fit", action="store_true")
    s.add_argument("--title")
    s.add_argument("-o", "--option", action="append", help="raw lp -o option")
    s.add_argument("--ps", action="store_true", help="send PDFs as PostScript (pdftops), for a server that fails PDFs")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_print)

    s = sub.add_parser("jobs", help="jobs on this queue and, for a client queue, on the print server, with the printer message")
    s.add_argument("-p", "--printer")
    s.add_argument("--completed", action="store_true", help="completed jobs instead of pending ones")
    s.set_defaults(fn=cmd_jobs)

    s = sub.add_parser("clean-jobs", help="cancel stale or stuck jobs here and on the print server")
    s.add_argument("-p", "--printer")
    s.add_argument("--stale", type=float, default=5, help="minutes a pending job may wait before it counts as stuck (default 5)")
    s.add_argument("--all", action="store_true", help="every pending job, whatever its age")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_clean_jobs)

    s = sub.add_parser("status", help="state, ink/toner, media and queued jobs")
    s.add_argument("printer")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("cancel")
    s.add_argument("job", nargs="*")
    s.add_argument("-p", "--printer")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_cancel)

    s = sub.add_parser("topdf", help="convert Markdown/HTML/Office/Typst to a printable PDF")
    s.add_argument("file")
    s.add_argument("-o", "--out")
    s.add_argument("--paper", default="a4")
    s.set_defaults(fn=cmd_topdf)

    s = sub.add_parser("render", help="fill a Typst template from templates/ and compile it")
    s.add_argument("template", nargs="?")
    s.add_argument("--list", action="store_true")
    s.add_argument("--var", action="append", default=[], help="KEY=value for «KEY»")
    s.add_argument("--body-file", help="file whose contents become «BODY» (Typst markup)")
    s.add_argument("--outdir", default=str(Path.home() / "printing" / "drafts"))
    s.add_argument("--name")
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("scan", help="flatbed/ADF scan over eSCL (AirScan)")
    s.add_argument("-p", "--printer", help="registry id (default: the only network scanner)")
    s.add_argument("--device", help="explicit SANE device string from scanimage -L")
    s.add_argument("--format", choices=["pdf", "png", "jpeg", "tiff"], default="pdf")
    s.add_argument("--resolution", type=int, default=300)
    s.add_argument("--mode", choices=["Color", "Gray"], default="Color")
    s.add_argument("--source", choices=["Flatbed", "ADF"], default="Flatbed")
    s.add_argument("--area", help="a4 | letter | a5 | WxH in mm (default: full glass)")
    s.add_argument("--outdir", default=str(Path.home() / "printing" / "scans"))
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_scan)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
