# LAN Print & Scan

Print and scan on your local network from an AI agent. Plugin `lan-print-scan`, for Claude Code and compatible agents.

It covers discovery, a machine-local printer registry, adding printers to computers, printing, typeset printouts from
templates, eSCL scanning, status and queue tidying.

## Where to run it

You can install this anywhere, and it works fine on a single laptop. It's written for a **server**, though, and that's how I use it.

My own pattern is hub and spoke, the same one I use with [Canopy](https://github.com/danielrosehill/Canopy): one always-on home server
holds the integrations, and clients stay thin. Here that means the server holds the shared CUPS queues and the scan relay, and each client
needs nothing beyond a CUPS client and the server's address. Printer details live in one place, and printing keeps working from anywhere your
VPN reaches.

Start with skill `onboard`, which scans your network and asks which shape you want. Skill `server-routes` has the server setup.

## Your own details stay out of the plugin

The plugin holds no site details. Yours go in a private data dir, chosen in this order: `$LAN_PRINT_SCAN_DIR`, `$CLAUDE_USER_DATA/lan-print-scan`,
`~/.claude-user-data/lan-print-scan`, then `$XDG_DATA_HOME/claude-plugins/lan-print-scan`.

| File | Holds |
|---|---|
| `printers.json` | The printer registry, written by `printctl.py registry` |
| `site.md` | Your server, queues and access notes, read by `server-routes` |
| `templates/*.typ` | Your own Typst templates. The same file name overrides a built-in |

All work goes through one stdlib-only CLI, `scripts/printctl.py`, which wraps the CUPS
client tools, `ipptool` and `avahi-browse`. Every subcommand prints JSON.

## Skills

| Skill | Does |
|---|---|
| `onboard` | First run: scans the network, checks tools, chooses server or client, registers printers |
| `discover-printers` | mDNS (`_ipp`, `_ipps`, `_pdl-datastream`, `_printer`, `_uscan(s)`), USB and CUPS sweep, merged by UUID, with dead-queue detection |
| `profile-printer` | Registers a printer with an id, name, site and description, plus a live IPP profile (ink, media, duplex, colour modes, resolutions, formats, firmware) |
| `add-printer-to-machine` | Adds a driverless IPP Everywhere CUPS queue here, or prints the `lpadmin` line for another host |
| `print` | Copies, duplex, mono, page ranges, media, quality and fit. Converts Markdown, HTML, Office and Typst to PDF first (`topdf`) |
| `print-document` | Writes a printout in Typst (free-form, or from `templates/`: session summary, blocker, note to self, test page), previews it, then prints |
| `discover-printers-arp` | Finds printers by ARP sweep and vendor OUI when mDNS shows nothing |
| `diagnose-network-printing` | One-shot triage when printing doesn't work |
| `check-cups-firewall` | Read-only ufw audit for CUPS and mDNS |
| `scan` | Flatbed/ADF scan over eSCL (AirScan) to PDF, PNG, JPEG or TIFF |
| `server-routes` | Share queues from a server, print through it, and scan through the `escl-scan` relay |
| `printer-status` | Live IPP state, error reasons, ink levels, loaded paper, jobs and cancel |
| `tidy-queues` | Local queues with reachability and site, and removes dead ones with confirmation |

## CLI

```
printctl.py discover [--timeout 8]
printctl.py probe <id | host | ipp(s)://uri>
printctl.py registry list|show|add|remove|set [--id --name --description --site --host --cups-queue --model --field k=v]
printctl.py install <id> [--default] [--queue NAME] [--uri ipps|ipp|dnssd] [--dry-run]
printctl.py queues
printctl.py remove-queue <queue>
printctl.py print FILE… [-p id|queue] [-n N] [--sides one|long|short] [--mono] [--pages R] [--media M] [--quality draft|normal|high] [--fit] [-o raw] [--ps] [--dry-run]
printctl.py status <id | queue | uri>
printctl.py cancel <job…> | --all -p <printer>
printctl.py jobs [-p queue] [--completed]          # this machine and the upstream print server
printctl.py clean-jobs [-p queue] [--stale MIN | --all] [--dry-run]
printctl.py topdf FILE [-o out.pdf] [--paper a4|us-letter]
printctl.py render TEMPLATE --var K=V … [--body-file F] [--outdir D] | render --list
printctl.py scan [-p id] [--format pdf|png|jpeg|tiff] [--resolution N] [--mode Color|Gray] [--source Flatbed|ADF] [--area a4|letter|WxH] [-o FILE]
```

## Where state lives

| What | Where | Committed? |
|---|---|---|
| Registry (`printers.json`) | `the data dir`  | No. It holds LAN addresses that are true on one network only |
| Copy cap | `$LAN_PRINT_SCAN_MAX_COPIES` (default 20) | n/a |
| Low-ink warning | `$LAN_PRINT_SCAN_LOW_INK` (default 15 %) | n/a |
| Font for Markdown → PDF | `$LAN_PRINT_SCAN_FONT` (default DejaVu Sans) | n/a |
| Drafts, printed docs, scans | `~/printing/drafts/`, `~/printing/done/`, `~/printing/scans/` | No |

The registry schema and a redacted example are in [`docs/registry.md`](docs/registry.md).
Traps found while building this are in [`docs/findings.md`](docs/findings.md).

## Scope

Label printers (Brother QL/PT, DYMO, Zebra) are detected and flagged `kind: label`. Ones that sit behind an HTTP print
bridge can be printed to with `scripts/labelctl.py` (skill `print-label`), choosing the printer with `-p/--target`:

- `niimblue`: a NIIMBOT behind a [niimblue-node](https://github.com/MultiMote/niimblue-node) REST server, rendered by the
  `niimbot-labels` plugin's `niimlabel.py`.
- `ptouch-bridge`: a Brother P-touch behind a small `ptouch-print` HTTP bridge (`GET /health`, `POST /print`).

Directly attached QL printers without a bridge are still the job of
[`label-printer-plugin`](https://github.com/danielrosehill/label-printer-plugin).

## Requirements

`cups-client` (`lp`, `lpstat`, `lpadmin`, `cancel`), `cups-ipp-utils` (`ipptool`),
`avahi-utils`, and `python3` ≥ 3.10. For scanning: `sane-utils` + `sane-airscan`.
For documents: `typst`, `pandoc`, `soffice`, `poppler-utils` (`pdfinfo`, `pdftotext`).
