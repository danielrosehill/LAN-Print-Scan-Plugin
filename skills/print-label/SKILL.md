---
name: print-label
description: Print a label on any registered label printer, picking the target by id (e.g. a NIIMBOT B1 for small die-cut button labels, a Brother P-touch for tape labels). Use on "print a label", "label this on the P-touch", "use the niimbot", "which label printers do we have".
allowed-tools: Bash(uv *)
---

# Print a label (routed by target)

One command for every label printer in the registry (`printers.json`, entries with `kind: label`).

```bash
L="${CLAUDE_PLUGIN_ROOT}/scripts/labelctl.py"
uv run -q --script "$L" targets                                # what's registered, and is each bridge up
uv run -q --script "$L" print -p <id> -t "Line 1\nLine 2" [-i ICON] [-n COPIES] [--dry-run -o /tmp/p.png]
uv run -q --script "$L" print -p <id> --png FILE               # an existing image
```

`-p` / `--target` takes a registry id. Without it, the entry marked `"default": true` is used.

## Choosing the target

- Run `targets` first if you don't know what's registered or whether it's up. Each target reports its bridge's own `/health`.
- **Die-cut small labels** (button caps, switch tags, a 40x30 sticker) → the NIIMBOT-type target.
- **Continuous tape** (cable flags, shelf edges, long text, anything that should be laminated) → the P-touch-type target. Its length grows with the text; the height is the tape loaded (the bridge reports `tapeMm`/`maxPx`).
- If the user names a printer ("on the P-touch", "the niimbot"), use that one.

## Drivers

| `driver` | How it prints | Registry fields |
|---|---|---|
| `niimblue` | Hands off to the niimbot-labels plugin's `niimlabel.py` (its own rendering, media sizes and `offset_mm` calibration). Extra niimlabel flags go after `--`, e.g. `-- --margin 1 --layout top` | `bridge`, `client` (path to `niimlabel.py`) |
| `ptouch-bridge` | Renders here (icon left, text right, IBM Plex Sans Bold) and POSTs `{imageDataUrl, copies}` to `<bridge>/print` | `bridge` |

## Steps

1. `targets` if unsure. 2. `--dry-run -o /tmp/p.png`, then Read the PNG. 3. Same command without `--dry-run`. 4. Report the JSON result.

Document printing (A4 etc.) is the `print` skill (`printctl.py print -p <id>`), not this one.

## Adding a label printer

Add a registry entry by hand (`printctl.py registry` handles document printers): `id`, `name`, `kind: "label"`, `driver`,
`bridge`, plus `client` for `niimblue`. Schema in `docs/registry.md`.
