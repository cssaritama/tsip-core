# Design

The website is a reading instrument for one question: where does price stand in time, and what happened in past periods that stood in the same place? Every visual decision serves that question. This document is the reference for any change to `web/`.

## Structure: time and space

The page follows the time–space model (`docs/TIME_SPACE_MODEL.md`). After the title and the market switch come two panels with the same weight:

- **Time**: the calendar coordinates of the current or next session (session window, day of the week, month and turn of the month, quarter and year progress), each with the graded statistics for that coordinate.
- **Space**: the grid of horizons against their reference ranges, then the open-levels board.

The findings index is grouped the same way: Time (sessions and intraday, weekly structure, calendar) and Space (where we are now, level memory, time to revisit, paths and entries).

## Principles

1. **Two axes, one element each.** The Time panel and the Space grid carry the identity. The grid: one row per horizon with a comparable-period analysis (week to year), with time elapsed, a range bar (the reference range is the middle half of the track and the marker is the last close), distances to the reference high and low in percent and ATR, and what followed in comparable periods. A closed period shows the next period's starting position. Below the grid, the open-levels board. Everything else is quiet.
2. **Evidence before decoration.** Colour encodes evidence strength and data status only. No gradients, glows or ornamental colour.
3. **Honest copy.** Plain verbs, sentence case, no claims a statistic cannot support. Grades and samples are shown next to every figure. "No signals" and "no promises" are part of the page, not fine print.
4. **Fast by construction.** Static HTML, one stylesheet, one script, one self-hosted variable font, no framework, no third-party requests, no tracking. A test fails the build if the page references an external script, style or font.
5. **One motion moment.** On load, the elapsed-time bars grow and the current zone settles. Nothing else moves on its own, and `prefers-reduced-motion` turns it off.
6. **Accessible.** Visible keyboard focus, text contrast of at least 4.5:1 for body text, semantic headings, labelled figures, and layouts that work from 360 px wide.

## Tokens

Defined as custom properties in `web/assets/styles.css`. Dark is the default; light follows `prefers-color-scheme`.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#0d1828` ink blue | `#f3f5f7` | Page background |
| `--raise` | `#122036` | `#ffffff` | The grid and raised surfaces |
| `--sunk` | `#0a1422` | `#e9edf2` | Inactive zones, captions |
| `--text` | `#e8ecef` | `#102033` | Primary text |
| `--text-2` / `--muted` | `#b9c4d2` / `#8392a8` | `#33465e` / `#5c6b80` | Secondary and tertiary text |
| `--brass` | `#cdae72` | `#8f6a2c` | Evidence strength, the active zone, the selected market |
| `--time` | `#8fb7d8` | `#2f6c9e` | Time elapsed, taken extremes, fresh data |
| `--contra` | `#d07a6e` | `#b4483b` | Contradicted findings (grade F) and stale data only |

**Evidence scale.** Grades use one hue whose strength rises with the evidence: A, B and C are brass at decreasing intensity, D is a neutral slate, F is the contradiction red, N/A is empty. The evidence meter repeats the grade as filled segments (A five, B four, C three, D two, F one, N/A none), so the grade never depends on colour alone.

## Type

- **Instrument Sans** (variable, weight 400–700, width 75–100%), self-hosted from `web/assets/fonts/` under the SIL Open Font License (`OFL-instrument-sans.txt`). One family; personality comes from the width axis.
- Display and section titles: weight 500, width 78–82%, tight tracking (−0.025em to −0.01em).
- Body: 16 px, line height 1.6, width 100%, lines under 75 characters.
- All figures use tabular numerals so columns of rates align.
- Scale: 12.5, 13.5, 16, 19, 24, 34, 46 and a fluid display size up to 92 px.
- Not used: all-caps labels, eyebrow labels above headings, monospace data labels, arrows appended to links.

## Layout

```
bar      mark  Findings Method Data Register About            data status
hero     Where price stands in time.
         lede (60ch)
         SPY  QQQ  BTC      Index references  SPX  NDX
         ┌ Horizon │ Time elapsed │ Position against prior range │ What followed ┐
         │ Week    │ ███████░░░   │ ─┤  ▌      ├─  Low −0.6%  High +2.3% │ 45% ▮▮▮□□ C │
         │ Month   │ …            │                              │              │
         └ instrument, last close; method note ─────────────────────────────────┘
         Open levels: closed-period highs and lows not traded since, age, distance (% and ATR)
findings index (sticky) │ groups of findings: title, question, headline, grade, visual, details
method   grading scales with meters · controls · what the statistics can and cannot do
data     status per market · sources and quality checks
register pre-registered hypotheses
about, footer
```

Content is left aligned on a 1200 px column with 32 px gutters (16 px on phones). Findings are rows separated by hairlines, not cards: the grade and the visual sit in a 300 px side column on wide screens and stack below the text on narrow ones.

## Instrument order

ADR 0049: SPY, QQQ and Bitcoin are the primary markets of the switch; SPX and NDX appear as labelled index references. Statistics of different instruments are never combined on the page.

## Checking a change

1. `tsip report` on a data store (or a synthetic one), then `tsip site --report <report.json> --out dist`.
2. Serve `dist/` and review desktop (1440 px) and phone (390 px) widths in both colour schemes; check there is no horizontal scroll and no console error.
3. `pytest` includes the self-contained site test.
