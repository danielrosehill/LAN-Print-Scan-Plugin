---
name: add-printer
description: Use when the user wants to register a new printer on the networked CUPS server.
---

# Add Printer

Register a printer on the CUPS server. Requires the printer's network URI and optional driver specification.

## When to use

- User has a new printer on the network and wants to add it to CUPS
- Printer discovered via Bonjour or ARP but not yet registered
- Moving a printer to a new server

## Inputs to gather

- `name` — friendly name for the printer (required, e.g. "Office-HP-LaserJet")
- `uri` — network URI (required, e.g. `ipp://printer.lan:631/ipp/print` or `socket://192.168.1.50:9100`)
- `driver` — driver name (optional; CUPS auto-detects if unset, e.g. "drv:///sample.drv/generic.ppd")

## Procedure

1. **Pre-flight warning.** Inform the user:
   ```
   Adding a printer to CUPS requires lpadmin group or sudo privilege on the CUPS server.
   If this fails, you may need to:
   - Add your user to the lpadmin group on the server: sudo usermod -a -G lpadmin <user>
   - Or provide a password when prompted for sudo.
   ```

2. **Call MCP tool `add_printer`** with `name`, `uri`, and optional `driver`. The MCP server is `network-cups` (registered in `.mcp.json`).

3. **Report result.** On success:
   ```
   Printer added: <name> at <uri>.
   Run list-printers to verify.
   ```

4. **On failure,** emit the MCP error and suggest:
   - Check the URI is correct (ping the host, verify port).
   - Verify sudo/lpadmin privilege on the CUPS server.
   - Check the CUPS daemon is running on the server: `systemctl status cups`.
   - Run `diagnose-network-printing` to check CUPS connectivity.

## Output / side effects

- Printer registered on the CUPS server.
- No local files modified.
- Note: This operation runs on the CUPS server, not the client machine.

## Safety / constraints

- Requires privilege (lpadmin or sudo) on the CUPS server.
- Errors are usually privilege or network-related; local errors suggest the MCP server itself is misconfigured.
- Confirm the URI format before submitting; incorrect URIs cannot be edited after addition and must be removed/re-added.
