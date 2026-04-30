---
name: print-file
description: Use when the user wants to print a local file to a networked printer.
---

# Print File

Submit a file to print on a networked CUPS printer. Validate file existence, confirm copy count, and submit via MCP.

## When to use

- User has a file and wants to print it
- Printing to a specific printer or default
- Multiple copies requested

## Inputs to gather

- `path` — absolute or relative path to the file (required)
- `printer` — printer name (optional; uses default if unset)
- `copies` — number of copies (optional; defaults to 1)

## Procedure

1. **Validate file.** Check that `path` exists and is readable:
   ```bash
   test -r "$path" || { echo "File not readable: $path"; exit 1; }
   ```
   Stop if file not found or not readable.

2. **Load defaults.** If `printer` unset, read `MCP_CUPS_DEFAULT_PRINTER` from env or config.json. If still unset, run `list-printers` to show options and ask user to choose one.

3. **Warn on copy limit.** If `copies` exceeds `MCP_CUPS_MAX_COPIES` (from env or config), warn the user: "Copy count <N> exceeds safety limit <M>. Proceed?" and wait for confirmation before continuing.

4. **Confirm with user:** Show:
   ```
   Ready to print:
     File: <path>
     Printer: <name>
     Copies: <N>
   Proceed? (yes/no)
   ```
   Halt if user says no.

5. **Call MCP tool `print_file`** with `path`, `printer`, `copies`. The MCP server is `network-cups` (registered in `.mcp.json`).

6. **Report result:** On success, emit:
   ```
   Submitted to <printer>: <path> (<N> copies).
   ```
   On failure, show the MCP error and suggest `diagnose-network-printing`.

## Output / side effects

- File queued on the CUPS server; physical print job submitted.
- No local files modified.

## Safety / constraints

- Confirm before printing to avoid accidental submission.
- Warn if copies exceed the safety limit.
- Validate file exists before submitting to avoid cryptic server-side errors.
