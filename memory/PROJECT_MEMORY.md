# Project memory: Discard Hold'em pokerbot

Read this first in every conversation. Update it at the end of every phase.

## 1. Status
- Phase: Phase 0 (verify on this machine) complete and passed.
- Current bot: v1 = dist\bot.py = snapshots\v1_bot.py (snapshots\v0_bot.py is the
  same bot without the fold-rate exploits).
- Uploaded to Unstop: nothing yet (v1 ready for upload).
- Verified on Windows (Python 3.11.18, numpy 1.26.4, scipy 1.17.1, 20 logical cores).
  All test tools, bundle, fuzz, timing reports, and match runs passed with zero errors/notices/forfeits.
- v1 lost heavily to the user's friend's bot (11 Nov, no log kept).

## 2. Next step
Upload dist\bot.py (v1) to Unstop, then run phase-2-features Step 0 (friend's bot diagnosis).

## 3. Decisions
- 2026-11-10 (user): Windows laptop; build phase by phase; playing style
  exploit-first and safe; working alone; wants a finished bot by 11 Nov evening.
- 2026-11-10 (user): the bot must have an edge over AI-coded bots and over
  "GTO + discard" bots.
- 2026-11-10: equity-based bot with opponent modelling; no game-theory solver
  (cannot be built, abstracted and made fast enough in the time available).
- 2026-11-10: submit a single bundled file, dist\bot.py (avoids any question
  about how a zip is unpacked). The preflop table is embedded.
- 2026-11-10: numpy batch evaluator, so turn and river equity are exact; a
  pure-Python fallback keeps the bot alive if numpy is unavailable.
- 2026-11-10: objective is expected chips per decision. Duplicate deals cancel
  card luck across legs, so we do not trade EV for lower variance; caution is
  for model error only.
- 2026-11-10: the test zoo is our own guess at the field; head-to-head against
  our previous snapshot is the main measure of progress.
- 2026-11-10 (user):
  * hybrid plan: keep the safety shell and the math core; replace the
    if/else decision layer with a trained, EV-structured policy
    (training-method skill). No full rebuild (solver or deep RL rejected
    as too risky before the deadline).
  * the friend's bot is available and becomes a training and test opponent
    (weight 3 of about 25; overfitting guarded by held-out opponents).
  * laptop: 8+ cores, can train overnight.
  * final upload by 12-13 Nov; stages C and D of training are optional.

## 4. Facts and lessons
- Preflop equities are compressed: best hand 0.794, top 10% 0.596, median
  0.492, worst 0.306. Only pairs of aces are big favourites. Three of a kind
  in hand is among the worst holdings.
- Lowest-card discard costs 5.5 points of showdown equity against the cheap
  rule. Simulated discard gains only about 0.1 over the cheap rule: the edge
  is in reading the opponent's discard, not in choosing ours.
- eval_batch is about 0.4 us per hand; turn equity exact in about 10 ms; river
  0.3 ms; flop 1,500 samples in about 4-5 ms.
- v1 thinking time: about 2 s per 200-hand leg and 5 s per 500-hand leg
  (about 7% of the bank); max reply about 23 ms on Linux reference machine.
  On this Windows machine (20 cores, Python 3.11.18): Stage 1 think time 2.7-3.2 s
  per leg (9-11% of bank), max reply ~30 ms; Stage 2 think time 7.6-9.3 s per leg
  (10-12% of bank), max reply ~35.5 ms. All requests ran in mode FULL.
- The local engine prints "time used 0.00 s" when a leg finishes within the
  5 s start-up allowance. Use tools\timing_report.py instead.
- v1 results (seeds 1-10): 90 wins in 90 matches against the nine zoo bots; see
  the table in the match-testing skill and memory\RESULTS_LOG.md.
- v1 against v0 (fold-rate exploits on vs off): 5-5 over 10 seeds, +0.52
  chips per hand, CI 0.78. No significant difference in self-play; the
  exploits matter against bots that fold too much.
- Known leak: against gto_like, the largest loss category is folding the river
  in medium and big pots after calling earlier streets.
- Fuzz test "caught errors" come from deliberately inconsistent input (for
  example a preflop request while holding 2 cards). They end in a legal
  fallback reply. Zero such errors occur in real matches.
- No-numpy mode works: it beat ai_typical in a test match.
- A/B sweeps already done (variant against v1, 30 seeds, chips per hand):
  CALL_MARGIN 0.00 -> -0.22 (CI 0.18): worse, keep a margin.
  CALL_MARGIN 0.08 -> -0.21 (CI 0.25): not better than 0.04.
  Not yet swept: UNCERTAINTY, VALUE_MIN, RAISE_VALUE, CALLER_SHARE, OOP_PENALTY,
  the SHRINK_* values, the PF_* thresholds, MC_FLOP.

## 5. Open questions
- For the organisers: are the provisional limits final (time banks, 5 s reply
  limit, 1 vCPU, 1 GB, tie-break caps)? How fast is the tournament machine?
- For the organisers: which numpy version is installed on the server?

## 6. Change log
- 2026-11-10 v0: baseline (table preflop, exact turn/river equity, range
  narrowing heuristic, value-heavy betting, simulated discard).
- 2026-11-10 v1: + steal every button and bet when checked to once the
  opponent is shown to fold too much (EXPLOIT_* and PF_STEAL_* in config).
