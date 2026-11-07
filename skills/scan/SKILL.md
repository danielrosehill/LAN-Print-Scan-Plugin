---
name: scan
description: Scan a document or photo from a networked printer's flatbed (or ADF) over eSCL/AirScan to PDF, PNG, JPEG or TIFF. Use when the user says "scan this", "scan to PDF", or wants a page from the glass digitised.
allowed-tools: Bash(python3 *), Bash(scanimage *), Bash(pdfunite *), Bash(mv *)
---

# Scan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" scan [-p <id>] \
  [--format pdf|png|jpeg|tiff] [--resolution 300] [--mode Color|Gray] \
  [--source Flatbed|ADF] [--area a4|letter|a5|WxH] [-o FILE | --outdir DIR]
```

The default is a 300 dpi colour PDF of the full glass into `~/printing/scans/`.
Scanning uses nothing up, so go ahead once the user says the page is on the glass.
If they haven't said so, ask once.

| User wants | Use |
|---|---|
| a document to keep or send | `--format pdf --mode Gray --area a4`, 300 dpi |
| a photo | `--format png --mode Color`, 600 dpi |
| something for OCR | `--format png --mode Gray`, 300 dpi |
| quick and small | 150 dpi |

`-p` matches the registry entry's IP or model against `scanimage -L`. Without `-p`,
the only network scanner is used. The SANE device name embeds the printer's mDNS
service name (e.g. `airscan:e0:HP DeskJet 5200 series [XXXXXX] (2)`), which changes
if the printer renames itself. That's why the script finds it fresh each time instead
of storing it.

## Multi-page

The DeskJet 5200 has a flatbed only. For several pages, scan each to its own PDF and
ask the user to swap the page between scans, then join them:

```bash
pdfunite p1.pdf p2.pdf p3.pdf combined.pdf
```

## When it fails

- `scanimage -L` lists nothing: check `sane-airscan` is installed and the printer is
  awake (`printctl.py status <id>`). eSCL is on 8080 (http) and 443 (https) for the
  HP. `discover` shows `_uscan` / `_uscans` when it's advertised.
- If it's still not found, pin it in `/etc/sane.d/airscan.conf` under `[devices]`:
  `"Home HP" = http://<ip>:8080/eSCL` (needs sudo; ask first).

After scanning, report the path and size, and ask where to file it if it's a keeper.
