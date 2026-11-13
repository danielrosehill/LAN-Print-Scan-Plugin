---
name: printer-status
description: Live state of a printer — idle/processing/stopped, error reasons (paper jam, out of paper, door open, low ink), ink/toner levels, paper loaded, and queued jobs, with job cancellation. Use when the user asks about ink, whether a print went through, why nothing came out, or to cancel a job.
allowed-tools: Bash(python3 *), Bash(lpstat *), Bash(cancel *)
---

# Printer status

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" status <id|queue|ipp-uri>
```

This asks the printer itself over IPP, not the CUPS queue, so the answer is the
device's real state:

- `state`: `idle` / `processing` / `stopped`
- `state_reasons`: `none` means fine. Otherwise IPP keywords such as
  `media-empty-error`, `media-jam-error`, `door-open`, `marker-supply-low-warning`,
  `cover-open`, `offline-report`. Translate them for the user.
- `markers`: ink/toner per cartridge with `level_percent`, the printer's own `low_at`,
  and `low`. Many inkjets report a coarse estimate (e.g. 90 / 60 / 30 / 10), so say
  "about". `low` is true at or below the printer's threshold or 15%
  (`$HOME_PRINTING_LOW_INK`), whichever is higher. The DeskJet 5200 reports
  `low_at: 1`, so its own threshold only fires when the cartridge is empty.

  Show ink as a bar, flagging low ones:
  `Tri-color  █████████░  90%` / `Black  █░░░░░░░░░  10%  ⚠ low`
- `media_ready`: paper the printer reports as loaded.
- `local_jobs`: this machine's queued jobs for it.

## "Nothing came out"

Work through the layers in order:

1. `status`: is the printer `stopped`, or are there error reasons?
2. `lpstat -p <queue>`: CUPS may have disabled the queue after a failure.
   Re-enable with `cupsenable <queue>`.
3. `lpstat -o <queue>`: is the job stuck? See the job's error with `lpstat -l -o <queue>`.
4. `printctl.py queues`: a queue that is `reachable: false` points at a printer on
   another network.

## Cancel

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" cancel <job-id> [<job-id>…]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" cancel --all -p <id-or-queue>
```

Cancelling your own job is fine. Confirm before `--all`.

`cancel` only reaches this machine's queue. When the queue forwards to a print server, a failed job can sit "stopped" on
the server after the local queue has emptied ("why nothing came out"). See both, then clear stuck ones on both sides:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" jobs -p <queue>          # local + server jobs, and the server printer's message
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/printctl.py" clean-jobs -p <queue>    # cancel pending jobs older than 5 min (--stale, --all, --dry-run)
```

A server message of `filter failed` on a PDF means re-send with `print --ps` (skill `print`).
