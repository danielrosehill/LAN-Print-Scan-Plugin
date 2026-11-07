---
name: tidy-queues
description: List this computer's CUPS print queues with whether each printer is actually reachable from here, tie them to registry entries and sites, and remove dead or duplicate queues with confirmation. Use when the print dialog is cluttered, after returning from another site, or when the user asks which printers are installed.
allowed-tools: Bash(python3 *), Bash(lpstat *)
---

# Tidy print queues

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" queues
```

Each queue comes back with `reachable` and `reachability_detail`, and with
`registered_as` / `site` from the registry.

| Situation | Suggest |
|---|---|
| unreachable, registered to another `site` | **Keep.** It's a travelling laptop's queue for the other house and will work again there. Say so. |
| unreachable, unregistered, `.local` host doesn't resolve | Ask what it was. Register it with its site, or remove it. |
| unreachable USB queue | The device is unplugged. Keep it if it belongs to a site the user visits. |
| two queues for one printer (same UUID/host) | Keep the `dnssd` one, remove the other. |
| label printer queue (QL, PT, DYMO) | Leave it alone. It belongs to the label-printer plugin. |

Removing a queue is easy to redo (`install` recreates it), but it is still a system
change. List what you'll remove and get one confirmation for the batch:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" remove-queue <queue>
```

After removing, clear `cups_queue` on the registry entry if it had one
(`registry set --id X --field cups_queue=`).
