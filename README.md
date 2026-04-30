# Network CUPS

Discover, diagnose, and print to networked CUPS printers from Claude Code.

Wraps the [`lan-mcp-cups`](https://github.com/danielrosehill/MCP-Network-CUPS) MCP server (auto-launched via `npx`) and adds bash-driven helper skills for LAN printer discovery and firewall diagnostics. Aimed at homelab setups where a Linux box runs CUPS and other LAN clients print to it over IPP.

## Skills

**MCP wrappers** (operate against the configured CUPS host):

- `list-printers` — show printers configured on the CUPS server
- `print-file` — print a local file to a networked printer
- `add-printer` — register a new printer on the CUPS server (requires lpadmin on the server side)

**LAN discovery**:

- `discover-printers-bonjour` — find printers via mDNS / Bonjour (`avahi-browse`)
- `discover-printers-arp` — find printers by ARP-scanning the LAN and matching vendor OUIs

**Diagnostics**:

- `check-cups-firewall` — read-only ufw audit for ports 631/tcp+udp and 5353/udp
- `diagnose-network-printing` — one-shot triage when "the printer doesn't work"

**Setup**:

- `onboard` — first-run setup; checks deps, elicits `MCP_CUPS_SERVER`, writes config

## Requirements

System packages: `avahi-utils`, `arp-scan`, `ufw`, `cups-client`, `node` >= 18 (for `npx`).

Environment variables (set during `onboard`, must be present in your shell so the MCP server picks them up):

- `MCP_CUPS_SERVER` (required) — CUPS host hostname/IP
- `MCP_CUPS_PORT` (default 631)
- `MCP_CUPS_DEFAULT_PRINTER` (optional)
- `MCP_CUPS_MAX_COPIES` (optional safety cap)

## Installation

```bash
claude plugins install network-cups@danielrosehill
```

Run the `onboard` skill once after installing.

## License

MIT
