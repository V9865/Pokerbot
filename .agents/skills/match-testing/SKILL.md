---
name: match-testing
description: How to measure the Discard Hold'em bot - the test opponents (zoo) including stand-ins for AI-coded and GTO-style bots, the parallel match harness, statistics and confidence intervals, the gates a change must pass, win targets, log analysis and timing reports. Use when running matches, judging whether a change helps, adding opponents, or reporting results.
---
# Match testing

## 1. The zoo (opponents\, already built)
| File | Behaviour | Stands in for |
| --- | --- | --- |
| station.py | check or call; discards the lowest card | the unmodified starter bot |
| random_bot.py | the starter kit's random bot | random entries |
| shover.py | all-in whenever a raise is legal | all-in bots |
| maniac.py | pot-size raise 70% of the time | hyper-aggressive bots |
| nit.py | plays the top 25%; bets only two pair or better | tight-passive bots |
| minraiser.py | min-raises 60% of the time | min-raise bots |
| ai_typical.py | equity vs a RANDOM hand, fixed thresholds, pot odds, cheap discard | the most common AI-written design |
| ai_typical_v2.py | same family with value raises, call margins, flop bluffs, simulated discard | a stronger AI-written design |
| gto_like.py | wide opens, minimum defence frequency, polarised bets with a fixed bluff ratio, two sizes, mixing, equity-max discard | "GTO + discard" bots |
| recorder.py | logs requests; used by tools\test_history.py | (test helper) |
| snapshots\vN_bot.py | our earlier versions | regression; the strongest opponent we have |
The zoo is OUR guess at the field. Winning against it is necessary, not
sufficient. The head-to-head result against our previous snapshot is the main
measure of real progress. Phase 3 adds opponents\exploiter.py (an adaptive bot
that attacks our patterns) to test robustness.

## 2. Harness
  py -3.11 tools\run_matches.py --opps all --seeds 1-10 --tag NAME
  py -3.11 tools\run_matches.py --opps gto_like,snapshots\v1_bot.py --seeds 1-40 --tag NAME
  options: --bot PATH (default dist\bot.py), --stage 2, --jobs N, --hands N
- Our bot is seat A; the engine swaps seats and cards in leg 2 by itself.
- Output per opponent: matches, W-D-L, mean chips per hand, 95% CI, mean capped
  score per hand (the tie-break), and problems. results.csv under runs\NAME\.
- Exit code 1 if our bot produced any notice, forfeit or traceback.
- Append every table to memory\RESULTS_LOG.md with the date, the version and
  the change being tested.
- The "time s" column is the engine's figure and is unreliable (see the rules
  skill). For timing use tools\timing_report.py, which runs serially.
- About 1.3 s per match per core on the reference machine for fast opponents;
  the ai_typical family and gto_like take a few seconds each.

## 3. Statistics
- Per-match results vary a lot. Compare versions on the SAME seeds and read the
  95% CI. A difference inside the CI is noise; say so.
- 10 seeds = 4,000 hands: enough to see a bug or a big effect. 40 seeds =
  16,000 hands: needed to confirm an effect of about 0.3 chips per hand.
- Use fresh seeds (1000+) for a final check against tuning to seeds 1-40.

## 4. Gates for keeping a change
1. Safety: harness exit code 0; fuzz OK; timing OK.
2. Regression: head-to-head against the previous snapshot over 40 seeds:
   wins >= losses and mean chips per hand above -0.2.
3. Improvement: the head-to-head mean is positive beyond its CI, OR at least
   one zoo matchup improves beyond its CI with none worse beyond 2x its CI.
If a change helps one matchup and hurts another beyond the CI, stop and ask the
user, showing both numbers. Revert anything that fails a gate.

## 5. Reference results for v1 (built on Linux, Python 3.11, seeds 1-10)
| Opponent | W-D-L | Chips per hand | 95% CI |
| --- | --- | --- | --- |
| station | 10-0-0 | +14.83 | 0.63 |
| random_bot | 10-0-0 | +9.97 | 1.51 |
| shover | 10-0-0 | +22.28 | 2.60 |
| maniac | 10-0-0 | +30.55 | 2.81 |
| nit | 10-0-0 | +1.85 | 0.62 |
| minraiser | 10-0-0 | +35.31 | 1.61 |
| ai_typical | 10-0-0 | +7.40 | 1.38 |
| ai_typical_v2 | 10-0-0 | +7.65 | 1.21 |
| gto_like | 10-0-0 | +2.82 | 0.85 |
Random numbers differ between machines, so expect similar, not identical, values.
Targets from here: keep every zoo matchup winning; beat each previous snapshot
head-to-head; lose no more than 0.5 chips per hand to opponents\exploiter.py.

## 6. Log analysis
  py -3.11 tools\analyze_log.py runs\NAME gto_like --worst 20
Groups hands by how they ended (who folded, street, seat, pot size) with chip
totals, then lists the worst hands. The log line shows both players' 3 cards,
the board, both discards and every action (x check, cN call to N, rN raise to
N, f fold). Known v1 leak to start from: "we folded on the river" in medium
and big pots against gto_like - chips put in on earlier streets and given up.

## 7. Timing
  py -3.11 tools\timing_report.py --stage 1
  py -3.11 tools\timing_report.py --stage 2
Serial matches against maniac and gto_like (the most decisions per hand).
Reads think_s and max_reply_ms from our SUMMARY line. Fails above 40% of the
bank or 250 ms.

## 8. Other tests
- tools\test_evaluator.py: evaluator against the engine, plus batch = scalar.
- tools\test_history.py: our pot reconstruction against real engine requests.
- tools\fuzz_protocol.py: random valid requests plus junk; legality, speed, exit.
Add a test for every new module (for example tools\test_ranges.py in Phase 2).
