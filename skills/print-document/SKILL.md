---
name: print-document
description: Write a document for paper (a letter, list, checklist, note, session summary, blocker note or test page), typeset it with Typst, show it for approval, and print it. Use when the user asks to "make a printout", "print me a note/letter/checklist", "print a summary of this session", or "print a test page".
allowed-tools: Bash(python3 *), Bash(typst *), Bash(pdftotext *), Bash(pdftoppm *), Bash(mkdir *), Bash(mv *), Read, Write, Edit
---

# Create and print a document

Drafts go in `~/printing/drafts/`. Once printed, move both the `.typ` and `.pdf` to
`~/printing/done/`.

## Templates

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" render --list
```

| Template | For |
|---|---|
| `session-summary` | what an agent session accomplished |
| `blocker` | something that needs a human |
| `note-to-self` | a reminder worth having on paper |
| `test-page` | proves the queue and all four colour channels work. `TITLE` = printer name, `BODY` = ink line(s) from `status` |

Variables are `«AGENT_NAME»` (default "Claude Code"), `«MODEL_NAME»` (your model id),
`«DATE»` (default now), `«TITLE»` and `«BODY»` (Typst markup). Write a long body to a
file and pass it with `--body-file`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" render session-summary \
  --var MODEL_NAME=<model-id> --var "TITLE=…" --body-file /path/body.typ
```

`render` refuses to compile if any `«VAR»` is left unfilled. To add a private template, or
override a built-in, drop a `.typ` with the same placeholders into `templates/` in the data dir.

## Free-form documents

Write the `.typ` yourself with these defaults:

```typst
#set page(paper: "a4", margin: 2.5cm)
#set text(font: ("IBM Plex Sans", "DejaVu Sans"), size: 11pt)
#set par(justify: true, leading: 0.65em)
```

- **Letter:** right-aligned date block, then salutation, body, sign-off.
- **Checklist:** `#box(width: 0.8em, height: 0.8em, stroke: 0.5pt)` before each line.
- **Hebrew:** `#set text(lang: "he", dir: rtl, font: ("Noto Sans Hebrew", "DejaVu Sans"))`.
- Use A4 unless the user is printing in the US (Letter).

Compile with `typst compile in.typ out.pdf`.

## Approve, then print

1. Show the user `pdftotext out.pdf - | head -40` and the page count. For anything
   visual, render a preview (`pdftoppm -r 50 -png -f 1 -l 1 out.pdf prev`) and look at
   it yourself first.
2. Print after approval, using the `print` skill:
   `printctl.py print out.pdf -p <id> [--sides long] [--mono]`.
3. **Test pages need no approval.** The user asked for one knowing what it does.

To print an existing file (PDF, image, text, Markdown, Office), skip this skill and
use `print`.
