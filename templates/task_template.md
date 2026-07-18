# Task File Template

> **Instructions for the AI model:** Read this entire file carefully before writing any code. Follow every specification exactly. Do not skip acceptance criteria. Ask for clarification only if a requirement is genuinely ambiguous — do not add features not listed here.

---

## Task Metadata

| Field | Value |
|---|---|
| **Task ID** | T000 |
| **Title** | [Descriptive title] |
| **Phase** | Phase 0 |
| **Priority** | P0 (Critical) / P1 (High) / P2 (Medium) |
| **Dependencies** | None / T001, T002 |
| **Estimated Complexity** | Small / Medium / Large |
| **Status** | TODO |

---

## Context

[Excerpt from the master plan relevant to this task. Include enough context that the AI model can understand WHY this task exists and HOW it fits into the larger system, without needing to read the entire master plan.]

---

## Objective

[1-2 sentence clear statement of what this task produces.]

---

## Detailed Requirements

### Functional Requirements

1. [Requirement 1]
2. [Requirement 2]
3. ...

### Technical Constraints

- **Language/Framework:** [e.g., Python 3.11+ / FastAPI]
- **Naming Conventions:** [e.g., snake_case for Python, camelCase for JS]
- **File Location:** [Exact path where output files should go]
- **Dependencies Allowed:** [List of packages/libraries the code may use]
- **Dependencies NOT Allowed:** [Anything explicitly excluded]

### Interface Contracts

[If this task produces something consumed by another task, define the interface here — function signatures, API shapes, data formats, etc.]

---

## Deliverables

List every file this task must produce:

| # | File Path | Description |
|---|---|---|
| 1 | `src/path/to/file.py` | [What it does] |
| 2 | `src/path/to/file2.py` | [What it does] |

---

## Acceptance Criteria

Each criterion will be checked during review. Code that fails any P0 criterion will be sent back for revision.

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | [Must-pass criterion] |
| AC-2 | P0 | [Must-pass criterion] |
| AC-3 | P1 | [Should-pass criterion] |

---

## Starter Code / Boilerplate

```
[Optional: provide skeleton code, schema DDL, or config templates to reduce ambiguity]
```

---

## Anti-Patterns to Avoid

- [Common mistake 1 that cheaper models tend to make for this kind of task]
- [Common mistake 2]

---

## References

- Master Plan Section: [Section number and title]
- Related Specs: [Link to spec files]
- Related Tasks: [T001, T003 — what they provide that this task depends on]
