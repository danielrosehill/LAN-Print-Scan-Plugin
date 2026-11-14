---
name: print
description: Print one or more files (PDF, images, plain text, and — after conversion — Markdown, Office documents, Typst) to a registered printer or CUPS queue, with copies, duplex, monochrome, page ranges, paper size, quality and fit-to-page. Use when the user says "print this", "print N copies", "print double-sided / in black and white", or hands over a file to print.
allowed-tools: Bash(python3 *), Bash(pandoc *), Bash(typst *), Bash(soffice *), Bash(lpstat *)
---

# Print

**If a print hub is configured** (`hub.json` key `print_hub`, or `$PRINT_HUB`; see `site.md`), send documents through it
so every job lands in one queue with history:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hubctl.py" print FILE [-p TARGET] [-n COPIES] [--sides one|long|short] \
  [--mono] [--pages 1-3] [--media A4] [--fit]
```

It accepts PDF, PostScript, images and plain text (convert anything else to PDF first, as below). Otherwise use the
local CUPS route:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" print FILE [FILE…] \
  -p <id-or-queue> [-n COPIES] [--sides one|long|short] [--mono] \
  [--pages 1-3,5] [--media A4] [--quality draft|normal|high] [--fit] [--title T] \
  [-o raw=option] [--ps] [--dry-run]
```

`-p` takes a registry id or a CUPS queue name. Leave it out to use the system default.
If there is no default and only one installed printer is registered, that one is used.
If the id is registered but has no queue on this machine, run `add-printer-to-machine`.

## Mapping what the user says

| User says | Flag |
|---|---|
| double-sided / duplex | `--sides long` (portrait). Use `--sides short` for landscape or flip-on-short-edge |
| black and white / save colour ink | `--mono` |
| draft / quick | `--quality draft` |
| pages 2 to 4 | `--pages 2-4` |
| fit / shrink to page | `--fit` |
| A5 / Letter | `--media A5` (`Letter`, `Legal`, or IPP names like `iso_a5_148x210mm`) |

Check against the printer's profile (`registry show`) before promising: duplex,
colour and paper sizes are in `capabilities` and `profile`. Copies are capped at
20 (`HOME_PRINTING_MAX_COPIES`). If more is asked, confirm first and set the env var
for that call.

## File types

CUPS filters handle **PDF, PostScript, JPEG/PNG and plain text** directly. Convert
everything else to PDF first (Markdown, HTML, `.typ`, docx/odt/xlsx/pptx):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" topdf in.md [-o out.pdf] [--paper a4|us-letter]
```

It returns the PDF path and page count. Markdown and HTML go through pandoc → typst
(font from `$HOME_PRINTING_FONT`, default DejaVu Sans), and Office files go through
`soffice --headless`. For complex web pages, a browser "save as PDF" beats pandoc.
To write a new document for paper, use `print-document`.

For anything over a few pages, or anything generated, show the page count and ask
before printing. Printing uses paper and can't be undone. One page, or the user
said "print it", means go ahead.

## PDF stops with "gstoraster filter failed"

If a PDF job stays in the queue, or the server logs `cfFilterGhostscript: Unexpected page count` / `gstoraster filter failed`
(the debug lines say `Missing Root object` or `Unable to find start of cross-reference table`), the server's `pdftopdf` filter
is mangling the PDF, not the file itself (seen 2026-11-13 on a snap CUPS 2.4 print server, with Chrome and cairo PDFs alike;
the spool copy was intact). Re-printing the PDF, or re-flattening it with `pdftocairo`, does not help. Cancel the stuck job
and send PostScript instead, which skips `pdftopdf`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" clean-jobs -p <queue> --all     # stuck jobs, here and on the server
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" print in.pdf -p <queue> --ps    # pdftops, then lp
```

If the site notes say the server has this fault, use `--ps` from the start.

For a landscape page do not add `-o landscape`: the page is already landscape, and the option rotates it a second time.
Confirm it printed from the server's `page_log` (`total 1`, not `total 0`), not from the client queue emptying.

## After

The result carries `jobs` (CUPS request ids). If the user wants confirmation it came
out, use `printer-status` to check the job left the queue and that the printer isn't
in `stopped` / `media-empty`.

A client queue that forwards to a print server empties even when the server stops the job. Check both sides:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" jobs -p <queue>               # pending here and on the server, printer message
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" jobs -p <queue> --completed   # the server's finished jobs
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" clean-jobs -p <queue> [--stale MIN | --all] [--dry-run]
```

`clean-jobs` cancels pending jobs older than `--stale` minutes (default 5), or all of them, on this machine and on the
server (remote cancel works for the job's own user). It only removes queued jobs, so it needs no confirmation; a page
already printing is lost, so check `jobs` first when one is mid-print.
