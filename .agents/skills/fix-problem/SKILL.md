---
name: fix-problem
description: Procedures for when something goes wrong with the Discard Hold'em bot - a notice, crash, traceback or forfeit; the bot being too slow; a matchup that loses or regresses; a phase that made things worse. Use when the user reports a problem or a gate fails.
---
# Fixing problems

## A notice, traceback, crash or forfeit
1. Reproduce with the same opponent and seed:
   `py -3.11 starter\engine.py dist\bot.py opponents\<opp>.py --seed <S> --log-dir runs\repro`
   and read runs\repro\A_leg*_stderr.txt and match.log.
2. Find the root cause in src\. Do not paper over it with a wider try/except.
3. Add a test that would have caught it (extend tools\fuzz_protocol.py or add a
   unit test in tools\).
4. Rebuild, rerun that seed, the fuzz test and the safety gate.
5. Do not change strategy in the same commit. Record it in memory under Lessons.

## Too slow (over 40% of the bank or a reply over 250 ms)
1. `py -3.11 tools\timing_report.py --stage 2` to confirm with no other load.
2. Profile a decision path with cProfile (drive src\strategy.py directly with a
   recorded request) and list the top 15 functions.
3. Reduce cost in this order: cache per hand; vectorise with numpy; fewer
   samples on small pots; move work out of observe(); lower MC_FLOP.
4. Show timing before and after. Decisions in FULL mode should change as
   little as possible.

## A matchup loses or regresses
1. `py -3.11 tools\run_matches.py --opps <opp> --seeds 1-30 --tag diag`
2. `py -3.11 tools\analyze_log.py runs\diag <opp> --worst 20`
3. State up to 3 hypotheses with evidence from the log lines.
4. Test one at a time on the same seeds; keep only what passes the gates in
   match-testing, including no regression elsewhere.

## A phase made things worse
`git log --oneline -10`, then `git revert` the offending commits (do not use
reset --hard without asking). Rebuild, rerun the safety gate, and write what
failed and why under Lessons in memory.
