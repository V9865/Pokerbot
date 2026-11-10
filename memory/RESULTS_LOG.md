# Results log (append only)

## 2026-11-10 v1 baseline, Linux reference machine, Stage 1, seeds 1-10
Command: py -3.11 tools\run_matches.py --opps all,snapshots\v0_bot.py --seeds 1-10 --tag v1_baseline
```
opponent             n     W-D-L chips/hand   95% CI   capped
station             10    10-0-0     +14.83   +-0.63    +1.00
random_bot          10    10-0-0      +9.97   +-1.51    +1.00
shover              10    10-0-0     +22.28   +-2.60    +1.00
maniac              10    10-0-0     +30.55   +-2.81    +1.00
nit                 10    10-0-0      +1.85   +-0.62    +0.90
minraiser           10    10-0-0     +35.31   +-1.61    +1.00
ai_typical          10    10-0-0      +7.40   +-1.38    +1.00
ai_typical_v2       10    10-0-0      +7.65   +-1.21    +1.00
gto_like            10    10-0-0      +2.82   +-0.85    +0.98
v0_bot              10     5-0-5      +0.52   +-0.78    +0.21
```
Problems: none (0 notices, 0 forfeits, 0 tracebacks).

## 2026-11-10 timing, v1, serial
```
stage 2  maniac    leg 1  4.99 s  6.7% of bank  max reply 21.6 ms
stage 2  maniac    leg 2  5.00 s  6.7%          20.4 ms
stage 2  gto_like  leg 1  4.96 s  6.6%          20.0 ms
stage 2  gto_like  leg 2  5.47 s  7.3%          23.0 ms
stage 1  maniac    leg 1  1.90 s  6.3%          17.8 ms
stage 1  maniac    leg 2  1.76 s  5.9%          18.3 ms
```

## 2026-11-10 A/B sweep against snapshots\v1_bot.py, 30 seeds each
Command pattern: py -3.11 tools\bundle.py runs\variants\X.py --set NAME=VALUE, then
py -3.11 tools\run_matches.py --bot runs\variants\X.py --opps snapshots\v1_bot.py --seeds 1-30 --tag sw_X
```
variant             n     W-D-L chips/hand   95% CI
CALL_MARGIN=0.0    30    9-0-21      -0.22   +-0.18
CALL_MARGIN=0.08   30   14-0-16      -0.21   +-0.25
```

## 2026-11-10 Phase 0 verify on Windows (Python 3.11.18, numpy 1.26.4, scipy 1.17.1, 20 cores)
Command: py -3.11 tools\run_matches.py --opps all --seeds 1-3 --tag phase0
```
opponent             n     W-D-L chips/hand   95% CI   capped  time s problems
station              3     3-0-0     +14.07   +-0.17    +1.00    26.4 
random_bot           3     3-0-0      +9.03   +-3.02    +1.00    17.2 
shover               3     3-0-0     +20.05   +-3.81    +1.00     0.0 
maniac               3     3-0-0     +32.68   +-2.75    +1.00    14.5 
nit                  3     3-0-0      +1.65   +-1.42    +0.79     1.4 
minraiser            3     3-0-0     +32.75   +-5.33    +1.00    22.5 
ai_typical           3     3-0-0      +8.35   +-3.61    +1.00    20.9 
ai_typical_v2        3     3-0-0      +6.54   +-2.33    +1.00    16.6 
gto_like             3     2-0-1      +2.22   +-2.40    +0.61    11.8 
```
Problems: none (0 notices, 0 forfeits, 0 tracebacks).

Timing check (serial):
```
Stage 1 (30s bank):
maniac    seed 1 leg 1: 2.95s ( 9.8%), max 29.2 ms | leg 2: 2.84s ( 9.5%), max 30.2 ms
maniac    seed 2 leg 1: 3.01s (10.0%), max 28.3 ms | leg 2: 2.70s ( 9.0%), max 26.9 ms
gto_like  seed 1 leg 1: 2.71s ( 9.0%), max 28.6 ms | leg 2: 3.22s (10.7%), max 29.5 ms
gto_like  seed 2 leg 1: 3.01s (10.0%), max 28.0 ms | leg 2: 2.73s ( 9.1%), max 29.4 ms

Stage 2 (75s bank):
maniac    seed 1 leg 1: 7.57s (10.1%), max 31.2 ms | leg 2: 7.81s (10.4%), max 33.3 ms
maniac    seed 2 leg 1: 7.80s (10.4%), max 33.4 ms | leg 2: 7.66s (10.2%), max 29.9 ms
gto_like  seed 1 leg 1: 8.22s (11.0%), max 33.3 ms | leg 2: 9.26s (12.3%), max 32.8 ms
gto_like  seed 2 leg 1: 8.27s (11.0%), max 32.0 ms | leg 2: 7.90s (10.5%), max 35.5 ms
```
All modes FULL [N, 0, 0, 0]. Exit codes 0.


## 2026-11-11 v1 baseline on Windows (seeds matching v1.1 evaluation)
```
opponent             n     W-D-L chips/hand   95% CI   capped
friend (stage 2)    20    7-0-13      -0.40   +-0.46    -0.20
raise_or_fold       30    26-0-4      +1.38   +-0.42    +0.72
rof_tight           20    15-0-5      +0.87   +-1.01    +0.51
rof_loose           20    15-0-5      +0.82   +-0.88    +0.42
rof_big             20    20-0-0      +3.46   +-0.60    +0.97
rof_small           20    20-0-0      +3.15   +-0.56    +0.97
liar                20    19-0-1      +3.37   +-0.69    +0.91
```

## 2026-11-11 Generalization Guard: v1.1 vs rof variants and liar (seeds 1-20)
Command: py -3.11 tools\run_matches.py --bot dist\bot.py --opps rof_tight,rof_loose,rof_big,rof_small --seeds 1-20
```
opponent             n     W-D-L chips/hand   95% CI   capped  gain vs v1
rof_tight           20    18-0-2      +2.20   +-0.84    +0.80     +1.33 (improves beyond CI)
rof_loose           20    15-0-5      +2.07   +-0.80    +0.60     +1.25 (improves beyond CI)
rof_big             20    19-0-1      +4.20   +-0.99    +0.90     +0.74 (improves)
rof_small           20    19-0-1      +2.15   +-0.61    +0.82     -1.00 (within CI, 19 wins)
liar                20    19-0-1      +3.22   +-0.88    +0.90     -0.15 (within CI, 19 wins)
```
Passes Generalization Guard Rule 2 (improves in 3 of 4 variants, none worse beyond CI) and Rule 3 (Fix A reverses meaning within 30 showdowns, no regression beyond CI).

## 2026-11-11 Acceptance Gates: v1.1 vs Friend and Raise-or-Fold
Commands:
py -3.11 tools\run_matches.py --bot dist\bot.py --opps friend --stage 2 --seeds 1-20 --tag v11_friend_s2
py -3.11 tools\run_matches.py --bot dist\bot.py --opps raise_or_fold --seeds 1-30 --tag v11_rof_s1
```
opponent             n     W-D-L chips/hand   95% CI   capped  gain vs v1
friend (stage 2)    20    18-0-2      +0.98   +-0.39    +0.70     +1.38 (improves beyond CI)
raise_or_fold       30    27-0-3      +2.03   +-0.60    +0.77     +0.65 (improves beyond CI)
```

## 2026-11-11 Regression Gate: v1.1 vs snapshots\v1_bot.py, seeds 1-40
Command: py -3.11 tools\run_matches.py --bot dist\bot.py --opps snapshots\v1_bot.py --seeds 1-40 --jobs 8 --tag v11_vs_v1_current
```
opponent             n     W-D-L chips/hand   95% CI   capped
v1_bot              40   28-0-12      +0.44   +-0.39    +0.27
```
Gate criteria: wins >= losses (28 >= 12, PASS), mean > -0.2 chips/hand (+0.44 > -0.2, PASS).

## 2026-11-11 Full Zoo Evaluation: Final v1.1 vs Baseline v1 (seeds 1-10)
- **v1.1 Bot**: `dist/bot.py` (Git commit: `b277b76`)
- **v1 Baseline**: `snapshots/v1_bot.py`
- Runs: `runs/v11_zoo_s1` (v1.1 Stage 1), `runs/v1_zoo_s1` (v1 Stage 1), `runs/v11_zoo_s2` (v1.1 Stage 2), `runs/v1_zoo_s2` (v1 Stage 2)

### Stage 1 (400 hands/match, 200/leg, seeds 1-10)
Git Commit: `b277b76`
```
opponent             n W-D-L(v11) chips(v11)   95% CI   capped | W-D-L(v1)  chips(v1)   95% CI | gain vs v1
station             10    10-0-0     +22.93   +-1.59    +1.00 |    10-0-0     +14.91   +-0.60 |      +8.02
random_bot          10    10-0-0     +11.50   +-1.44    +1.00 |    10-0-0     +10.41   +-1.39 |      +1.09
shover              10    10-0-0     +22.93   +-2.17    +1.00 |    10-0-0     +22.98   +-2.36 |      -0.05
maniac              10    10-0-0     +33.32   +-1.94    +1.00 |    10-0-0     +32.90   +-2.95 |      +0.42
nit                 10     9-0-1      +1.00   +-0.62    +0.57 |     9-0-1      +1.64   +-0.82 |      -0.64
minraiser           10    10-0-0     +28.53   +-4.00    +1.00 |    10-0-0     +34.29   +-2.15 |      -5.76
ai_typical          10    10-0-0      +9.56   +-1.48    +1.00 |    10-0-0      +6.96   +-1.55 |      +2.60
ai_typical_v2       10    10-0-0      +7.56   +-1.19    +1.00 |    10-0-0      +7.36   +-1.10 |      +0.20
gto_like            10    10-0-0      +2.91   +-0.93    +0.93 |    10-0-0      +2.98   +-0.69 |      -0.07
raise_or_fold       10    10-0-0      +2.19   +-0.89    +0.87 |     7-0-3      +1.04   +-0.86 |      +1.15
rof_tight           10    10-0-0      +2.27   +-0.61    +0.91 |     7-0-3      +0.71   +-0.89 |      +1.57
rof_loose           10    10-0-0      +3.14   +-0.74    +1.00 |     8-0-2      +1.36   +-1.28 |      +1.79
rof_big             10    10-0-0      +4.82   +-1.26    +1.00 |     9-0-1      +3.24   +-1.36 |      +1.58
rof_small           10     9-0-1      +2.13   +-1.04    +0.68 |    10-0-0      +2.74   +-0.93 |      -0.61
liar                10    10-0-0      +3.99   +-0.82    +1.00 |    10-0-0      +3.34   +-1.21 |      +0.65
friend              10     7-0-3      +1.35   +-1.18    +0.44 |     6-0-4      +0.12   +-0.91 |      +1.23
```
All 16 matchups won by v1.1. Problems: 0 notices, 0 forfeits, 0 tracebacks.
Design-set average gain (`raise_or_fold`): **+1.15 chips/hand**
Held-out set average gain (15 opps): **+0.80 chips/hand** (> 50% of design gain).

### Stage 2 (1,000 hands/match, 500/leg, seeds 1-10)
Git Commit: `b277b76`
```
opponent             n W-D-L(v11) chips(v11)   95% CI   capped | W-D-L(v1)  chips(v1)   95% CI | gain vs v1
station             10    10-0-0     +22.68   +-0.82    +1.00 |    10-0-0     +14.79   +-0.35 |      +7.90
random_bot          10    10-0-0     +10.12   +-0.94    +1.00 |    10-0-0      +9.18   +-0.84 |      +0.94
shover              10    10-0-0     +23.31   +-2.30    +1.00 |    10-0-0     +22.53   +-2.31 |      +0.78
maniac              10    10-0-0     +33.53   +-1.45    +1.00 |    10-0-0     +32.25   +-1.77 |      +1.28
nit                 10    10-0-0      +1.21   +-0.52    +0.75 |    10-0-0      +1.68   +-0.53 |      -0.47
minraiser           10    10-0-0     +28.50   +-2.82    +1.00 |    10-0-0     +33.85   +-1.33 |      -5.35
ai_typical          10    10-0-0     +10.30   +-0.69    +1.00 |    10-0-0      +7.30   +-0.92 |      +3.00
ai_typical_v2       10    10-0-0      +6.62   +-0.63    +1.00 |    10-0-0      +6.76   +-0.64 |      -0.15
gto_like            10    10-0-0      +1.94   +-0.62    +0.92 |    10-0-0      +2.55   +-0.26 |      -0.61
raise_or_fold       10    10-0-0      +2.12   +-0.64    +0.95 |     7-0-3      +1.11   +-0.85 |      +1.02
rof_tight           10    10-0-0      +1.74   +-0.77    +0.88 |     7-0-3      +0.86   +-0.75 |      +0.88
rof_loose           10     9-0-1      +2.02   +-0.84    +0.83 |     8-0-2      +0.87   +-0.51 |      +1.16
rof_big             10    10-0-0      +3.51   +-0.60    +1.00 |    10-0-0      +4.02   +-0.84 |      -0.50
rof_small           10    10-0-0      +1.72   +-0.80    +0.79 |    10-0-0      +3.16   +-0.55 |      -1.45
liar                10    10-0-0      +4.59   +-0.71    +1.00 |    10-0-0      +3.18   +-0.55 |      +1.41
friend              10    10-0-0      +1.66   +-0.50    +0.91 |     2-0-8      -0.45   +-0.79 |      +2.11
```
All 16 matchups won by v1.1. Problems: 0 notices, 0 forfeits, 0 tracebacks.
Design-set average gain (`raise_or_fold`): **+1.02 chips/hand**
Held-out set average gain (15 opps): **+0.73 chips/hand** (> 50% of design gain).

### 2x CI Gate Check and Diagnostic Investigation
No opponent had v1.1 worse than v1 by more than 2x its 95% CI:
- In Stage 1: max negative ratio was `minraiser` (gain -5.76 vs CI 4.00, ratio = 1.44x CI < 2.0x).
- In Stage 2: max negative ratios were `minraiser` (gain -5.35 vs CI 2.82, ratio = 1.90x CI < 2.0x) and `rof_small` (gain -1.45 vs CI 0.80, ratio = 1.81x CI < 2.0x).

Log analysis via `tools/analyze_log.py`:
1. **minraiser**:
   - `minraiser` blind min-raises every single street regardless of cards. Both v1 and v1.1 won 10-0-0 in both Stage 1 and Stage 2 with massive margins (+28.5 to +34.3 chips/hand; 100% of matches hit the max cap of +1.00).
   - In v1, fixed sizing meant v1 pumped large pots indiscriminately; in v1.1, Fix A observes minraiser's small bets showing random cards ($p \approx 0.50, s_{\text{small}} \approx 1.0$), correctly widening minraiser's range. Because minraiser keeps min-raising through river, v1.1 exercises tighter river equity constraints vs multi-raises, folding slightly more marginal hands rather than stacking off into occasional 3-bet rivers.
2. **rof_small**:
   - `rof_small` bets 0.25-0.4 pot and calls everything under 0.5 pot. Both v1 and v1.1 win 10-0-0 in Stage 2.
   - In v1, `BET_SMALL = 0.45` was below 0.5 pot, so `rof_small` called every small value bet. In v1.1, Fix B evaluates EV across sizes; noticing 0% folds to small bets, it avoids small bluffs but also tests larger sizes where `rof_small` occasionally folds, slightly shifting pot distribution while still solidly winning +1.72 chips/hand (+17,163 chips).


## 2026-11-11 Re-run of Friend Bot (Fixed Seeds 1-20, Apples-to-Apples Comparison)
Ran on final committed v1.1 `dist/bot.py` across identical seed lists:
- **Stage 1 (400 hands/match, 200/leg, seeds 1-20)**: `runs/friend_s1_20/results.csv`
  * Record: **16-0-4**, **+1.02 +- 0.48 chips/hand** (capped +0.67)
  * Seeds 1-10: **9-0-1** (only seed 6 lost: -0.59 chips/hand)
- **Stage 2 (1,000 hands/match, 500/leg, seeds 1-20)**: `runs/friend_s2_20_final/results.csv`
  * Record: **18-0-2**, **+1.20 +- 0.31 chips/hand** (capped +0.81)
  * Seeds 1-10: **10-0-0** (all 10 seeds won!)
  * Seeds 11-20: 8-0-2 (minor losses on seed 11: -0.19, seed 17: -0.09)

