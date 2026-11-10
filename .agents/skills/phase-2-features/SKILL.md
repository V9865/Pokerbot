---
name: phase-2-features
description: Phase 2 of the pokerbot build (update 1) - add the friend's bot as an opponent and diagnose the loss, compute the hand-strength features the trained policy needs (equity now and at showdown, EHS squared, positive and negative potential, strength against the top of the range, blockers, board texture, discard information), and add the Bayesian opponent range. Decisions stay the same as v1 in this phase. Use when the user says to run phase 2.
---
# Phase 2: diagnosis, features, Bayesian range (about 3-4 hours)

Read first: memory\PROJECT_MEMORY.md, the skills poker-strategy (sections 1, 2, 5, 6),
training-method (sections 1-2), bot-safety, match-testing.
Show an implementation plan before writing code.

## Step 0. The friend's bot (do this first; report before Step 1)
1. The user copies the friend's bot to opponents\friend.py. If it has several
   files, put them in opponents\friend\ and use opponents\friend\bot.py.
2. Check it runs: one match against opponents\station.py. If it crashes, times
   out or produces notices, tell the user; results against a broken bot mislead.
3. Add it to ZOO in tools\run_matches.py (as "friend" or "friend\bot") so
   `--opps all` includes it.
4. `py -3.11 tools\run_matches.py --opps friend --seeds 1-20 --tag friend_v1`
5. `py -3.11 tools\analyze_log.py runs\friend_v1 friend --worst 30`
6. Read the worst hands and describe, with chip totals:
   - how the friend's bot plays (preflop range, bet sizes, bluff frequency,
     discard rule, how often it folds to our bets)
   - where v1 loses the chips (e.g. folding too often to big bets, paying off
     strong hands, being bluffed on the river, losing at showdown after
     discarding badly)
7. Write the diagnosis into memory (Facts and lessons) and STOP. Show the user
   the diagnosis and wait for the go-ahead.

## Step 1. src\features.py (add to ORDER in tools\bundle.py before strategy)
compute features once per decision from our cards, the board, both discards
and the opponent's range weights (uniform until Step 2 is done). Everything is
a float in a known range. Define each in a docstring.
| Name | Meaning | Street |
| --- | --- | --- |
| e_show | equity at showdown vs the weighted range (existing functions) | all |
| e_now | P(we are ahead right now) vs the range, ties half | flop, turn |
| ehs2 | mean over future boards of (equity on that board)^2 | flop, turn |
| ppot | P(win at showdown given behind now) | flop, turn |
| npot | P(lose at showdown given ahead now) | flop, turn |
| e_top25, e_top50 | equity vs the strongest 25% / 50% of the range (top_share_equity) | all |
| rank_in_range | weighted share of their range that our current hand beats | all |
| block_top10 | share of the top 10% of their unconditioned range removed by our cards | all |
| tex_flush | 0, 0.5 or 1: no flush possible / flush draw possible / flush possible | all |
| tex_straight | same for straights | all |
| tex_paired | 1 if the board is paired | all |
| opp_disc_rank | opponent discard rank / 12 (0.5 before the discard) | turn, river |
| p_lowest | posterior that the opponent discards by the LOWEST rule | turn, river |
Implementation notes:
- Turn: extend equity.turn_equity to also return the per-(hand, river) result
  matrix; ehs2, ppot, npot follow from it and opp_now. Exact, no sampling.
- Flop: sample K = 40 runouts (turn, river) x up to N = 120 opponent hands
  drawn from the range; evaluate with eval_batch in one call (4,800 rows).
  Compare our best keep (from flop_equity) with their cheap-rule keep.
- River: e_now = e_show, ehs2 = e_show^2, ppot = npot = 0.
- Cache features per (hand_id, street, range_version).
- Budget: features under 15 ms per decision in FULL mode; PANIC mode returns
  cheap approximations (e_show from scalar_equity, the rest from the board).
- No numpy -> same cheap approximations.

## Step 2. Bayesian range
Implement poker-strategy section 5 (Range3 before the discard, Range2 of at
most 990 hands after it, turn and river updates) and the discard-rule posterior
of section 6, in src\ranges.py and src\opponent.py, exactly as the old phase-2
plan described:
- Range3 over the 22,100 hands in hand_index order; preflop likelihoods;
  sampling by cumulative weights.
- Range2 in the same order as equity.opp_hands; weight = W3 x L_flop x L_discard.
- Weight floor 0.05 x mean; never zero.
- Config switch USE_BAYES (True/False) for A/B tests.
- The features of Step 1 use these weights.

## Step 3. Tests
- tools\test_features.py: the nuts on the river gives e_show = 1; a made
  flush on the turn has npot near the share of boards that pair or fill a
  full house; a flush draw on the flop has ppot around 0.35; blockers: holding
  the ace of the flush suit raises block_top10 on a three-suited board;
  every feature finite and inside its range on 2,000 random spots.
- tools\test_ranges.py: as in the old plan (normalised weights, dead cards
  excluded, order matches opp_hands, the LOWEST-rule king test, weighted
  river equity equals brute force, sampling never returns dead cards).

## Acceptance (decisions still v1's)
- all tests, fuzz (normal and --no-numpy) and timing (both stages) OK;
  features must not push thinking time above 20% of the bank
- head-to-head against snapshots\v1_bot.py, seeds 1-40: regression gate
  (the only change to decisions is better equity from the range)
- friend, seeds 1-20: report the change against friend_v1
Snapshot v2, update memory, commit "phase 2: features and ranges". Tell the
user whether to upload v2 (only if it beats v1 head-to-head AND does better
against the friend's bot).
