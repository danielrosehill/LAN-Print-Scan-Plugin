---
name: onboard
description: Use when the user installs the plugin and needs to configure it for the first time.
---

# Onboard

Configure the network-cups plugin for first-time use. Check system dependencies, elicit the CUPS server hostname, and write config to the plugin data directory.

## When to use

- Fresh plugin installation
- First-time setup
- Reconfiguring CUPS server connection

## Inputs to gather

- CUPS server hostname or IP (e.g. `cups.lan`)
- Optional: default printer name
- Optional: max copies safety limit

## Procedure

1. **Check dependencies.** Run:
   ```bash
   for cmd in avahi-browse arp-scan ufw nc node npm; do command -v $cmd >/dev/null 2>&1 || echo "missing: $cmd"; done
   ```
   Offer to install missing ones:
   ```bash
   sudo apt-get install avahi-utils arp-scan ufw cups-client nodejs npm
   ```

2. **Verify Node.js ≥18:**
   ```bash
   node --version
   ```
   If below 18, direct user to upgrade or use `nvm`.

3. **Elicit CUPS server hostname/IP.** Ask the user for the CUPS host (e.g. "cups.lan" or "192.168.1.100"). Confirm reachability:
   ```bash
   nc -zv <MCP_CUPS_SERVER> 631
   ```
   If timeout, stop and suggest checking the hostname/network or CUPS service on the server.

4. **Elicit optional settings.** Ask for default printer name and max copies limit; accept empty responses.

5. **Write config.json.** Create or overwrite:
   ```
   ${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugins}/network-cups/config.json
   ```
   with:
   ```json
   {
     "cups_server": "<hostname-or-ip>",
     "cups_port": 631,
     "default_printer": "<name-or-empty>",
     "max_copies": <number-or-null>
   }
   ```

6. **Set environment variables.** Show the user this snippet and instruct them to add it to their shell rc (`.bashrc`, `.zshrc`, etc.):
   ```bash
   export MCP_CUPS_SERVER="<hostname>"
   export MCP_CUPS_PORT=631
   export MCP_CUPS_DEFAULT_PRINTER="<printer-name>"
   export MCP_CUPS_MAX_COPIES=10
   ```
   Explain: "The MCP server (`lan-mcp-cups`) reads these env vars at startup. Without them in your shell, the plugin will not connect to CUPS."

7. **Optional smoke test.** Ask if the user wants to run `list-printers` to verify the connection. If yes, call `list-printers` skill.

## Output / side effects

- `${CLAUDE_USER_DATA}/network-cups/config.json` created with user-supplied CUPS server, port, and optional defaults.
- User shown env var snippet to add to their shell rc.
- Network reachability confirmed (nc port 631 succeeded).
- Dependencies validated or install command provided.

## Safety / constraints

- Do not write env vars to shell rc automatically; only show the snippet and instruct the user.
- `nc` may not report timeouts clearly on all systems; if in doubt, ask the user to ping the server manually.
- Instruct user that environment variables must be set **before** launching Claude Code if using the CLI, or persist them in the IDE's shell profile.
