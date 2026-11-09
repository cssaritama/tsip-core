# 0017 Institutional Execution and Risk Matrix (W-82)

**Status:** withdrawn (2026-11-09) · **Level:** 2 study · **Open work:** W-82, W-115 · **Decisions:** ADR 0064, ADR 0071 (proposed)

This specification was withdrawn before any study was built. Its first version stated results (shares, returns and money figures) that no code in this repository produces, without the control, holdout, bootstrap interval and grade that `docs/METHODOLOGY.md` requires, and in a few places inconsistent with each other and with earlier graded results. A specification states a question and a protocol before the run (`specs/README.md`, level 2); it does not report outcomes.

The question may be specified again from the template, with its control, test budget and a hypothesis registered in `registry/hypotheses.json` before the first run on real data. Until then nothing in it is a TSIP result. The page display was removed in `3de72ca`; with the stated inputs, quarter Kelly would be about 12.3%, so the 2% cap was a separate rule, and the void-fill frequency is a different endpoint from target-before-stop. The proposed desk workflow is [0018](0018-desk-brief-and-pilot.md).
