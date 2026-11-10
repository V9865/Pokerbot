---
name: phase-4-train
description: Phase 4 of the pokerbot build (update 1) - build the training tool and run staged CMA-ES training of the policy parameters against a weighted opponent population, with checkpoints, held-out validation and acceptance gates. Training runs overnight in a separate window started by the user. Use when the user says to run phase 4, to start or resume training, or to evaluate a training stage.
---
# Phase 4: training (tool: about 2 hours; runs: overnight)

Read first: memory, training-method (all), match-testing.

## Build tools\train.py
  py -3.11 tools\train.py --stage A|B|C|D [--gens N] [--pop N] [--jobs N]
                          [--hands N] [--resume] [--dry-run]
- Reads tools\train_config.json: opponents and weights (friend removed; rof_tight, rof_loose,
  rof_big, rof_small, raise_or_fold weight 2 each; snapshots\v1_1_bot.py weight 3),
  held-out opponents (friend, liar, ai_typical, 2nd exploiter; seeds >= 5000),
  which PARAMS each stage trains (others fixed at current src values),
  sigma0, population, matches per opponent, L2 penalty for stage C.
- Objective per match: score = 0.6 * tanh(n / 0.25) + 0.4 * clip(n, -1, 1),
  F = weighted mean of score over opponents. Notice, forfeit or traceback: F = -10.
- Train on Stage 1 length (200 hands/leg, 400 total) at least half of the time.
- Uses the `cma` package (`py -3.11 -m pip install cma`) on parameters scaled
  to [0, 1] by BOUNDS.
- For each candidate: write runs\train\<stage>\cand_<gen>_<i>.json, build a
  variant with `tools\bundle.py runs\train\<stage>\cand_<gen>_<i>.py --params ...`,
  play the generation's seed set against every training opponent with the
  run_matches logic (import its play() function; do not shell out per match
  more than needed), compute F (training-method section 5).
- Common random numbers: all candidates of a generation use the same seeds;
  seeds change every generation.
- Re-evaluate the generation's best on twice the matches.
- After every generation: checkpoint JSON, one line to memory\TRAINING_LOG.md
  (time, stage, gen, best F, mean F, sigma, matches played), and print it.
- --resume continues from the latest checkpoint after a crash or a reboot.
- --dry-run: one generation with population 4 and --hands 40, to test the
  pipeline in a few minutes.
- At the end: write runs\train\<stage>\best.json and print the validation
  command.
Also tools\validate_params.py runs\train\<stage>\best.json: the acceptance
runs of training-method section 8 (held-out seeds 5000-5039), printing the
gate results.

## Run (the user starts it; long commands time out inside conversations)
1. Agent: run `--dry-run` and fix any problem. Then measure one real
   generation of stage A and estimate the time per generation.
2. Agent: give the user the exact commands, sized to fit the time available,
   for example:
     py -3.11 tools\train.py --stage A --gens 15 --jobs 7
     py -3.11 tools\train.py --stage B --gens 25 --jobs 7
   (jobs = cores - 1, so the laptop stays usable)
3. User: runs them in a PowerShell window, laptop plugged in, sleep disabled.
4. Next conversation ("Resume from memory", then "evaluate stage A"):
   validate_params on best.json; accept or reject per training-method
   section 8 (replaces v1.1 only if on held-out seeds: no winning W-D-L becomes losing,
   capped chips improve on average, and friend Stage 1 AND Stage 2 are no worse than
   v1.1 within CI); if accepted, write PARAMS into src\policy_params.py, rebuild,
   run fuzz and timing, snapshot vN, commit, append to memory.
5. Repeat for B, then C and D if time allows. Each stage starts from the
   accepted params of the previous one.

## Report after each stage
A table per opponent (held-out seeds): previous snapshot vs new params, chips
per hand with CI, match wins; the F curve over generations (from
TRAINING_LOG.md); which parameters moved most and what that means in poker
terms (e.g. "bets bigger for value against callers"). Tell the user whether to
upload the new snapshot.
