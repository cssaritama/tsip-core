# 0002 Readable charts and the render check

**Status:** shipped (0.2.13)
**Level:** 1 feature · **Open work:** W-45 (partly) · **Decisions:** ADR 0064

## Problem and decision supported

The founder reported that charts overlap and are hard to read (untested-levels ladder, 2026-11-04): labels of nearby levels touched each other and dots of levels at similar distances covered each other. A chart that cannot be read cannot support a decision, and overlaps were only caught by eye.

## Requirements

- R1. No text in a chart shall overlap other text, at any supported width (360 to 1920 px).
- R2. Dots of levels at similar distances shall not cover each other; labels moved away from their dot shall be joined to it by a leader line.
- R3. A render check shall build the page from a report, open it in a headless browser at several widths and fail on console errors, horizontal scroll and overlapping chart text.
- R4. No board tile, Time coordinate or revisit card shall be wider inside than its own box (content clipped by the tile is invisible to the page scroll check).

## Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| C1 | The untested-levels ladder keeps at least 16 px between labels, keeps highs above and lows below the close line, and draws leader lines for moved labels | render check (overlap test) on the published report of 2026-11-04 and on a synthetic report |
| C2 | The board's level map places highs above and lows below the axis and stacks dots that would touch | render check |
| C3 | The value label of the highlighted bar never overlaps a neighbouring bar's label | render check |
| C4 | `tools/render_check.py` reports zero overlaps, zero console errors and no horizontal scroll at 390, 768, 1024, 1280, 1440 and 1920 px, for an equity, a crypto market and a close-only index | run log in the release |
| C5 | The render check reports no clipped tile (added in 0.2.16; it found the cost selector widening the money tile at 390 px) | run log in the release |

## Non-goals

- Running the render check in GitHub Actions (W-45, next step: it needs a browser in the workflow).
- Pixel-perfect comparison against reference images.

## Design notes

Overlap is measured on the rendered bounding boxes of SVG text elements and dots, in screen pixels, with a one-pixel tolerance; hidden elements are ignored.

## Verification

| ID | Result | Evidence |
|---|---|---|
| C1 | passed | render check on the published report of 2026-11-04 14:44 UTC (SPY, QQQ, BTC, ETH, SPX, NDX) |
| C2 | passed | render check, 2026-11-04 |
| C3 | passed | render check, 2026-11-04 |
| C4 | passed: 0 problems on the published report and on a synthetic 0.2.13 report, at 390, 768, 1024, 1280, 1440 and 1920 px, dark and light | `tools/render_check.py` output, 2026-11-04 |
| C5 | passed after the fix (0.2.16) | `tools/render_check.py` output, 2026-11-05 |
