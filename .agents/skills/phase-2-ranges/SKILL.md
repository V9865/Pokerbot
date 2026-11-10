---
name: phase-2-ranges
description: Phase 2 of the pokerbot build - replace the range-narrowing heuristic with a Bayesian opponent range (3-card weights before the discard, an exact list of at most 990 hands after it) and learn the opponent's discard rule from showdowns. Use when the user says to run phase 2 or to build the range model.
---
# Phase 2: Bayesian range and discard reading (about 2.5 hours)

Read first: poker-strategy sections 2, 5 and 6; bot-safety section 3.
Plan before coding: write an implementation plan and show it to the user.

Build:
1. src\ranges.py (add "ranges" to ORDER in tools\bundle.py before "strategy"):
   a. At import: numpy arrays for all 22,100 three-card hands in hand_index
      order (the three card ids per hand) and their q values from PF_Q. Measure
      start-up; it must stay under 2 s. Guard everything with HAVE_NP.
   b. class Range3: weights over the 22,100 hands; mask(dead cards);
      apply_preflop(action, T values); sample(n, rng) -> (n, 3) card ids via
      cumulative weights and searchsorted.
   c. build_range2(range3, d, hole, board, flop_actions, posterior, opp_stats)
      -> (hands (M,2), weights (M,)) in the SAME ORDER as equity.opp_hands, with
      weight = W3 * L_flop * L_discard as in poker-strategy section 5.
   d. update_range2(weights, strength, action, T values) for turn and river.
   e. Weight floor and normalisation. Both discards are dead everywhere.
2. Discard-rule posterior (LOWEST / CHEAP / RANDOM) updated in observe() at
   each showdown from opp_hole_cards + opp_discard + board[:3]. Keep it cheap
   (three rule evaluations, no simulation).
3. strategy.py: build and update the range from the history on every request
   (rebuild from scratch from history each time; cache by history length).
   Pass Range3 samples to flop_equity(opp3=...) and Range2 weights to
   turn_equity / river_equity and top_share_equity. Keep read_history's x as
   the fallback for PANIC mode and no-numpy. Add a config switch USE_BAYES so
   variants can be A/B tested with `tools\bundle.py --set USE_BAYES=False`.
4. Our own discard: use equity against Range3; random choice between keeps
   within 0.01 (DISCARD_MIX_BAND).
5. tools\test_ranges.py:
   - weights are finite, non-negative and sum to 1; dead cards have weight 0
   - Range2 order equals equity.opp_hands order; at most 990 hands
   - with the posterior forced to LOWEST, an opponent discarding a king leaves
     over 95% of the weight on hands whose kept cards both rank K or A
   - after a preflop raise the mean q of the range falls; after a limp it rises
   - weighted river equity equals a brute-force weighted loop on 20 random spots
   - sampling Range3 never returns a dead card (10,000 samples)

Acceptance (show every table; log them in memory\RESULTS_LOG.md):
- all tests pass; fuzz OK in numpy and no-numpy modes; timing OK on both stages
- head-to-head against snapshots\v1_bot.py, seeds 1-40: passes the regression
  gate, and ideally is positive beyond the CI
- zoo, seeds 1-10: all matchups still won; none worse than v1 beyond 2x CI
- A/B: the same build with USE_BAYES=False against USE_BAYES=True, 40 seeds,
  to isolate the effect of the range model
If the Bayesian bot does not beat v1, do NOT ship it as default: report the
numbers, look at analyze_log for where it loses, tune the likelihood parameters
(w, floor, T defaults) on fresh seeds, and ask the user before spending more
than 45 minutes on it. v1 stays the uploaded version until v2 wins.

Then copy dist\bot.py to snapshots\v2_bot.py, update memory, commit
"phase 2: bayesian ranges", and tell the user whether to upload v2.
