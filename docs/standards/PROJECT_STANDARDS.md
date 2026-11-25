# Systems Studio Engineering Standard

Version 2.8.0, 26 November 2026. Read this file and [PROFILE.md](PROFILE.md) at
the start of each piece of work. Open the other files only when the task needs them.

## What we build

We design, build and operate production systems. Work is done when it runs in
its target environment: tested, observable, documented, reversible and owned.
Prototype, `research`, `coursework` and `competition` work says so in its entry
point, with what it would need to reach production.

## Rules that always apply

1. **Outcome first.** Each initiative's spec states the user, deliverable,
   measurable result, date and the condition that would show it is wrong.
2. **Ordered delivery.** Specify, research, plan, implement, verify, then
   review by someone who did not write the change and sees only the spec,
   the diff and the evidence. Fix findings and verify again.
3. **Report what happened.** Use PASS, FAIL, ERROR or NOT_RUN. Never present a
   planned or partial result as done.
4. **One home per fact.** The task list owns status, the spec behavior, the
   ADR the reason for a decision, the verification record the evidence.
5. **Resumable at every stop.** At each milestone, record the state, the
   evidence and one exact next action where the entry point says status lives.
6. **Authority.** Reversible work in scope proceeds through verification.
   Spending, production changes, submissions and external commitments need the
   owner's approval. Spending defaults to zero and grows only with results.
7. **Data stays in its class.** Secrets never enter Git. Follow
   [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) for everything else.
8. **Pull requests and authorship.** Changes go through pull requests and leave
   the default branch working.
9. **Language.** Artifacts are in American English. Talk to the owner in the
   language the entry point names.

## Read when the task needs it

| When you need to | Read |
| --- | --- |
| Start a spec, ADR, verification record or checkpoint | Copy a file from [templates/](templates/) to the project; never edit the template |

## Exceptions and upgrades

A project adds rules in its entry point and relaxes one only by a recorded
exception: rule, reason, owner, review date. Never edit these files, which
`adoption.json` verifies by hash. Upgrade through a reviewed pull request.
