# Registry

``printers.json` in the data dir`, written only by `printctl.py registry`
and `install`. It's machine-local and never committed.

```json
{
  "version": 1,
  "printers": [
    {
      "id": "hp-deskjet-5200",
      "name": "HP DeskJet 5200",
      "description": "Home — colour inkjet, duplex, flatbed scanner; A4 loaded",
      "site": "home",
      "kind": "document",
      "added_on": "2026-10-21T19:11:50+03:00",
      "make_model": "HP DeskJet 5200 series",
      "host": "HPXXXXXXXXXXXX.local",
      "ip": "192.168.1.x",
      "mac": "xx:xx:xx:xx:xx:xx",
      "uuid": "…",
      "uris": {
        "ipps": "ipps://<host>.local:631/ipp/print",
        "ipp": "ipp://<host>.local:631/ipp/print",
        "dnssd": "ipps://<percent-encoded service name>._ipps._tcp.local/",
        "socket": "socket://192.168.1.x:9100"
      },
      "capabilities": {
        "color": true, "duplex": true, "scan": true, "fax": true,
        "paper_max": "legal-A4", "airprint": true,
        "pdl": ["application/vnd.hp-PCL", "image/jpeg", "application/PCLm", "image/urf", "image/pwg-raster"]
      },
      "admin_url": "http://<host>.local./#hId-pgAirPrint",
      "profile": {
        "firmware": "…",
        "markers": [{"name": "tri-color ink", "level_percent": 90}, {"name": "black ink", "level_percent": 90}],
        "media_ready": ["iso_a4_210x297mm"],
        "sides_supported": ["one-sided", "two-sided-short-edge", "two-sided-long-edge"],
        "color_modes": ["auto", "auto-monochrome", "monochrome", "color", "process-monochrome"],
        "quality_supported": [3, 4, 5],
        "resolutions": [{"units": "dpi", "xres": 300, "yres": 300}],
        "formats": ["application/vnd.hp-PCL", "image/pwg-raster"]
      },
      "profiled_on": "2026-10-21T19:12:10+03:00",
      "cups_queue": "hp-deskjet-5200",
      "installed_on": {"<hostname>": "2026-10-21T19:12:12+03:00"}
    }
  ]
}
```

| Field | Notes |
|---|---|
| `id` | Key used by every subcommand. `-p`/`status` also accept `cups_queue` |
| `site` | Free text: `home`, `office`, … `tidy-queues` uses it to keep other sites' queues |
| `kind` | `document` or `label`. Label printers are out of scope |
| `profile` | `null` if the IPP probe failed at registration. Refresh with `probe <id>` |
| `profile.markers` | A snapshot from registration time. Use `status` for live levels |
| `cups_queue` / `installed_on` | Set by `install`. Queues added on other hosts aren't tracked automatically |

Entries registered from a CUPS queue only (`--cups-queue`, for printers that can't be
reached now) have `uris.cups_device` and no `capabilities`/`profile`.
