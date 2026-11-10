---
name: phase-0-verify
description: Phase 0 of the pokerbot build - verify the delivered kit and the v1 bot on this Windows machine, set up git, and confirm v1 is safe to upload. Use when the user says to start, to run phase 0, or to verify the kit.
---
# Phase 0: verify the kit (about 20 minutes, no changes to src\)

1. Read memory\PROJECT_MEMORY.md. Skim the skills discard-holdem-rules,
   poker-strategy, bot-safety and match-testing.
2. Environment. Show the output of each:
   - `py -3.11 --version`
   - `py -3.11 -c "import numpy, scipy; print(numpy.__version__, scipy.__version__)"`
     (if this fails: `py -3.11 -m pip install numpy scipy`)
   - `git --version`
   - the number of CPU cores
3. Check that the starter kit is present: starter\engine.py,
   starter\bot.py, starter\example_bots\random_bot.py. If they are missing,
   stop and ask the user to copy the starter kit into starter\.
4. Run, in this order, and show each result line:
   - `py -3.11 tools\test_evaluator.py` (RESULT: OK; takes a few minutes)
   - `py -3.11 tools\test_history.py` (RESULT: OK)
   - `py -3.11 tools\bundle.py` (rebuilds dist\bot.py)
   - `py -3.11 tools\fuzz_protocol.py` (RESULT: OK)
   - `py -3.11 tools\fuzz_protocol.py dist\bot.py 1500 250 --no-numpy` (RESULT: OK)
   - `py -3.11 tools\timing_report.py --stage 1` and `--stage 2` (RESULT: OK)
   - `py -3.11 tools\run_matches.py --opps all --seeds 1-3 --tag phase0`
5. Compare the harness table with the v1 reference table in match-testing
   section 5. Every matchup should be won; chips per hand should be in the same
   region. Report any matchup that is lost or any problem line.
6. If this folder is not a git repository: `git init`, then commit everything
   as "phase 0: verified kit" (runs\ is ignored).
7. Compare starter\engine.py with the skill discard-holdem-rules and list any
   rule the skill gets wrong or omits. Do not edit the skill; report.
8. Update memory (Status, Next step, the machine's timing numbers, the results
   table in RESULTS_LOG.md) and commit.

Stop and report: versions, each test result, the results table, timing as a
percentage of the bank, and the differences list. If everything passed, tell
the user: "dist\bot.py (v1) is verified and ready to upload."
