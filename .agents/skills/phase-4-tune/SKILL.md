---
name: phase-4-tune
description: Phase 4 of the pokerbot build - evidence-driven tuning: find the costliest mistakes in the match logs, fix them one at a time, sweep a few parameters with A/B variants, and confirm Stage 2 timing and robustness on fresh seeds. Use when the user says to run phase 4 or to tune the bot.
---
# Phase 4: tuning (about 2 hours; stop when the time box ends)

Read first: match-testing. Work in small, measured steps. Log every result.

1. Leaks. For gto_like, ai_typical_v2, nit and the previous snapshot run 30
   seeds each, then `py -3.11 tools\analyze_log.py runs\<tag> <opp> --worst 20`.
   List the 5 costliest recurring patterns with chip totals and two example
   hands each. Start with the known one: chips lost by folding the river after
   calling earlier streets.
2. Fix one pattern at a time. After each fix: the affected matchups (30 seeds)
   and the regression gate against the previous snapshot (40 seeds). Keep only
   what passes; revert the rest. At most 6 iterations.
3. Parameter sweeps with variants (never edit config for a test):
   `py -3.11 tools\bundle.py runs\variants\NAME.py --set PARAM=VALUE`
   `py -3.11 tools\run_matches.py --bot runs\variants\NAME.py --opps snapshots\vN_bot.py,gto_like,ai_typical_v2 --seeds 1-40 --tag sw_NAME`
   Sweep at most 5 parameters, one step up and one down each. Adopt a value
   only if it wins head-to-head beyond the CI AND does not hurt gto_like or
   ai_typical_v2 beyond their CI. Self-play alone can mislead; require both.
   memory\PROJECT_MEMORY.md lists sweeps already done; do not repeat them.
4. Time headroom: v1 used about 7% of the bank. If under 25% after Phase 3, try
   MC_FLOP 3000 (less noise) and keep it if timing stays under 40%.
5. Stage 2: `py -3.11 tools\timing_report.py --stage 2`, then 3 seeds of
   Stage 2 matches against every zoo bot. Safety gate clean.
6. Overfitting check: every zoo bot and the previous snapshot on fresh seeds
   1000-1009. Results should agree with seeds 1-10 within the CIs.

Report a table of v1 -> ... -> v4 per opponent (chips per hand with CI, match
wins), the changes kept and reverted, and timing. Snapshot v4, update memory,
commit "phase 4: tuned", and tell the user whether to upload v4.
