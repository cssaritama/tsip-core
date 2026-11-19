# Verification — [Spec Number] [Short Title]

<!-- Verification record template, Systems Studio Engineering Standard 2.4.0.
     Copy this file next to the spec it verifies, for example
     specs/NNN-short-name/VERIFICATION.md. Record what actually happened. -->

- **Spec:** [link to SPEC.md]
- **Revision verified:** [commit hash]
- **Date:** [YYYY-MM-DD]
- **Verified by:** [name or role]
- **Reviewed by:** [a different person or a fresh review context]

## Results

| Acceptance ID | Check | Command or method | Result | Evidence |
| --- | --- | --- | --- | --- |
| A1 | [what was checked] | `[command]` | PASS / FAIL / ERROR / NOT_RUN | [log, file or link] |

Use NOT_RUN when a check could not run, and state the consequence below.

## Review findings

| Finding | Severity | Resolution | Re-verified at |
| --- | --- | --- | --- |
| [what the reviewer found] | Blocking / Minor | [fix or decision] | [commit hash] |

## Gaps and limitations

[What this verification does not prove, and why.]

## Verdict

[Accepted | Accepted with recorded gaps | Rejected], on revision [commit hash].
