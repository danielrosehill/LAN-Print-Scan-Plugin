---
name: profile-printer
description: Record a discovered printer in the machine-local registry with an id, human name, site and description, plus a full IPP capability profile (ink, media, duplex, colour modes, resolutions, formats, firmware). Use after discovery finds a printer, when the user says "profile/remember/save this printer", or to refresh a profile after a firmware update or a move.
allowed-tools: Bash(python3 *)
---

# Profile a printer

The registry is what every other skill reads. It lives at
``printers.json` in the data dir` (override: `$LAN_PRINT_SCAN_DIR`).
It is machine-local because it holds LAN addresses, so it is never committed.

## 1. Find it

Run `discover-printers` first unless the user has given an IP or host.

## 2. Name it

Discovery gives a model and an address. It can't tell you what the user will call it
later ("the printer upstairs"). Ask for these together in one question, offering
defaults:

| Field | Default |
|---|---|
| `--id` | `suggested_id` from discovery, e.g. `hp-deskjet-5200` |
| `--name` | the model, tidied |
| `--site` | `home`. Use `office` or another site name for printers elsewhere |
| `--description` | where it is, what it's for, what paper is loaded |

## 3. Register

Network printer (pulls the mDNS record and a live IPP profile):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" registry add \
  --id hp-deskjet-5200 --name "HP DeskJet 5200" --site home \
  --description "Home — colour inkjet, duplex, scanner; A4 loaded" \
  --host 192.168.1.50          # mDNS host, IP or UUID from discover
```

An existing CUPS queue whose printer isn't reachable right now (USB, another site):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" registry add \
  --id hp-laserjet-m14 --name "HP LaserJet M14-M17" --site office \
  --description "…" --cups-queue HP_LaserJet_M14-M17 --model "HP LaserJet M14-M17"
```

`registry add` refuses a duplicate id. To change fields, use
`registry set --id X --field description=… --field site=…`. Don't remove and re-add,
because that loses `installed_on` history. To refresh the capability profile only,
run `probe <id>` and show it.

## 4. Show it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" registry show --id <id>
```

Report ink levels, media loaded, duplex/colour, and whether it can scan. Then offer
`add-printer-to-machine` if it has no `cups_queue` yet.
