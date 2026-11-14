---
name: print-label
description: Print a label on any label printer behind the LAN print hub, choosing the printer by target (e.g. a NIIMBOT for small die-cut button labels, a Brother P-touch for tape). The hub renders text + icon server-side. Use on "print a label", "label this on the P-touch", "use the niimbot", "which label printers do we have".
allowed-tools: Bash(python3 *)
---

# Print a label through the print hub

All label printers sit behind one HTTP print queue ([LAN Print Hub](https://github.com/danielrosehill/LAN-Print-Hub)).
The client is stdlib-only:

```bash
H="${CLAUDE_PLUGIN_ROOT}/scripts/hubctl.py"
python3 "$H" targets                                            # printers + live health (kind: label | document)
python3 "$H" label -p <target> -t "Line 1\nLine 2" [-i ICON] [-n COPIES] --preview /tmp/p.png   # render only
python3 "$H" label -p <target> -t "Line 1\nLine 2" [-i ICON] [-n COPIES]                        # print, waits for the result
python3 "$H" label -p <target> --png FILE                       # an existing image
python3 "$H" jobs -l 10                                         # history
```

`-p` takes a target id or alias (`targets` lists both). Without `-p` the hub uses its default label printer.
Hub URL: `$PRINT_HUB`, else `hub.json` in the plugin data dir (`{"print_hub": "http://host:9190"}`); `site.md` names it.

## Choosing the target

- **Die-cut labels** (button caps, switch tags, small stickers) → the NIIMBOT-type target (`driver: niimblue`).
- **Continuous tape** (cable flags, shelf edges, long text) → the P-touch-type target (`driver: ptouch-bridge`). Length grows with the text; height is the loaded tape.
- A printer the user names wins.

## Steps

1. `--preview /tmp/p.png`, then Read the PNG. Thin outline icons print faintly: prefer filled icons, or drop the icon.
2. Same command without `--preview`. 3. Report the job `state` (`done` / `failed` + `error`).

## Options

`-i` Iconify id (`prefix:name`, bare name = `material-symbols:`). `--opt k=v` passes any hub label field, e.g.
NIIMBOT `layout=top|left|icon|text`, `margin_mm=1`, `offset_mm=-2`, `media=40x30`, `density=4`, `border=true`;
any target `invert=true`. Per-printer defaults (media, margin, offset calibration) live in the hub's `targets.yaml`,
so normally pass none.
