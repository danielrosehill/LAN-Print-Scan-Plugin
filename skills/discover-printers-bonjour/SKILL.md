---
name: discover-printers-bonjour
description: Use when you want to scan the LAN for printers via mDNS/Bonjour.
---

# Discover Printers via Bonjour

Scan the local network for printers advertising via mDNS (Bonjour/Avahi). Return a table of discovered devices.

## When to use

- User wants to find printers on the LAN by name/model
- Printer not yet registered in CUPS
- Bonjour/mDNS is available on the network
- Pre-flight before running `add-printer`

## Inputs to gather

- None (uses local avahi-daemon and network broadcast)

## Procedure

1. **Check avahi-daemon.** Verify the service is running:
   ```bash
   systemctl is-active avahi-daemon
   ```
   If inactive, output:
   ```
   avahi-daemon is not running.
   To start it: sudo systemctl start avahi-daemon
   To enable on boot: sudo systemctl enable avahi-daemon
   ```
   Stop here until the user confirms the service is running.

2. **Browse for printers.** Run with a 5-second timeout:
   ```bash
   timeout 5 avahi-browse -rt _ipp._tcp _ipps._tcp _printer._tcp 2>/dev/null || true
   ```
   Parse lines matching `=` (result/resolved) into a table.

3. **Extract fields.** For each result line, extract (using regex or field split):
   - `name` (service name, before `@`)
   - `hostname` (host field, or derive from full `address.local` record)
   - `IPv4` (address field, IPv4 only)
   - `port` (port number)
   - `model` (from `ty=` TXT field, e.g. "HP LaserJet Pro M404n")
   - `rp` (resource path, e.g. `/ipp/print`, from TXT field)

4. **Format as table:**
   ```
   Name                 Host              IPv4            Port  Model                    Path
   Office-HP            printer01.local   192.168.1.50    631   HP LaserJet Pro M404n    /ipp/print
   ...
   ```

5. **Handle empty result.** If no printers found after 5 seconds:
   ```
   No printers found via Bonjour.
   Possible reasons:
   - Printer does not support mDNS/Bonjour.
   - Printer is on a different VLAN or network segment.
   - Bonjour advertisement is disabled on the printer.
   
   Try: discover-printers-arp (ARP-based network scan)
   ```

## Output / side effects

- Printer table to stdout.
- No local files modified.
- Read-only; no side effects.

## Safety / constraints

- Read-only discovery; safe to run repeatedly.
- mDNS broadcast may not cross VLANs; if printers are segregated, try `discover-printers-arp`.
