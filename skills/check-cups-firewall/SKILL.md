---
name: check-cups-firewall
description: Use when CUPS connections are timing out and you suspect ufw firewall is blocking ports.
---

# Check CUPS Firewall Rules

Audit the local ufw firewall for CUPS (631/tcp, 631/udp) and mDNS (5353/udp) access rules.

## When to use

- User reports timeout connecting to CUPS
- Firewall misconfiguration suspected
- Pre-flight before troubleshooting CUPS connectivity
- Diagnostic: confirming rules are in place

## Inputs to gather

- None (reads firewall state)

## Procedure

1. **Check if ufw is active.** Run:
   ```bash
   sudo ufw status
   ```
   If output shows "inactive", report:
   ```
   ufw is not active. Firewall is not enforcing rules.
   (Another firewall may be in use — check nftables or firewalld.)
   ```
   Stop here.

2. **Detect alternate firewalls.** Check for:
   ```bash
   sudo systemctl is-active firewalld && echo "firewalld is running"
   sudo nft list tables 2>/dev/null && echo "nftables is active"
   ```
   If either is active, report:
   ```
   <firewall> is the active firewall, not ufw.
   This skill only audits ufw rules. Consult <firewall> docs.
   ```
   Stop here.

3. **Parse ufw status.** Run:
   ```bash
   sudo ufw status verbose
   ```
   Check for rules matching:
   - `631/tcp` (both in/out, or default allow-out)
   - `631/udp` (both in/out, or default allow-out)
   - `5353/udp` (mDNS, for Bonjour printer discovery)

4. **Emit checklist.** Output three rows:
   ```
   Firewall Rule Audit (ufw)
   
   Port     Proto  Direction  Status
   631      tcp    in         PASS  (allow 631/tcp in)
   631      tcp    out        PASS  (allow 631/tcp out)
   631      udp    in         PASS  (allow 631/udp in)
   631      udp    out        PASS  (allow 631/udp out)
   5353     udp    in         WARN  (not found; Bonjour discovery may fail)
   5353     udp    out        PASS  (allow 5353/udp out)
   ```
   Mark as PASS if found, FAIL if explicitly denied, WARN if missing but not critical.

5. **Show remediation commands.** If any FAILs or WARNs, output:
   ```bash
   To allow CUPS (631/tcp and 631/udp):
   sudo ufw allow 631/tcp
   sudo ufw allow 631/udp
   
   To allow mDNS (5353/udp) for printer discovery:
   sudo ufw allow 5353/udp
   
   To reload: sudo ufw reload
   ```

## Output / side effects

- Audit report (checklist of rules) to stdout.
- No rules modified (read-only).

## Safety / constraints

- Read-only; does not modify firewall rules.
- Does not attempt to auto-fix — user must approve and run the suggested commands manually.
- Only covers ufw; other firewalls require different steps.
