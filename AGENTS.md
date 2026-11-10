# Discard Hold'em Pokerbot: project rules

These rules are always on. Keep this file short; details live in the skills
under `.agents\skills\` and in `memory\PROJECT_MEMORY.md`.

## Goal
Win the Pokerbots competition (Discard Hold'em, heads-up no-limit, Python 3.11).
We submit ONE file, `dist\bot.py` (standard library + numpy + scipy, under 5 MB).
Official deadline: 15 Nov 2026 23:59 IST. Our target: final upload by 11 Nov evening,
with a valid upload after every phase.

A working, tested bot (v1) is already in this repository. The job is to verify it
on this machine and then make it stronger, phase by phase, WITHOUT ever breaking it.

## Memory protocol (every conversation, no exceptions)
1. FIRST read `memory\PROJECT_MEMORY.md`. It is the source of truth for status,
   decisions and lessons. Do not rely on conversation history or knowledge items.
2. After every batch of matches, append the results table to `memory\RESULTS_LOG.md`.
3. At the end of every phase (or before stopping for any reason) update
   `memory\PROJECT_MEMORY.md`: Status, Next step, Decisions, Lessons. Then commit.
4. If memory and code disagree, trust the code, fix the memory, and say so.

## Hard rules (breaking one can forfeit matches or disqualify the team)
1. stdout carries only protocol JSON: one line per reply, flushed. `safety.py`
   redirects `sys.stdout` to stderr at import; replies go out only through `send()`.
2. Reply to every `action_request` and `discard_request`. Budget: under 40% of the
   time bank per leg, no single reply over 250 ms (the hard limit is 5 s).
3. Every reply passes through `sanitize_action` / `sanitize_discard`. Any exception
   leads to a fallback reply. No exception may escape the loop in `main.py`.
4. Ignore unknown message types and fields. Exit after `match_end` or on end of input.
5. In the bot (`src\`): no file access, no network, no subprocesses, no threads, no
   multiprocessing, no state across legs. Tools and test opponents may use them.
6. Never try to detect duplicate deals or pass information between legs (Rulebook 10.3).
7. Only stdlib, numpy, scipy. Python 3.11 syntax. Plain numpy calls that exist in
   numpy 1.24 and later. The bot must also run WITHOUT numpy (degraded mode).
8. Our own code only. Never copy code from public poker-bot repositories
   (Rulebook 10.1). Published algorithms are fine.
9. Never edit `dist\bot.py` by hand; it is built by `tools\bundle.py`.
10. Never weaken a test, a gate or a hard rule to make a change pass.
11. Never upload a variant built with --set or --params. Only dist\bot.py built from src\ after a stage is accepted.

## Working rules
- Run Python as `py -3.11`. Run commands from the workspace root.
- Before working on an area read its skill: rules -> `discard-holdem-rules`;
  decisions -> `poker-strategy`; protocol, timing, bundling -> `bot-safety`;
  tests and acceptance -> `match-testing`.
- Phases are skills: phase-0-verify, phase-1-harden, phase-2-features,
  phase-3-policy, phase-4-train, phase-5-submit. Do one phase per
  conversation, in order, and stop at its checkpoint. The trained policy is
  described in the skill training-method.
- Every tunable number lives in `src\config.py` with a one-line comment.
- After ANY change in `src\`: `py -3.11 tools\bundle.py`, then
  `py -3.11 tools\fuzz_protocol.py`, then a smoke batch
  (`py -3.11 tools\run_matches.py --opps station,gto_like --seeds 1-2 --tag smoke`).
  Zero notices, zero tracebacks, zero forfeits.
- A strategy change is kept only if it passes the gates in `match-testing`
  (safety, regression against the previous snapshot, improvement). Otherwise revert it.
- One change at a time. Measure, then keep or revert. Record the result either way.
- New modules must be added to `ORDER` in `tools\bundle.py`. Project modules import
  each other only as `from <module> import <names>` on one line at the top.
- Commit after each accepted change and each phase: `phase N: <summary>`.
- When a choice belongs to the user (playing style, a trade-off between matchups,
  anything irreversible) stop and ask, giving the options and a recommendation.
- Bot stderr: errors plus the end-of-leg SUMMARY line only (64 KB limit per leg).

## Layout
- `src\` bot modules: config, cards, evaluator, preflop_table (generated), safety,
  equity, strategy, main
- `tools\` bundle, build_preflop_table, run_matches, fuzz_protocol, test_evaluator,
  test_history, analyze_log, timing_report
- `opponents\` test opponents (the zoo); `starter\` the organisers' kit (engine.py)
- `dist\bot.py` the submission; `snapshots\vN_bot.py` every uploaded version
- `memory\` project memory; `runs\` match logs (git-ignored); `docs\` the PDFs
