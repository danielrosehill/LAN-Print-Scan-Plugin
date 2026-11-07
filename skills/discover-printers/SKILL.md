---
name: discover-printers
description: Find the printers this machine can see — networked (mDNS/Bonjour, IPP, raw 9100, eSCL scanners), USB-attached, and CUPS queues already set up — and say which queues are dead. Use when the user asks what printers there are, why a printer isn't showing, or before profiling or adding one.
allowed-tools: Bash(python3 *), Bash(lpstat *), Bash(avahi-browse *), Bash(ipptool *)
---

# Discover printers

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" discover
```

Takes ~12 s (one `avahi-browse` per service type). Returns JSON with four parts:

| Key | What it is |
|---|---|
| `network` | One entry per device, merged across `_ipp`, `_ipps`, `_pdl-datastream`, `_printer`, `_uscan(s)` by UUID. Carries `make_model`, `host`, `ip`, `mac`, `uris` (ipps / ipp / dnssd / socket), `capabilities` (color, duplex, scan, fax, pdl, airprint), `kind` (`document` or `label`), `suggested_id`, and `registered_as` if already in the registry. |
| `cups_queues` | Every local CUPS queue with `reachable` true/false/null and why. |
| `usb` | USB devices from printer vendors (HP, Epson, Brother, Canon …). |
| `tooling` | Which CLI tools exist. A missing `avahi-browse` means no network discovery, not no printers. |

## Reading the result

- **A CUPS queue saying `idle` proves nothing.** CUPS reports the queue's state,
  not the printer's. Trust `reachable`. A queue whose `.local` host does not resolve
  is for a printer on a different network (e.g. printers at another site when at home).
- **`kind: label`** (Brother QL/PT, DYMO, Zebra) belongs to the `label-printer`
  plugin. Mention it, don't profile it here.
- **Nothing on the network but you expected a printer:** inkjets sleep and drop off
  mDNS. Ask the user to wake it, then re-run. Next fallback is an IP probe:
  `printctl.py probe 192.168.1.x` (IPP on 631).
- One device often advertises several names (`… (2)` suffixes after a reset). The
  UUID merge handles that; the service name with the suffix is the live one.

Finish with a short table: printer, address, status (registered / not registered /
stale queue), and offer the next step — `profile-printer` for new ones,
`tidy-queues` for dead ones.
