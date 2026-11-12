# Project memory: Discard Hold'em pokerbot

Read this first in every conversation. Update it at the end of every phase.

## 1. Status
- Phase: Phase 4 Stage A complete and ACCEPTED (`T_mean`); `v4` (`dist\bot.py` = `snapshots\v4_bot.py`) replaces `v1.1`.
- Current bot: `v4` = `dist\bot.py` = `snapshots\v4_bot.py` (221,788 bytes; built from `src\policy_params.py` with `T_mean` parameters, no `--params`).
- Uploaded to Unstop: ready to upload `dist\bot.py` (`v4`); awaiting user upload confirmation.
- Benchmarks (Stage A validation on fresh seeds `90000+` vs `snapshots\v1_1_bot.py`):
  * Head-to-head vs `v1_1` (`seeds 90000-90039`, Stage 2): **31-0-9** (`+0.631 ± 0.227` chips/hand, capped **`+0.494`**), 0 problems.
  * Held-out average (`friend`, `liar`, `ai_typical`, `exploiter2` `seeds 90000-90019`, 30 `persona` `seeds 90000-90029`, Stage 1 & 2, 220 matches): **215/220 (97.73%)**, equal-opp avg capped **`+0.9362`** vs `v1_1` `+0.9089` (match-weighted `+0.9387` vs `+0.9172`, paired raw gain `+0.167 ± 0.214`), 0 win->loss flips.
  * `friend` held-out (`90000-90019`): Stage 1 **17-0-3** (`+1.50 ± 0.69`, cap `+0.69` vs `v1_1` `15-0-5`, `+0.44`, cap `+0.39`); Stage 2 **18-0-2** (`+1.44 ± 0.47`, cap `+0.77` vs `v1_1` `19-0-1`, `+1.20`, cap `+0.77`).
  * Safety bots (`station`, `random_bot`, `shover`, `maniac`, `minraiser`, Stage 2 `90000-90004`): **25-0-0** (`+1.00` cap all), 0 notices/forfeits/tracebacks.
  * Pre-upload gates on `v4` `dist\bot.py`: `test_policy` PASS (`0.251 ms/dec`), `test_history` PASS (`213/213`), `test_evaluator` PASS, `fuzz_protocol` (`3000` normal: max `28.7 ms`; `1500` `--no-numpy`: max `2.5 ms`) PASS, serial `timing_report` Stage 1 max `12.5%` bank (`42.3 ms`), Stage 2 max `12.1%` bank (`34.2 ms`), smoke batch `v4_smoke` (`all` 19 opps × `1-3`) **56-0-1** with 0 problems.

## 2. Next step
Upload `dist\bot.py` (`v4`) to Unstop if desired, then decide whether to run Stage B (postflop structural parameters, starting from accepted `v4` params) or move to Phase 5 final audit.

## 2b. Change log
- 2026-11-12 v4 (Phase 4 Stage A trained policy — accepted `T_mean`):
  * Ran 25 generations of Stage A CMA-ES (`pop=12`, 11 training opponents, 2 matches/opp = 6,600 matches total on `C:\pokerbot_runs\train\stage_a`) in 4.12 hours; 0 forfeits/notices/tracebacks.
  * Compared final-gen best (`T_best`, `best.json`) and final CMA-ES population mean (`T_mean`, `mean.json` from `cma_latest.pkl`) against `snapshots\v1_1_bot.py` on fresh paired seeds `90000+`. Both passed all Section 8 gates; accepted `T_mean` over `T_best` due to dominant H2H (`31-0-9`, `+0.631` vs `29-0-11`, `+0.250`), positive raw held-out gain (`+0.167` vs `-0.072`), and deterministic `TAU_BET = TAU_ACT = 0.02`.
  * Key trained moves (`PARAMS` in `src\policy_params.py`): `BETA_MULTI` `0.0 -> 0.2218` (multi-street value term on flop/turn), `PF_CALL_PFR_MULT` `1.30 -> 1.0081` (tighter BB calls vs button opens), `CALL_MARGIN` `0.04 -> 0.0224`, `BIG_CALL_MARGIN` `0.07 -> 0.1070`, `PF_CALL_Q_MED` `0.55 -> 0.4801`, `PF_OPEN_Q` `0.75 -> 0.7713`, `RANGE_BLEND` `0.0 -> 0.0292`, `TAU_BET = TAU_ACT = 0.02` (clamped at lower bound).
  * Training tooling fixes: kept `tools\train.py` seeds strictly `< 5000` (`100..4899`), saved `mean_params` / `mean.json` in JSON alongside checkpoints to avoid Python/NumPy pickle incompatibility across environments, and separated cap-saturated bots into post-stage validation (`C:\pokerbot_runs\`).
- 2026-11-11 v2 (Bayesian Opponent Ranges - Phase 2 Step 2):
  * Bayesian ranges: implemented `src/ranges.py` with `Range3` (22,100 combinations) and `Range2` (up to 990 combinations).
  * Preflop: `Range3` updates prior distribution based on learned button raise frequency `pfr_btn` from Fix C and action likelihoods.
  * Discard rule posterior: observes showdown discard choices, updates Dirichlet posterior over [LOWEST, CHEAP, RANDOM] discard policies, and weights `Range2` upon opponent discard reveal.
  * Postflop likelihoods: updates `Range2` on opponent turn/river actions using Fix A learned bet size meaning $s_k$ smoothed over $\pm 5$ percentile points with weight floor at 0.08, avoiding double-counting with `read_history` ($x = 1.0$ when Bayesian range is active).
  * Exact equity weighting: exact vectorized weights passed into `turn_equity` and `river_equity`, seamlessly integrated into `top_share_equity`.
  * Incremental history processing: history events processed incrementally per action to eliminate redundant batch evaluations and keep match execution fast.
  * Step 1b decision: bet-size grid kept for feature inputs in Phase 3 policy (`USE_SIZE_GRID = False`), avoiding greedy single-street trap.
- 2026-11-11 v1.1 (fix-v1-1):
  * Stand-in opponent: implemented opponents\raise_or_fold.py plus 4 variants (rof_tight, rof_loose, rof_big, rof_small) and mirrored opponent liar.py.
  * Fix A (Adaptive size reading): at showdowns, calculates card strength percentile p using eval_batch; learns s_k per bet size bucket (small, med, large, over) smoothed with prior weight 6 and clamped to +-0.22 of prior until 30 showdowns.
  * Fix B (EV betting & bluffing): replaces fixed betting with EV maximization over {0.33, 0.50, 0.75, 1.0} * pot vs EV(check), with response rates learned per bucket, station protections, and river mixing.
  * Fix C (Preflop raise scaling): scales BB calling threshold and 3-betting against button open raises based on observed pfr_btn, with adaptation bounded to nominal +-0.20.
  * Generalization guard: confirmed robustness across all 4 rof variants and liar; verified held-out gains exceed design-set gains.

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
- 2026-11-11 (user): Amendments before Phase 2:
  * Baseline from now on is snapshots\v1_1_bot.py (commit b277b76), not v1.
  * Phase 2 Step 0 (friend diagnosis) already complete; skip it. All regression gates vs snapshots\v1_1_bot.py.
  * New Step 1b (bet-size grid in src\strategy.py, config in config.py):
    - sizes when not facing a bet: {0.25, 0.33, 0.45, 0.6, 0.75, 1.0, 1.4} pot (1.4 if stack covers; STACK_OFF rule unchanged).
    - Replace 4 response buckets with per-size counts; our bet counts at nearest grid size; smoothed rate = (counts[b] + 0.5 * neighbor_counts + 8 * prior) / total_weight.
    - Clamps: fold-rate within +-0.30 of prior until 40 observations at size + neighbors.
    - Gate: rof_small Stage 2 within CI of v1's +3.16, gto_like Stage 2 no worse than v1.1, full zoo within CI, head-to-head vs v1_1 seeds 1-40 wins >= losses.
  * Reporting rule: gain CI = sqrt(CI_new^2 + CI_old^2) (or paired CI). Report chips/hand AND capped chips/hand (+-1.00/hand) and W-D-L; judge by W-D-L and capped chips.
  * Training plan amendments:
    - Pool (tools\train_config.json): remove friend. Add rof_tight, rof_loose, rof_big, rof_small, raise_or_fold (weight 2 each), snapshots\v1_1_bot.py (weight 3).
    - Held out for validation only: friend, liar, ai_typical, second exploiter variant, seeds >= 5000. Never report training F on these.
    - Objective per match: score = 0.6 * tanh(n / 0.25) + 0.4 * clip(n, -1, 1), F = weighted mean. Notice/forfeit/traceback: F = -10.
    - Train on Stage 1 length (200 hands/leg) >= 50% of the time.
    - Replacement gate: on held-out seeds, no winning W-D-L becomes losing, capped chips improve on average, friend S1 & S2 no worse within CI.
- 2026-11-11 (user): Step 1b decision: do not ship it.
  * Add USE_SIZE_GRID to config.py and set False: decisions use v1.1 sizing and response buckets exactly.
  * Keep grid code and per-size counts as inputs to trained policy in Phase 3 (policy chooses among grid sizes with learned weights; exploration happens in training, not in matches).
  * Proceed to Step 2 (Bayesian range with no-double-counting rule and USE_BAYES ablation), gated against snapshots\v1_1_bot.py. Do not snapshot v1_2.
- 2026-11-11 (Phase 3 decisions approved by user):
  * Baseline from now on is snapshots\v1_1_bot.py (commit b277b76).
  * Wider opponent pool: opponents\persona.py with ~10 style knobs sampled deterministically by MATCH_SEED. Sanity: beats random_bot (5-0-0, +11.08 chips/hand), loses to v1_1 (0-0-5, +3.11 chips/hand for v1_1).
  * Training pool: includes personas (seeds < 5000) at weight 4 (13.8% of pool <= 15% cap limit).
  * Held-out pool (seeds >= 5000): 30 fixed personas (seeds 5000-5029), friend, friend2 (when added), liar, ai_typical, exploiter2. Never report training F on these.
  * Policy architecture: RANGE_BLEND in [0, 1] between Bayesian range and v1.1 shrink range (starts at 0.0). Softmax sizing (learned TAU_BET) over 7-point grid {0.25, 0.33, 0.45, 0.60, 0.75, 1.00, 1.40} pot with multi-street future value term (BETA_MULTI * delta_pot).
  * Stage A parameter scope: trains at most ~15 parameters (RANGE_BLEND, BETA_MULTI, TAU_BET, TAU_ACT, and ~10 key v1.1 thresholds). Residual weights fixed at 0 overnight.
  * Warm start pass condition: head-to-head vs v1_1 over 40 seeds Stage 2 with wins between 16 and 24 and mean within its 95% CI of zero.
  * Acceptance rule: average capped chips across ALL held-out opponents improves, win share does not fall, no win becomes a clear loss, and head-to-head vs live is not worse. No single opponent (friend included) decides acceptance alone.

## 4. Facts and lessons
- Step 1b evaluation: greedy single-street EV over a size grid gets stuck (never tries the size the opponent calls) and loses multi-street value; capped chips fell 0.1-0.24 vs gto_like, rof variants, liar and friend. Fix belongs in the trained policy (multi-street value term e.g. learned weight x pot growth on flop/turn + softmax with learned temperature during training).
- Diagnosis of 50 Stage-2 matches (50,000 hands) of v1 vs friend's bot:
  * v1 lost 31 of 50 matches, -11,871 chips (-0.24/hand); -0.83/hand as BB, +0.35 as button.
  * Friend's style: button opens top ~15% to 6, limps rest, folds worst 18%; BB 3-bets top ~5%, calls almost everything. Postflop bets ~1.0 pot are ahead 83-90% of the time, bets ~0.33 pot only 38-50%. Facing our 0.45-0.85 pot bets it almost never calls (0-6%): folds 56-79%, raises 15-43%.
  * Leak 1: calls vs big bets lost ~150k chips vs folding; calls vs small bets gained ~250k. Bet size reflects hand strength; v1 previously ignored size.
  * Leak 2: under-bluffing: we bet only 43-56% when checked to although friend folds 56-79% to our bets.
  * Leak 3: calling its preflop raises with average hands lost -17,800 chips.
  * Non-leaks: our river folds were correct (behind 94% of the time); discards both followed cheap rule (85-88%).
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
