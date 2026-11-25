---
name: print-label
description: Print a label on any label printer behind the LAN print hub, choosing the printer by target (e.g. a NIIMBOT for small die-cut button labels, a Brother P-touch for tape). The hub renders text + icon server-side. Use on "print a label", "label this on the P-touch", "use the niimbot", "which label printers do we have".
allowed-tools: Bash(python3 *)
---

# Print a label through the print hub

**Label design belongs to the `label-printer` plugin** (fonts, Hebrew/RTL, icons, layouts, styles, templates):
use its skills to design and preview the label. The hub is one transport: use this skill when the chosen
printer is registered on the hub, or when the user asks for the hub. Prefer `--png FILE` with a label rendered
by label-printer; the hub's server-side text/icon render (below) is the simple fallback and has no Hebrew/RTL support.

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

## Tape economy (continuous tape)

The hub scales text to the full tape height, so a short single line comes out huge: on 24 mm tape "Grade A" is
82 mm long, against 31 mm as `Grade\nA`. Before every tape print:

- **Read `size_px` from the preview**: length in mm = width px / 180 * 25.4 (180 dpi P-touch). Aim for about 45 mm or less for a
  short label; over 60 mm needs a reason (long text, a cable flag).
- **Break short text over two lines** with `\n`, balancing the lines. Compare the one- and two-line previews and print the shorter one.
- **Text that should stay on one line**: render a PNG at the tape's full pixel height (`health.maxPx`) with the text at a smaller
  size, centred vertically, and print it with `--png`. A 60 px font puts "Grade A" in about 32 mm.
- **Batch by default.** Two or more labels, even different ones, go out as one job:
  `uv run -q --script "${CLAUDE_PLUGIN_ROOT}/scripts/tape_batch.py" 'Grade A::2' 'Grade B::2' 'Lavaliers\n3.5 mm::2'` (`text::copies`; run with
  `--preview /tmp/p.png` first and read it). It goes straight to the P-touch bridge's `/print-batch`, sets a heading line over smaller
  lines, and keeps each label within `--max-mm 45`. Collect the labels of one request, and any that arrive while a job is being
  prepared, before printing. It does not appear in the hub's job list.
- **Tape width:** the script expects 24 mm and stops if another is loaded. On narrower tape (12 mm is about 70 px): one line, no
  icon, shortest wording, and follow the user's own instructions for it (`--tape 12`).
- **Group copies in one job** (`-n 2`): each job also feeds about 25 mm of lead tape (`tapeUsedMm` minus `labelMm`, 2026-11-25).
- A user who asks for a big label gets one.

## Resume after the tape runs out (or a jam)

The job is recorded before it is sent, so nothing has to be retyped. Do not resend the whole batch.

1. Ask the user for the first label that is **missing or unusable** (and which copy, if some copies of it came out). The bridge may
   report success for a job whose tape ran out, and a call that errored or was interrupted may still have printed: the strip in the
   user's hand decides.
2. Wait until the user says the new cartridge is in. A reported tape width does not prove the refill: an empty cassette still has one.
   If the new tape has another width, ask, then pass `--tape`.
3. `tape_batch.py --list` shows the recorded job. Preview the rest, read the PNG, then run it without `--preview`:
   `tape_batch.py --resume-from "USB-C 240W" [--copy 2] --preview /tmp/p.png`. A partly printed, unusable label is reprinted from
   its own copy number, so it counts as not printed.
4. The resumed part becomes the recorded job, so a second run-out resumes the same way.

A job sent before recording existed, or through another tool: `tape_batch.py --record-only 'A::2' 'B::1' ...`, then step 1.

## Options

`-i` Iconify id (`prefix:name`, bare name = `material-symbols:`). `--opt k=v` passes any hub label field, e.g.
NIIMBOT `layout=top|left|icon|text`, `margin_mm=1`, `offset_mm=-2`, `media=40x30`, `density=4`, `border=true`;
any target `invert=true`. Per-printer defaults (media, margin, offset calibration) live in the hub's `targets.yaml`,
so normally pass none.
