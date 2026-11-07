---
name: onboard
description: First-run setup. Scan the local network for printers and scanners, check the tools, register what's found, and choose where this plugin runs, ideally a home server. Use on "set up printing", "onboard", "find the printers on my network", or the first time this plugin is used on a machine.
---

# Onboard

Read-only until step 4. Use `scripts/printctl.py`, at `${CLAUDE_PLUGIN_ROOT}/scripts/`.

1. **Check tools.** Run `printctl.py discover`. Its `tooling` block shows what's missing. See Requirements in the README, and say which
   features each missing tool costs. Ask before installing anything.
2. **Scan the network.** `discover` sweeps mDNS (`_ipp`, `_ipps`, `_pdl-datastream`, `_printer`, `_uscan`, `_uscans`), USB and existing CUPS
   queues. If a printer you expect is missing, wake it and re-run, then try skill `discover-printers-arp`, or `printctl.py probe <ip>`.
3. **Show the findings** as a short table: name, address, printing, scanning (`_uscan` means eSCL), and any label printers, which belong to a
   label plugin. Flag printers on DHCP: give them a reservation, or their address will change.
4. **Choose the shape** (see "Where to run it" in the README). Ask which machine this is:
   - **Server (recommended):** the shared queues and the scan relay live here. Continue with skill `server-routes`.
   - **Client of an existing server:** record the server, then stop. Nothing else is needed on a thin client.
   - **Standalone:** add queues to this machine with skill `add-printer-to-machine`.
5. **Register** each chosen printer with skill `profile-printer`.
6. **Save the site notes** to `site.md` in the data dir: server address, queue names, printer address, and how to reach the server. This
   file stays private, so don't put it in the plugin. Skill `server-routes` reads it.
7. **Test** with `printctl.py status <id>` and, for scanners, `escl-scan --status --host <printer>`. Offer a test page, because it uses paper.
