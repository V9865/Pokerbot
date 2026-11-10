---
name: project-memory
description: How to read and update this project's persistent memory in memory\PROJECT_MEMORY.md and memory\RESULTS_LOG.md. Use at the start of every conversation, after every batch of matches, at the end of every phase, and whenever the user asks where things stand or to resume work.
---
# Project memory

Antigravity does not reliably remember earlier conversations. Everything that
must survive lives in two files in the repository.

## memory\PROJECT_MEMORY.md (read first, every conversation)
Sections, in this order. Keep the file under 300 lines; summarise old detail.
1. Status: current phase, current snapshot, what is uploaded, what is in progress.
2. Next step: the single next action, concrete enough to start without questions.
3. Decisions: dated one-liners - what was decided, why, by whom (user or agent).
4. Facts and lessons: measured numbers, things that failed and why, traps.
5. Open questions: for the user or the organisers.
6. Change log: one line per accepted or reverted change with its measured effect.

## memory\RESULTS_LOG.md (append only)
For every harness batch: date and time, bot version or change tested, the
command, and the table as printed. Never rewrite old entries.

## Rules
- Update memory BEFORE the final message of a phase, then commit.
- Record failures too. "Tried X, lost 0.4 chips per hand to gto_like, reverted"
  saves the next conversation from repeating it.
- If the user states a preference or a decision, write it under Decisions
  immediately.
- To resume: read PROJECT_MEMORY.md, run `git log --oneline -10` and
  `git status`, summarise in five lines, and wait for the user's go-ahead before
  changing code.
