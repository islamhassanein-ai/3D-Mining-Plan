# Review Template

> **Instructions for reviewer (Claude expert model):** Evaluate the AI-generated output against the original task file. Be specific about what must change vs what is merely a suggestion. Categorize every issue.

---

## Review Metadata

| Field | Value |
|---|---|
| **Task ID** | T000 |
| **Task Title** | [Title] |
| **Output File** | `outputs/phase0/T000_output.md` |
| **Review Date** | YYYY-MM-DD |
| **Overall Verdict** | ✅ PASS / ⚠️ PASS WITH CHANGES / ❌ FAIL — REDO |

---

## Acceptance Criteria Check

| AC # | Criterion | Result | Notes |
|---|---|---|---|
| AC-1 | [From task file] | ✅ Pass / ❌ Fail | [Details] |
| AC-2 | [From task file] | ✅ Pass / ❌ Fail | [Details] |
| AC-3 | [From task file] | ✅ Pass / ⚠️ Partial | [Details] |

---

## Architecture & Design Compliance

| Check | Status | Notes |
|---|---|---|
| Follows master plan architecture | ✅ / ❌ | |
| Consistent with related specs | ✅ / ❌ | |
| Interface contracts honored | ✅ / ❌ | |
| No unauthorized dependencies | ✅ / ❌ | |
| File paths match specification | ✅ / ❌ | |

---

## Code Quality Assessment

| Aspect | Rating (1-5) | Notes |
|---|---|---|
| Correctness | | |
| Error handling | | |
| Code clarity / readability | | |
| Naming conventions | | |
| Comments / documentation | | |
| Edge case coverage | | |

---

## Issues Found

### 🔴 Blocking (must fix before merge)

1. **[Issue title]**
   - **Location:** `file.py`, line XX
   - **Problem:** [What's wrong]
   - **Required fix:** [Specific instruction for the cheap AI to fix this]

### 🟡 Important (should fix, not blocking)

1. **[Issue title]**
   - **Location:** `file.py`, line XX
   - **Problem:** [What's wrong]
   - **Suggested fix:** [How to improve]

### 🟢 Suggestions (nice-to-have)

1. **[Suggestion]**

---

## Integration Notes

[Any concerns about how this output will integrate with other tasks' outputs. Flag potential conflicts early.]

---

## Revision Instructions

[If verdict is FAIL or PASS WITH CHANGES, write the exact prompt/instructions to send back to the cheap AI along with the output, so it can fix the issues. Be specific enough that the cheap model can act on this without re-reading the entire task file.]

```
REVISION REQUEST for Task T000:

Your previous output needs the following changes:

1. [Specific change 1]
2. [Specific change 2]

Do NOT change: [things that are correct and should be preserved]

Resubmit the complete updated code.
```
