---
name: diagnose-network-printing
description: Use when network printing fails and you need one-shot triage across all layers.
---

# Diagnose Network Printing

Run a comprehensive diagnostic sequence to isolate printing issues. Stop at the first hard failure and surface the remediation hint.

## When to use

- "The printer doesn't work" and user needs quick triage
- After configuration or network changes
- Before escalating to more detailed debugging
- Pre-flight after `onboard` setup

## Inputs to gather

- None (uses env vars and config from `onboard`)

## Procedure

Execute the following checks in sequence. Stop immediately on failure and show the remediation.

**1. Check MCP_CUPS_SERVER env var.**
```
Read MCP_CUPS_SERVER from environment.
If unset, read from ${CLAUDE_USER_DATA}/network-cups/config.json -> cups_server.
If still unset, emit: "CUPS server not configured. Run onboard skill."
Stop.
```

**2. Test TCP reachability to CUPS port 631.**
```bash
nc -zv -w 2 $MCP_CUPS_SERVER 631
```
If timeout/refused:
```
FAIL: Cannot reach CUPS server at $MCP_CUPS_SERVER:631.
Remediation:
  - Verify CUPS is running on the server: ssh <user>@$MCP_CUPS_SERVER systemctl status cups
  - Check firewall on the server: sudo ufw allow 631/tcp 631/udp
  - Verify hostname/IP is correct.
  - Run check-cups-firewall for local firewall audit.
Stop.
```

**3. Check avahi-daemon is active (for Bonjour printer discovery).**
```bash
systemctl is-active avahi-daemon
```
If inactive (but not a hard stop; just WARN):
```
WARN: avahi-daemon not running. Bonjour discovery will fail.
  To start: sudo systemctl start avahi-daemon
  To enable: sudo systemctl enable avahi-daemon
Continue to next check.
```

**4. Attempt brief Bonjour browse.**
```bash
timeout 3 avahi-browse -rt _ipp._tcp 2>/dev/null | head -5
```
If returns rows, output:
```
INFO: Found printers via Bonjour (sample output shown above).
```
If no rows:
```
WARN: No printers found via Bonjour. Printer may not support mDNS.
Continue to next check.
```

**5. Audit firewall (summary of check-cups-firewall).**
```
Run check-cups-firewall skill internally.
Emit one-line summary: "Firewall: PASS (631/tcp, 631/udp allowed)" or "Firewall: FAIL (see details below)".
If FAIL, show remediation commands inline.
```

**6. Query MCP list_printers.**
```
Call MCP tool list_printers via network-cups server.
If ≥1 printer returned, report: "PASS: <N> printer(s) registered on CUPS server."
If 0 printers, report: "WARN: No printers registered on CUPS server yet. Use add-printer or discover-printers-* to register one."
If MCP error (auth, connection), report: "FAIL: MCP connection failed: <error>. Check MCP_CUPS_SERVER and env vars."
```

## Output / side effects

Emit a checklist like:
```
Network Printing Diagnostic (2026-04-30)

[PASS] MCP_CUPS_SERVER set to: cups.lan
[PASS] TCP 631 reachable (CUPS running)
[WARN] avahi-daemon inactive (Bonjour unavailable) — run: sudo systemctl start avahi-daemon
[PASS] Firewall: 631/tcp, 631/udp allowed
[PASS] 2 printers registered on CUPS

Result: Network printing healthy.
```

Or (on first failure):
```
Network Printing Diagnostic (2026-04-30)

[PASS] MCP_CUPS_SERVER set to: cups.lan
[FAIL] TCP 631 unreachable
       Remediation:
       - Verify CUPS running on cups.lan: ssh user@cups.lan systemctl status cups
       - Check server firewall: sudo ufw allow 631/tcp 631/udp on the CUPS host
       - Confirm DNS resolution: nslookup cups.lan

Stopped at step 2. Fix above and re-run.
```

No local files modified.

## Safety / constraints

- Read-only diagnostic (except for `check-cups-firewall` which is also read-only).
- Safe to run repeatedly without side effects.
- Does not attempt to auto-fix; remediation hints are guidance only.
