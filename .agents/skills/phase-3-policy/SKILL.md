---
name: phase-3-policy
description: Phase 3 of the pokerbot build (update 1) - replace v1's if/else decision rules and fixed bet sizes with the parametric trained policy (EV-structured scores, learned parameters, softmax mixing), build the full opponent model and the adaptive exploiter test opponent, and verify the untrained policy starts level with v1. Use when the user says to run phase 3.
---
# Phase 3: the policy and the opponent model (about 4 hours)

Read first: memory, training-method (all), poker-strategy sections 7-9,
bot-safety. Use Plan mode: show the plan and wait for approval.

## Build
1. src\opponent.py (move OppModel here; add to ORDER before policy):
   every opponent feature in training-method section 1, updated from the
   history in hand_result, smoothed with priors; plus the discard posterior
   from Phase 2. Bet-size buckets: < 0.4, 0.4-0.8, 0.8-1.3, > 1.3 pot / all-in.
2. src\policy_params.py: PARAMS and BOUNDS for every parameter in
   training-method sections 2 and 3, with initial values that reproduce v1
   (document the mapping in comments, e.g. which v1 threshold each one replaces).
3. src\policy.py: the postflop policy (training-method section 2) and the
   preflop policy (section 3). Pure functions of (features, situation,
   opponent features, PARAMS, rng) returning an action dict. Vectorised where
   it matters; under 5 ms per decision.
   NOTE: Bet-size choice must include a multi-street value term (expected future
   bets when called, e.g. learned weight x pot growth on flop and turn) and must
   not be pure argmax during training (softmax with learned temperature over the
   candidate sizes {0.25, 0.33, 0.45, 0.60, 0.75, 1.00, 1.40}).
4. strategy.py: config switch POLICY = "learned" | "v1". "learned" calls
   policy.py; "v1" keeps the old code path (also the PANIC-mode fallback).
5. tools\bundle.py: add --params FILE.json (override PARAMS in a variant;
   refuse when the output is dist\bot.py). Add --set POLICY='"v1"' support
   check for A/B (strings must be quoted Python literals).
6. opponents\exploiter.py: built on ai_typical_v2. Tracks OUR fold-to-bet
   per street, our bet frequency and our showdown strength after big bets.
   Bluffs more when we fold more than 50%; calls down lighter when we bet more
   than 50%; folds more to our big bets when they have always been strong.
   opponents\exploiter2.py: the same with different thresholds (held out from
   training). Add both to ZOO.
7. tools\test_policy.py:
   - probabilities sum to 1 over legal actions only; illegal actions never chosen
   - nuts on the river, checked to: P(bet or all-in) > 0.8 under initial params
   - no equity, facing a pot-size river bet: P(fold) > 0.8
   - opponent folds 90% to big bets (synthetic stats): bet probability with
     e_show < 0.3 rises compared with a 10% folder
   - every parameter at its lower bound, then its upper bound: still legal
     replies and no exceptions on 2,000 random spots
   - timing: 1,000 decisions under 5 ms each on average

## Warm start check (no training yet)
- learned policy with initial params vs snapshots\v1_bot.py, seeds 1-40:
  mean within +-0.5 chips per hand. If worse, fix the structure (bug) first.
- zoo (including friend and exploiter), seeds 1-10: no matchup worse than v1
  beyond 2x CI.
- fuzz (normal and --no-numpy), timing (both stages) OK.

## Finish
Snapshot v3 (POLICY="learned", initial params), update memory with the warm
start numbers, commit "phase 3: policy". Upload only if it beats v2 or v1
head-to-head; otherwise keep the current upload. Then tell the user that
Phase 4 needs the laptop overnight.
