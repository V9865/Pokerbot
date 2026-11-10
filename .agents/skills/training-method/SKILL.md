---
name: training-method
description: How the trained decision policy works and how it is trained - the feature set, the EV-structured policy with learned parameters, the preflop model, softmax action selection, the training population and objective, CMA-ES optimisation with common random numbers, staged training, validation on held-out seeds, and how to avoid overfitting. Use in phases 2, 3 and 4 and whenever changing the policy or the training tools.
---
# The trained policy and how it is trained

## 0. Why this design
A full solver or deep reinforcement learning is too slow and too risky before
the deadline (decided with the user, see memory). Instead, the hand-written
if/else thresholds of v1 are replaced by a policy with about 50-110 learned
parameters inside a structure that already knows poker arithmetic. Structure
makes training sample-efficient: the optimiser tunes how much to trust each
estimate, how opponents respond to each bet size, and small corrections,
rather than learning poker from nothing.

## 1. Inputs
- Hand features from src\features.py (phase-2-features Step 1).
- Situation: pot P, to_call, pot odds, stack-to-pot ratio (log), position
  (1 = in position), street, raises so far this street, whether we were the
  last aggressor on the previous street.
- Opponent features from src\opponent.py, all smoothed with a prior:
  fold / call / raise rate against each of our bet-size buckets, aggression
  per street, vpip, pfr, all-in rate, big-bet honesty (share of their big bets
  that showed a top-30% hand), discard posterior. Before enough data, the
  priors make them neutral.

## 2. Postflop policy (src\policy.py)
Candidate actions (only legal ones): fold, check or call, bet/raise of
F = {0.33, 0.66, 1.0, 1.5} pot, all-in. Raise amounts use
opp_bet + f * (pot + to_call), clamped; sizes that coincide collapse.

For each candidate, a score in units of the pot:
  passive (check/call):
    EV_c = R[street, pos] * e_show * (P + to_call) - to_call
  fold:
    EV_f = 0
  aggressive with size b:
    f_b  = sigmoid(a0[bucket] + a1 * logit(opp_fold_rate[bucket]) + a2 * street)
           (predicted chance they fold)
    e_c  = equity vs the strongest (1 - f_b) share of the range
           (top_share_equity), blended: e_c' = t * e_c + (1 - t) * e_show
    EV_b = f_b * P + (1 - f_b) * (R_b[street] * e_c' * (P + 2b) - b)
  score_a = EV_a / P + r_a . phi
  phi = [1, e_now, ehs2, ppot, npot, rank_in_range, block_top10, tex_flush,
         tex_straight, tex_paired, opp_aggr, opp_honesty] (12 values)
  r_a = learned residual weights per action class (passive, small bet
        <= 0.66, big bet >= 1.0, all-in, fold): 5 x 12 = 60, start at 0.
Selection: probabilities = softmax(score / tau) over legal actions; sample
from it (this is the mixing that hides our thresholds). tau is learned, with a
lower bound of 0.02. In PANIC mode, take the argmax of the v1 rules.
Learned structural parameters (about 30): R[street, pos] (6), R_b[street]
(3), a0[bucket] (4), a1, a2, t, tau, a commit threshold on e_c' for all-ins,
a call margin added to EV_c when to_call > 40% of the stack, bluff appetite
(a bias added to bets when e_show < 0.35), and the range-likelihood widths
w and floor from poker-strategy section 5 (they shape e_c).

## 3. Preflop policy
q = preflop percentile (0 best). For each decision level k (first in, vs a
limp, vs 1 raise, vs 2, vs 3+):
  P(raise) = sigmoid((theta_r[k] + c_r * opp_fold_pf - q) / s)
  P(call | not raise) = sigmoid((theta_c[k] + d * log(price) + c_c * opp_pfr - q) / s)
Raise sizes: first in, a learned size in {4..8}; re-raises x{2.5, 3, 3.5}
by learned choice. About 15 parameters.
Never fold the button for 1 chip (hard rule, not learned): measured equity
makes it wrong.

## 4. Parameters file
src\policy_params.py holds PARAMS (name -> value) and BOUNDS (name -> (lo, hi)).
Initial values reproduce v1 as closely as the structure allows. Before any
training, check the warm start: the untrained policy against
snapshots\v1_bot.py over 40 seeds should be about even. If it is clearly
worse, the structure has a bug: fix it before training.
tools\bundle.py gets an option --params FILE.json that overrides PARAMS in
the bundled file (variants for training; never for dist\bot.py).

## 5. Training population and objective
Opponents and weights (keep in tools\train_config.json):
| Opponent | Weight | Why |
| --- | --- | --- |
| friend | 3 | a real entry that beat v1 |
| snapshots\v1_bot.py | 2 | must keep beating our own baseline |
| current best (frozen at the start of each stage) | 2 | self-play pressure |
| exploiter | 2 | an adaptive bot that attacks our patterns |
| gto_like, ai_typical_v2 | 2 each | the two main families in the field |
| station, random_bot, shover, maniac, nit, minraiser, ai_typical | 1 each | weak bots must still be crushed |
Hold out from training (validation only): opponents\ai_typical.py and a second
exploiter variant (exploiter with different parameters), plus all seeds >= 5000.

Objective per candidate (maximise):
  F = sum_o w_o * mean over matches of tanh(net_chips_per_hand / 3) / sum_o w_o
tanh rewards winning each match and stops huge wins against weak bots from
dominating. Any notice, forfeit or traceback sets F = -10 for the candidate.

## 6. Optimiser: CMA-ES
- Tools only: `py -3.11 -m pip install cma` (allowed: tools are not the bot).
- Parameters are scaled to [0, 1] by their bounds; sigma0 = 0.15.
- Population 12-16. Every candidate in a generation plays the SAME seeds
  against the same opponents (common random numbers); the seed set changes
  every generation (seed = 1000 * generation + k). Fresh seeds stop the
  optimiser from fitting particular deals.
- Each candidate: 4 matches per opponent (about 50 matches). Short matches
  (--hands 100) in the first third of a stage, full length after.
- Re-evaluate the best candidate of each generation on 2x the matches before
  accepting it as the stage's best (noise protection).
- Checkpoint after every generation to runs\train\<stage>\gen_NNN.json
  (mean, sigma, best params, F); --resume continues from the latest one.
- Append one line per generation to memory\TRAINING_LOG.md.

## 7. Stages
| Stage | Trains | Dimensions | Generations | Typical time on 8 cores |
| --- | --- | --- | --- | --- |
| A | preflop parameters | ~15 | 15 | 1-2 h |
| B | postflop structural parameters | ~30 | 25 | 3-5 h (overnight) |
| C | residual weights r (L2 penalty 0.02 * sum r^2 subtracted from F) | 60 | 25 | 4-6 h (overnight) |
| D | opponent-response parameters (a0, a1, preflop c terms) with the exploiter weight raised to 4 | ~10 | 15 | 1-2 h |
Measure the first generation's time and scale generations to fit the night.
Stages C and D are optional if time runs out.

## 8. Accepting a stage
After each stage, validate the stage's best params (built with --params):
- held-out seeds 5000-5039 against: the previous snapshot, v1, friend,
  gto_like, ai_typical_v2, the held-out ai_typical and the second exploiter
- accept only if: head-to-head vs the previous snapshot is positive beyond
  its CI or at least not worse with a clear gain against friend; no opponent
  worse than the previous snapshot beyond 2x CI; safety and timing gates pass
- accepted -> write the params into src\policy_params.py, rebuild, snapshot
  vN, commit. Rejected -> keep the previous params; record why in memory.

## 9. Pitfalls
- Overfitting to the friend's bot: its weight is 3 of about 25; validation
  includes held-out opponents. If the friend's result improves while held-out
  opponents get worse, reject.
- Noise: never compare candidates on different seeds; never accept a stage on
  fewer than 40 validation seeds per opponent.
- Training uses the real engine through tools\run_matches.py logic (exact
  rules). Do not write a separate simulator unless profiling shows engine
  overhead above 30% of training time; if you do, it must reproduce the
  engine's results exactly on 200 recorded deals first.
- Antigravity conversations can time out on long commands. Training runs are
  started by the USER in a separate PowerShell window; the agent prepares the
  command, then analyses the checkpoints afterwards.
