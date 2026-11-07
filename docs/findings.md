# Findings

Verified 2026-10-21 on Ubuntu (CUPS 2.4.16, pandoc 3.7.0.2) against an HP DeskJet 5200 on a home LAN.

## `ipptool -j` emits invalid JSON

CUPS 2.4's `ipptool -j … get-printer-attributes.test` leaves a trailing comma after the
last member of an array of collections, for example:

```
"printer-resolution-supported": [ {…}, {…}, ],
```

`json.loads` rejects it ("Illegal trailing comma before end of array"). `printctl.py`
strips `,` before `]`/`}` before parsing. This is confirmed on the DeskJet 5200. Other
printers will hit it whenever they return any collection array.

## One device, several mDNS records with clashing TXT keys

The DeskJet advertises `_ipp`, `_ipps`, `_pdl-datastream` (9100), `_uscan` (8080) and
`_uscans` (443) under one UUID. The non-IPP records reuse TXT keys with different
values: `_pdl-datastream` has `rp=` (empty), and the scanner records carry their own
`pdl`, `rp` and `adminurl`. A naive merge (last wins) produced
`ipps://host:631/` with no `ipp/print` path, and a wrong `pdl` list. Fix: browse IPP
first and let the first non-empty value win.

## A missing `.local` name hangs instead of failing

`getent hosts EPSONXXXXXX.local` for a printer on another network blocks for the
whole nss-mdns timeout (>5 s) instead of returning "not found". Every lookup needs
its own timeout, and a timeout should count as "doesn't resolve".

## A CUPS `idle` queue proves nothing

`lpstat -p` reported all three leftover other-site queues (`EPSON_ET_2900_Series`,
`HP_LaserJet_M14-M17` USB, `QL-810W`) as `idle … enabled` while none of the printers
was reachable. That is the queue's state, not the device's. Reachability is checked
directly: a TCP connect to the resolved host:631, `ipptool` against DNS-SD URIs, or
`lsusb` for USB.

## `ipptool` resolves DNS-SD URIs itself

`ipptool -q -T 5 'ipps://<service>._ipps._tcp.local/' get-printer-attributes.test`
answers in ~0.5 s. That makes it the cheapest liveness check for a queue installed
with a DNS-SD URI. Resolving the name to a host first would need a 12 s avahi browse.

## Don't install queues with DNS-SD service-name URIs

The first install (2026-10-21) used the DNS-SD URI
`ipps://HP%20DeskJet%205200%20series%20%5BXXXXXX%5D%20(2)._ipps._tcp.local/`. The
`(2)` is an mDNS collision suffix: the printer saw its own name already taken at some
point (typically a stale record from before a reboot or a second interface) and
renamed itself. The suffix goes away or changes when the printer next restarts
cleanly, and a queue bound to the old name then points at nothing. CUPS still shows it
as `idle`. The `.local` **hostname** (`HPXXXXXXXXXXXX`, from the MAC) doesn't change,
so the `install` default is now `ipps://<host>.local:631/ipp/print`.

The SANE device name has the same problem (`airscan:e0:HP DeskJet 5200 series
[XXXXXX] (2)`), so `scan` looks the device up fresh each time by IP or model and
never stores it.

## HP's own low-ink threshold is 1 %

The DeskJet 5200 returns `marker-low-levels = 1,1`, so a check against the printer's
threshold only says "low" when the cartridge is empty. `status` flags `low` at
`max(printer threshold, 15 %)`.

## DNS-SD URI quoting

`lpinfo -v` emits the service name percent-encoded **except** parentheses:
`HP%20DeskJet%205200%20series%20%5BXXXXXX%5D%20(2)`. `urllib.parse.quote(name,
safe="()")` reproduces it exactly. The `(2)` suffix is the printer's own collision
rename after a reset, and it is part of the live name.

## `lpadmin` needs no sudo here

The user is in the `lpadmin` group, so `lpadmin -p … -m everywhere` succeeded
unprivileged. The script retries with `sudo -n` only on "Forbidden".

## pandoc → typst needs a font

`pandoc in.md -o out.pdf --pdf-engine=typst` fails in pandoc 3.7.0.2 with
`font fallback list must not be empty`. Passing `-V mainfont="DejaVu Sans"` (or any
installed font) fixes it, and `printctl.py topdf` always passes it.

## eSCL scanning works without config

`scanimage -L` finds the HP as `airscan:e0:…` through sane-airscan's mDNS discovery,
with no `/etc/sane.d/airscan.conf` entry needed. A 75 dpi grey PDF scan of the empty
glass was verified 2026-10-21 (11 KB).
