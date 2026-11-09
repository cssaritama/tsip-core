# 0020 · Decision interface, replay and review

Status: first-view prototype shipped through the normal site build when this change is deployed; pilot, replay and alerts are pending. Extends 0018. The first job is to prepare the next session for SPY.

| Work | Acceptance |
|---|---|
| W-93 · Default decision screen | At 1440 × 900 show instrument, cutoff/time zone, freshness, nearest valid reference on each side and the reason a comparison is absent. Show at most one independently cleared comparison. Keep market map, studies and methodology one click away. On phone, order is data state, two levels, evidence. Keyboard, deep links and touch work. Benchmark against the existing Cockpit using 0018. |
| W-94 · Point-in-time replay and decision log | Load by report fingerprint and instrument. Preserve timestamp, methodology version and data entitlement. The user may record prepare/wait, why and relevant scenario before outcomes become visible. An export reproduces the decision and evidence exactly. Verify replay against archive and distinguish dataset corrections from original snapshots. |
| W-95 · Watchlist and threshold alerts | Start with a user-owned watchlist and in-app alerts for freshness or a level-distance threshold. Specify trigger, evaluation interval, deduplication, delivery lag and pause behavior. Replay fixtures prove alerts do not use future bars. No trading action. |
| W-96 · Evidence and wording | Label observed frequency, incremental effect, prediction and modeled economics distinctly. Surface baseline, sample, interval and cutoff. Use “reference levels” for historical extrema. Keep “liquidity” for measured volume, depth, spread or a precisely documented proxy. Preserve zero and distinguish missing from no event. |

Proposed navigation: Brief → Scenario → Evidence; Research and Data remain explicit destinations. Run desktop, mobile, keyboard and stale/partial scenarios before replacing the default. Suppress current scenarios for stale or unsupported inputs, with historical replay still available.

Verification: SPY against a captured public report at 1440 and 390 px. Tested fresh, stale and degraded report statuses, keyboard disclosure, horizontal overflow and browser errors. Trader timing, screen-reader use and additional assets remain pilot work.
