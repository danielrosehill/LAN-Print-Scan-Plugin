---
name: list-printers
description: Use when you want to see all configured printers on the networked CUPS server.
---

# List Printers

Query the CUPS server and return a formatted list of all available printers and their current state.

## When to use

- User wants to see available printers
- Diagnostic: checking if a printer is registered
- Pre-flight before printing or adding a printer

## Inputs to gather

- None (uses MCP_CUPS_SERVER from config/env)

## Procedure

1. **Load CUPS server hostname.** Read from env var `MCP_CUPS_SERVER` or fallback to `${CLAUDE_USER_DATA}/network-cups/config.json` → `cups_server` field.

2. **Call MCP tool `list_printers`** via the `network-cups` MCP server (registered in `.mcp.json`, invoked via `npx -y lan-mcp-cups`). This returns a JSON list of printer objects with fields: `name`, `state`, `is_default`, `location`, `info`.

3. **Format as table:** Columns: `Name`, `State`, `Location`, `Model`, `Default?`. If `is_default` is true, mark with `*`.

4. **Handle empty result:** If zero printers returned, output:
   ```
   No printers found on <cups_server>.
   Suggestions:
   - Run discover-printers-bonjour to scan the LAN for printers.
   - Run discover-printers-arp if Bonjour is not available.
   - Run diagnose-network-printing for full connectivity checks.
   ```

5. **Handle errors:** If MCP tool fails (e.g. connection refused, auth error), emit the raw error and suggest running `diagnose-network-printing`.

## Output / side effects

- Table of printers to stdout.
- No local files modified.

## Safety / constraints

- Read-only; no side effects on the CUPS server.
