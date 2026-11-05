# Design

The website is a decision instrument for one question: where does price stand in time and in space, and what has followed from the same place before? Every visual decision serves that question. This document is the reference for any change to `web/`.

## The decision standard

A page element earns its place only if it answers a question a trader asks before acting, and it answers it the same way every time:

1. **A question as the title.** "How far does it move?", not "Volatility".
2. **One figure first,** large, with its unit and its comparison in one line ("1.13%: average daily range over the last 14 sessions").
3. **One visual** that shows the figure against its control. Text explains the visual; it never replaces it.
4. **The grade next to the figure,** in letters and segments, with its meaning in plain words. Ungraded descriptions (today's ATR, position in a range) carry no grade and say what they are.
5. **A link to the evidence** (the full finding with method, control and numbers).
6. **No advice.** Figures describe what has happened. Verbs such as buy, sell, enter or target are not used.

Elements that cannot meet the standard (for example a statistic without a control) stay in the findings library, not in the board.

## Visual language

The same encodings are used everywhere, so a reader learns them once:

| Encoding | Meaning |
|---|---|
| Bar, with a thin line across it | Observed value (bar) against its control (line): random walk, arbitrary levels at the same distance, or the average slot |
| Bars above and below a zero line | Movement against the average slot (the zero line is the control), one bar per hour, half-hour, weekday, month or quarter |
| Solid line against dashed line | Real levels against the control over time (revisit curves) |
| Range track with a middle band | The prior period's range is the middle half of the track; the marker is the last close |
| Axis in ATR with a shaded band | Untested levels by distance from the last close; the band is one normal day (±1 ATR) |
| Gauge with a middle band | Percentile of today's ATR in the instrument's own history; the band is the middle half of history |
| Bars left and right of a close line, with whiskers | Median move below and above the close to the period's end; whiskers are the middle half of past periods; thin lines are the other periods' medians |
| Table cell with a number, a short bar and a grade letter | The share for periods like today (number and bar) against the other periods at the same point (thin line), with its grade |
| Highlighted bar or label | The current (or next) coordinate in time |

## Structure

After the title, a one-sentence lede and the market switch:

1. **At a glance** (the decision board): six tiles.
   - *How far does it move?* ATR now, its percentile in the instrument's history (gauge), and a ladder of magnitudes on one scale: average bar, busiest bar, average day close to close, ATR now, average day high to low.
   - *When does it move?* The intraday volatility profile with the current or next slot highlighted, and where the day's high and low form in the current window against a random walk.
   - *Where does it stand?* Range tracks for the week, month and quarter, with distances in ATR.
   - *Which levels are in reach?* All untested levels on one ATR axis (highs above the line, lows below), and the nearest high above and low below with reach odds within 5, 20 and 60 sessions.
   - *What can be made or lost from here?* The median move above and below the close to the end of the week (figure and fan chart), and a table with the week, month and quarter side by side, each with the number of past periods it rests on: typical moves in ATR and percent, six graded shares (1 and 2 ATR above and below, ended above or below) against other periods at the same point, and the shares that ended beyond the reader's own trading cost, chosen from sourced exchange and broker profiles or typed in (remembered in the browser, descriptive only).
   - *What does the evidence support?* How many of the market's effects tested against a control are graded A or B, the distribution of grades, and the three strongest effects with their controls.
2. **Time**: the calendar coordinates of the current or next session (session window, day of the week, month, quarter and year), each with a small profile chart (current coordinate highlighted) and the graded facts for that coordinate.
3. **Space**: the grid of horizons against their reference ranges, the untested-levels ladder and table, and the revisit curves (how soon prior highs and lows are traded again, against arbitrary levels).
4. **Findings**, the evidence library: every question, grouped by Time and Space, graded findings first.
5. **Method, Data, Register, About.**

A close-only index reference (SPX, NDX) shows only the evidence tile and a note that positions, levels and intraday timing are shown for the tradable funds.

## Numbers a trader reads without a glossary

- Differences of percentages are written as **pts** (percentage points) and always next to the two numbers they come from: "87% observed against 83% for arbitrary levels".
- Volatility effects are shown as relative movement ("+44% against the average half-hour") and as typical ranges in percent of price.
- Distances are in percent of the last close and in ATR. Price levels are never shown (`docs/DATA_POLICY.md`).
- The method section ends with a short glossary (pts, bps, control, ATR, grade, recent check).

## Readable charts

No chart text may overlap other text or a dot, at any width from 360 to 1920 px (`specs/0002-readable-charts.md`). Labels are laid out with at least 16 px between them; a label moved away from its point is joined to it by a leader line; dots that would touch are stacked; notes that do not belong to a single mark are written as captions under the chart, not inside it. Axis labels are thinned until they no longer touch. `tools/render_check.py` measures every chart on the rendered page and fails on any overlap, and on any tile whose content is wider than the tile itself (clipped content).

## Confidence

- Every grade is shown with its meaning ("strong evidence", "no reliable difference from the control", "not enough history yet: 18 past quarters").
- Within each findings group, graded findings come first and strongest first; questions without enough history are kept, collapsed at the end with the reason. Facts without enough history are shown muted in the Time panel.
- The board's evidence tile states the failure rate openly: most tested patterns are not graded A or B, and saying so is part of the product.

## Principles

1. **Decisions first.** The board comes before the detail; the detail is one click away from every tile.
2. **Evidence before decoration.** Colour encodes evidence strength and data status only, plus two side colours used consistently for levels (highs in the time colour, lows in brass). No gradients, glows or ornamental colour.
3. **Honest copy.** Plain verbs, sentence case, no claims a statistic cannot support. "No signals" and "no promises" are part of the page, not fine print.
4. **Fast by construction.** Static HTML, one stylesheet, one script, one self-hosted variable font, no framework, no third-party requests, no tracking. A test fails the build if the page references an external script, style or font.
5. **One motion moment.** On load, the elapsed-time bars grow and the range markers settle. Nothing else moves on its own, and `prefers-reduced-motion` turns it off.
6. **Accessible.** Visible keyboard focus, text contrast of at least 4.5:1 for body text, semantic headings, labelled figures (`role="img"` with a text alternative), and layouts that work from 360 px wide. Charts are redrawn with fewer labels below 720 px.

## Tokens

Defined as custom properties in `web/assets/styles.css`. Dark is the default; light follows `prefers-color-scheme`.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#0d1828` ink blue | `#f3f5f7` | Page background |
| `--raise` | `#122036` | `#ffffff` | Tiles, the grid and raised surfaces |
| `--sunk` | `#0a1422` | `#e9edf2` | Inactive zones, captions |
| `--text` | `#e8ecef` | `#102033` | Primary text, the current-coordinate outline, control lines |
| `--text-2` / `--muted` | `#b9c4d2` / `#8392a8` | `#33465e` / `#5c6b80` | Secondary and tertiary text |
| `--brass` | `#cdae72` | `#8f6a2c` | Evidence strength, the selected market, lows |
| `--time` | `#8fb7d8` | `#2f6c9e` | Time elapsed, highs, fresh data, the normal-day band |
| `--contra` | `#d07a6e` | `#b4483b` | Contradicted findings (grade F) and stale data only |

**Evidence scale.** Grades use one hue whose strength rises with the evidence: A, B and C are brass at decreasing intensity, D is a neutral slate, F is the contradiction red, N/A is empty. The evidence meter repeats the grade as filled segments (A five, B four, C three, D two, F one, N/A none), so the grade never depends on colour alone.

## Type

- **Instrument Sans** (variable, weight 400–700, width 75–100%), self-hosted from `web/assets/fonts/` under the SIL Open Font License (`OFL-instrument-sans.txt`). One family; personality comes from the width axis.
- Display and section titles: weight 500, width 78–82%, tight tracking (−0.025em to −0.01em). Tile figures: 46 px, width 80%.
- Body: 16 px, line height 1.6, lines under 75 characters.
- All figures use tabular numerals so columns of rates align.
- Not used: all-caps labels, eyebrow labels above headings, monospace data labels, arrows appended to links.

## Layout

```
bar      mark  Findings Method Data Register About                    data status
hero     Time–Space Intelligence
         one-sentence lede
         SPY  QQQ  BTC  ETH      Index references  SPX  NDX
board    At a glance · market, last close, next session              market data status
         ┌ How far does it move? ┬ When does it move? (two columns)          ┐
         │ 1.13% · gauge · ladder │ +44% · intraday profile · day high/low    │
         ├ Where does it stand?  ┼ Which levels are in reach? (two columns)  ┤
         │ week, month, quarter  │ ATR axis · nearest high and low · odds    │
         ├ What can be made or lost from here? (full width, week/month/quarter) ┤
         │ +0.9 / −0.9 ATR · fan chart  │ six shares, bar and control line   │
         ├ What does the evidence support? (full width)                      ┤
         │ 25 of 111 · grade bar │ three strongest effects, bar and control  │
         └────────────────────────────────────────────────────────────────────┘
time     session · day of week · month · quarter and year, each with a profile chart
space    grid of horizons · untested levels (ladder and table) · revisit curves
findings index (sticky) │ evidence library
method · data · register · about · footer
```

Content sits on a 1200 px column with 32 px gutters (16 px on phones). Tiles are separated by hairlines drawn by the grid gap, not by cards with shadows. Below 1020 px the board has two columns; below 720 px one.

## Instrument order

ADR 0049 (with Ether added by ADR 0056): SPY, QQQ, Bitcoin and Ether are the primary markets of the switch; SPX and NDX appear as labelled index references. Statistics of different instruments are never combined on the page.

## Checking a change

1. `tsip report` on a data store (or a synthetic one), then `tsip site --report <report.json> --out dist`. Check with the latest published report too (from the `report-archive` branch), so real values are reviewed, and with a report built by the current code, so new fields are reviewed.
2. Run `python tools/render_check.py --site dist` (390 to 1920 px, both colour schemes, an equity, a crypto market and a close-only index): it fails on console errors, horizontal scroll and overlapping chart text. Then look at desktop (1440 px) and phone (390 px) yourself.
3. `pytest` includes the self-contained site test and the board structure test.
