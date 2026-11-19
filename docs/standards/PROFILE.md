# Project profile: `quant`

Version 2.4.0. Adds to the [project standards](PROJECT_STANDARDS.md) and never relaxes them.
Default data class: **Internal** ([Data classification](DATA_CLASSIFICATION.md)).

## Rules every profile shares

1. The entry point is `CONTRIBUTING.md`. It names the profile, the owner, the data
   class and the lifecycle state: Proposed, Active, Maintenance or Archived.
2. The active specification follows the [specification template](templates/SPEC_TEMPLATE.md)
   or records why a project convention replaces it.
3. A claim of a result links a verification record based on the
   [verification template](templates/VERIFICATION_TEMPLATE.md).

## Rules for `quant`

1. A study states its hypothesis, data source, data license, sample period and
   the result that would reject it before any result is computed.
2. Every reported result separates in-sample from out-of-sample evidence and
   states transaction costs, slippage and the number of variants tried.
3. Features use only information available at the decision time. The
   verification record states how look-ahead was checked.
4. No claim of an edge is published without a verification record reviewed by
   someone other than its author.
5. The repository never places live orders or holds brokerage credentials.
