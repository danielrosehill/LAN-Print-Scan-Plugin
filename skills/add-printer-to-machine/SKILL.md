---
name: add-printer-to-machine
description: Add a registered printer as a CUPS queue on this computer (driverless IPP Everywhere, no vendor driver), optionally as the default, or produce the exact command to add it on another Linux/macOS machine on the LAN. Use when the user says "add the printer to this/that computer", "install the printer", "set up printing on X", or printing fails because no queue exists.
allowed-tools: Bash(python3 *), Bash(lpstat *), Bash(lpoptions *), Bash(ssh *)
---

# Add a printer to a computer

## This machine

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" install <id> [--default] [--queue NAME]
```

This runs `lpadmin -p <queue> -E -v <uri> -m everywhere`. **IPP Everywhere is the
right choice for any AirPrint/Mopria printer** (the registry's
`capabilities.airprint: true`). CUPS builds the PPD from the printer's own IPP
attributes, so no hplip, Epson or Brother driver is needed. Only fall back to a
vendor driver when the printer doesn't do IPP (old USB lasers). For USB IPP printers,
`ipp-usb` exposes them as network IPP.

URI choice (`--uri`, default `ipps`):

- `ipps`: `ipps://<host>.local:631/ipp/print`. The `.local` hostname is derived from
  the MAC on HP, Epson and Brother (`HPXXXXXXXXXXXX`, `EPSONXXXXXX`,
  `BRWXXXXXXXXXXXX`), so it survives both DHCP changes and the printer renaming its
  mDNS service. Use this by default.
- `dnssd`: `ipps://<service name>._ipps._tcp.local/`. Avoid it. The service name
  carries collision suffixes like `(2)` that the printer drops or changes after a
  reset, and the queue then silently points at nothing. The HP here has been
  advertising as `… [XXXXXX] (2)`.
- `ipp`: plain-text IPP. Only use it for printers whose TLS is broken.

On Ubuntu the user is in `lpadmin`, so no sudo is needed. If `lpadmin` says
Forbidden, the script retries with `sudo -n`. If that fails too, tell the user to run
the printed command with sudo.

`--default` sets the system default (`lpadmin -d`). For a per-user default without
touching the system, run `lpoptions -d <queue>` instead.

## Another machine

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" install <id> --dry-run
```

This prints a single `lpadmin …` line. Run it on the target:

- other Linux hosts: `ssh <host> '<command>'`. They need `cups` and `cups-client`
  installed and must resolve `.local` names (nss-mdns). Otherwise swap the
  hostname for the IP.
- **macOS**: the same `lpadmin` line works.
- **Windows / Android / iOS**: no command needed. They discover AirPrint/Mopria
  printers on their own. Tell the user to use the system "Add printer" dialog.

The remote install is recorded only if done on this machine. For a remote host, add a
note with `registry set --id X --field installed_elsewhere=<host>`.

## Verify

Check `printctl.py queues`: the new queue should say `reachable: true`. Don't send a
test page unless the user asks, because that uses paper and ink. `print --dry-run`
proves the queue accepts options.
