---
name: server-routes
description: Share printing and scanning from one server, so clients and agents print and scan through it instead of talking to the device. Covers setting up shared CUPS queues, printing from a client, and the escl-scan relay. Use for "print through the server", "share the printer", "scan relay", or when off the LAN.
---

# Server routes

First read `site.md` in the data dir (see README) if it exists: it holds this deployment's addresses, queues and access commands.
Anything there overrides the examples below. If it's missing, run skill `onboard`.

## Set up the server

CUPS refuses remote clients until it's told otherwise. In `cupsd.conf`, allow only your own networks, and keep `/admin` local:

```
ServerAlias *
DefaultAuthType None
<Location />
  Order allow,deny
  Allow localhost
  Allow 192.168.1.0/24
</Location>
<Location /admin>
  Order allow,deny
  Allow localhost
</Location>
<Policy default>
  <Limit All>
    Order deny,allow
  </Limit>
</Policy>
```

This has no login: anything on those networks can print. Add a VPN or tailnet range if you want remote printing. Back the file up first,
then restart CUPS. Snap CUPS keeps its config in `/var/snap/cups/common/etc/cups/`. Then make a permanent shared queue:

```bash
lpadmin -p <queue> -E -v ipp://<printer>:631/ipp/print -m everywhere
lpadmin -p <queue> -o printer-is-shared=true
```

Don't use the queues `cups-browsed` creates on its own: they aren't shared. Give the printer a DHCP reservation.

## Print from a client

```bash
lp -h <server>:631 -d <queue> FILE
lpstat -h <server>:631 -p <queue>
```

Convert to PDF first with `printctl.py topdf`.

## Scan through the relay

`scripts/escl-scan` needs only Python, so nothing else is installed on the server. Link it onto the PATH, then run it there:

```bash
escl-scan --host <printer> --status
escl-scan --host <printer> --format pdf --resolution 300 --mode gray    # writes ~/printing/scans/ on the server
```

Confirm the page is on the glass first. Copy the file back, then delete it from the server. Flatbed only, A4. For several pages, run it once
per page and join them with `pdfunite`.
