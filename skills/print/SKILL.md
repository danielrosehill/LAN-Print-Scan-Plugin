---
name: print
description: Print one or more files (PDF, images, plain text, and — after conversion — Markdown, Office documents, Typst) to a registered printer or CUPS queue, with copies, duplex, monochrome, page ranges, paper size, quality and fit-to-page. Use when the user says "print this", "print N copies", "print double-sided / in black and white", or hands over a file to print.
allowed-tools: Bash(python3 *), Bash(pandoc *), Bash(typst *), Bash(soffice *), Bash(lpstat *)
---

# Print

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" print FILE [FILE…] \
  -p <id-or-queue> [-n COPIES] [--sides one|long|short] [--mono] \
  [--pages 1-3,5] [--media A4] [--quality draft|normal|high] [--fit] [--title T] \
  [-o raw=option] [--dry-run]
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

## After

The result carries `jobs` (CUPS request ids). If the user wants confirmation it came
out, use `printer-status` to check the job left the queue and that the printer isn't
in `stopped` / `media-empty`.
