# 3D Mining Tool — Planning Pipeline Workflow

## Overview

This project uses a **three-tier AI workflow** to build the Gold Prospect 3D Visualization Tool efficiently:

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLAUDE (Expert Model)                                              │
│  ► Reads master plan                                                │
│  ► Creates detailed specs & self-contained task files               │
│  ► Reviews all outputs from the cheap model                         │
│  ► Approves or sends back for revision                              │
└──────────────┬──────────────────────────────────┬───────────────────┘
               │ Creates task files               │ Reviews outputs
               ▼                                  ▲
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│  tasks/phase0/T00X_*.md      │──►│  outputs/phase0/T00X_output.md   │
│  (Self-contained specs)      │   │  (AI-generated code/docs)        │
└──────────────┬───────────────┘   └──────────────┬───────────────────┘
               │ You send to cheap AI             │ You paste output
               ▼                                  │
┌──────────────────────────────┐                  │
│  CHEAP AI MODEL              │──────────────────┘
│  (Haiku / GPT-4o-mini / etc) │
│  ► Receives task file        │
│  ► Generates code/docs       │
│  ► Returns output            │
└──────────────────────────────┘
```

---

## Step-by-Step Workflow

### Step 1: Pick the Next Task

Open `tasks/_task_index.md` and find the next task where:
- Status is `TODO`
- All dependencies are `DONE`

### Step 2: Send Task to Cheap AI

1. Open the task file (e.g., `tasks/phase0/T001_project_scaffold.md`)
2. Copy the **entire contents** of the file
3. Paste it into a new conversation with your cheap AI model
4. Wait for the output

> **Tip:** If the cheap AI asks questions instead of producing code, tell it: "Do not ask questions. Follow the task file exactly and produce all deliverables listed."

### Step 3: Save the Output

1. Copy the cheap AI's full response
2. Save it to `outputs/phase0/T001_output.md` (matching the task ID)
3. Update `tasks/_task_index.md`: set the task status to `SENT_TO_AI`

### Step 4: Request Claude Review

Tell Claude (expert model):

```
Review the output for Task T001. 
- Task file: F:\Monark\3D Mining Plan\tasks\phase0\T001_project_scaffold.md
- Output file: F:\Monark\3D Mining Plan\outputs\phase0\T001_output.md
Use the review template and save the review to reviews/phase0/T001_review.md
```

### Step 5: Handle Review Results

| Verdict | Action |
|---|---|
| ✅ **PASS** | Update task status to `DONE` in `_task_index.md`. Move to next task. |
| ⚠️ **PASS WITH CHANGES** | Use the revision instructions from the review file. Send them + the original output back to the cheap AI. Save revised output as `T001_output_v2.md`. Request re-review. |
| ❌ **FAIL — REDO** | Send the revision instructions from the review file to the cheap AI. May need to send the full task file again with the revision notes appended. |

### Step 6: Integration

After every 3-4 tasks are `DONE`, ask Claude to:

```
Check integration of completed tasks T001-T004. 
Verify the outputs work together and flag any interface mismatches.
Review folder: F:\Monark\3D Mining Plan\outputs\phase0\
```

---

## File Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Task file | `T{NNN}_{snake_case_name}.md` | `T001_project_scaffold.md` |
| Output | `T{NNN}_output.md` | `T001_output.md` |
| Revised output | `T{NNN}_output_v{N}.md` | `T001_output_v2.md` |
| Review | `T{NNN}_review.md` | `T001_review.md` |

---

## Tips for Best Results

1. **Never edit task files** after sending to cheap AI — if changes are needed, create a new version or add a revision appendix
2. **One task = one conversation** with the cheap AI. Don't stack multiple tasks.
3. **Order matters** — always follow the dependency chain in `_task_index.md`
4. **Keep outputs raw** — don't edit cheap AI outputs before review. Let Claude see exactly what was generated.
5. **Budget tracking** — note token counts per task to optimize cost over time

---

## Quick Reference: Asking Claude for Help

| Need | Prompt |
|---|---|
| Create a new spec | "Read the master plan section [X] and create a detailed spec at `specs/[name].md`" |
| Create a new task | "Break spec `specs/[name].md` into task files following the template" |
| Review an output | "Review task T00X output against its task file, save review to reviews/" |
| Integration check | "Check all DONE tasks in phase0 for interface compatibility" |
| Revise a task file | "Task T00X needs more detail on [area]. Update the task file." |
