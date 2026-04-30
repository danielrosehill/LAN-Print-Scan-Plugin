---
name: discover-printers-arp
description: Use when mDNS discovery fails or the user wants to scan all devices on the subnet.
---

# Discover Printers via ARP

Scan the local subnet using ARP to find all active devices, then identify likely printers by MAC OUI (vendor prefix).

## When to use

- Bonjour/mDNS is not available or found no results
- Printer is on the same subnet but not advertising mDNS
- Network-wide device inventory needed
- Firewall is blocking port 5353 (mDNS)

## Inputs to gather

- Optional: `--interface` — specific network interface (e.g. `eth0`; auto-detected if unset)
- Optional: `--vendor-filter` — filter by vendor name (e.g. "HP" to show only HP devices)

## Procedure

1. **Auto-detect interface.** If `--interface` not provided, derive the primary LAN interface:
   ```bash
   IFACE=$(ip -o -4 route show to default | awk '{print $5; exit}')
   echo "Scanning on interface: $IFACE"
   ```
   Stop if no default route found; ask user to specify `--interface` manually.

2. **Check for root/sudo.** Test if `arp-scan` is installed:
   ```bash
   command -v arp-scan >/dev/null || { echo "arp-scan not found. Install with: sudo apt-get install arp-scan"; exit 1; }
   ```
   If not installed, stop and show the apt command.

3. **Prompt for sudo if needed.** If not running as root, show:
   ```
   This scan requires sudo privilege to access raw network sockets.
   Running: sudo arp-scan --localnet -i <interface>
   ```

4. **Run ARP scan.** Execute:
   ```bash
   sudo arp-scan --localnet -i "$IFACE" 2>/dev/null
   ```

5. **Parse output and identify printers.** For each line with an IP and MAC, cross-reference the MAC OUI (first 3 octets) against a built-in vendor list:
   - `08:00:69` → Xerox
   - `08:52:BA` → HP
   - `1C:23:62` → HP
   - `4C:80:93` → Brother
   - `74:6F:F7` → Epson
   - `5C:F9:38` → Canon
   - `A4:B6:D3` → Kyocera
   - `00:00:48` → Ricoh
   - `00:1A:80` → Samsung
   - `00:14:85` → Lexmark
   - (and others as feasible)

6. **Format as table:**
   ```
   IP              MAC               Vendor      Likely Printer?
   192.168.1.50    08:52:BA:xx:xx:xx HP          Yes
   192.168.1.75    4C:80:93:xx:xx:xx Brother     Yes
   192.168.1.100   52:54:00:xx:xx:xx QEMU        No
   ...
   ```

7. **Apply vendor filter.** If `--vendor-filter` provided, show only matching rows.

## Output / side effects

- Table of ARP results with vendor guesses to stdout.
- No local files modified.
- Read-only; no side effects.

## Safety / constraints

- Requires sudo; will prompt the user.
- ARP scan is network-safe but may be flagged by intrusion detection on large networks.
- OUI matching is heuristic; vendor list is not exhaustive and may have false positives/negatives.
- Will not find devices that are offline or do not respond to ARP.
