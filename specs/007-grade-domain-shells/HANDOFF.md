# Handing 007 to an implementer model

## Before anything else

1. Read [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md). **T003, T005, T006, T008, and
   T009 are blocked** on unresolved geological questions and must not be
   implemented until those are answered there. T002 and T004 are ready.
2. Read `backend/src/services/compositing.py` and
   `backend/tests/unit/test_compositing.py`. T001 is implemented and is the
   canonical reference for style, docstring depth, test structure, and fixture
   philosophy. Match it.

## The rule that matters most

**One task per session. Tests green before the next file is opened.**

These tasks are ordered so that every one of T001–T007 is a pure function with
a fixed signature and hand-computed test fixtures. That structure exists
specifically so a cheaper model can be checked objectively instead of trusted.
Feeding several task files at once destroys that property — the model starts
inventing cross-task shortcuts and the fixtures stop catching them.

## Prompt to use per task

> Read `specs/007-grade-domain-shells/tasks.md` in full, then
> `specs/007-grade-domain-shells/tasks/T00N_<name>.md` in full.
> Implement exactly what T00N specifies — the deliverable files, nothing more.
> Do not modify files outside T00N's deliverables list.
> Every numeric fixture in the task file is hand-computed and authoritative: if
> your implementation disagrees with a stated fixture, your implementation is
> wrong.
> `backend/src/services/compositing.py` and its test file are the reference
> for style and test structure — match their docstring depth and fixture
> approach.
> If any requirement is ambiguous, **stop and report the ambiguity** — do not
> invent a rule, a default, a cut-off, a weighting, or a convention.
> Then run:
> `venv/Scripts/python.exe -m pytest backend/tests -q -c backend/pytest.ini`
> and report the output.

For T009, run the frontend tests instead:
`npm --prefix frontend test`

## Verification gate between tasks

Before starting T00N+1, confirm:

1. The full backend suite passes, not just the new file. A green new test with
   three pre-existing tests broken is a net loss.
2. `git diff --stat` touches only the files in T00N's deliverables table.
3. `backend/requirements.txt` gained nothing except `numpy` (T005) and
   `scikit-image` (T006).
4. Spot-check one fixture by hand. The failure mode with cheap models is not a
   broken test — it is a test quietly rewritten to match wrong output. Pick a
   fixture with a stated number (`7.5/7.6` in T003, `0.375` in T007,
   `3.333…`/`2.0` in T005) and confirm the assertion still contains that number.

## The five bugs to grep for after each task

These are specific to this codebase and this domain, and every one of them
produces plausible-looking output:

```bash
grep -rn "grade or 0" backend/src/services/          # NULL treated as zero
grep -rn "superseded_by" backend/src/services/       # must appear in T004 queries
grep -rn "nan_to_num\|np.nan_to_num" backend/src/    # unestimated nodes zero-filled
```

Plus two that need eyes rather than grep:

- **Axis swap.** Any backend code putting northing into `z`. T004 F3 and T006
  F3 catch it; confirm those tests exist and assert the values stated.
- **Dip sign.** Any code assuming dip is positive downward. T004 F1's
  elevation must *decrease* with depth.

## What is deliberately not in these tasks

Variography, kriging, block models, tonnage, grade estimation, resource
classification. If the implementer proposes any of them, the answer is no —
this feature produces a domain envelope, not a resource. Scope creep here is
not just extra work, it is output that would be mistaken for a resource
estimate.
