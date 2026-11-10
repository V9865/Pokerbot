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

## 2026-11-11 Full Zoo and Leave-One-Out Report: seeds 1-10
Command: py -3.11 tools\run_matches.py --bot dist\bot.py --opps all --seeds 1-10 --jobs 8 --tag v11_full_zoo
```
opponent             group        n     W-D-L chips/hand   95% CI   capped  gain vs v1
station              held-out    10    10-0-0     +22.68   +-1.36    +1.00     +7.85
random_bot           held-out    10    10-0-0     +10.28   +-1.53    +1.00     +0.31
shover               held-out    10    10-0-0     +22.83   +-2.34    +1.00     +0.55
maniac               held-out    10    10-0-0     +33.24   +-2.28    +1.00     +2.69
nit                  held-out    10     8-0-2      +0.98   +-0.64    +0.55     -0.87
minraiser            held-out    10    10-0-0     +28.33   +-2.48    +1.00     -6.98
ai_typical           held-out    10    10-0-0      +9.36   +-1.70    +1.00     +1.96
ai_typical_v2        held-out    10    10-0-0      +7.75   +-1.38    +1.00     +0.10
gto_like             held-out    10    10-0-0      +3.07   +-0.64    +1.00     +0.25
raise_or_fold        design-set  10     9-0-1      +1.93   +-0.85    +0.83     +0.55
rof_tight            held-out    10    10-0-0      +2.72   +-1.20    +0.88     +1.85
rof_loose            held-out    10     9-0-1      +2.34   +-1.07    +0.80     +1.52
rof_big              held-out    10    10-0-0      +3.89   +-1.58    +0.89     +0.43
rof_small            held-out    10     9-0-1      +2.20   +-0.81    +0.89     -0.95
liar                 held-out    10    10-0-0      +3.99   +-0.92    +1.00     +0.62
friend               held-out    10     7-0-3      +0.91   +-0.96    +0.33     +1.31
```
All 16 matchups won. Problems: 0 notices, 0 forfeits, 0 tracebacks.
Average gain on design set: +0.55 chips/hand.
Average gain on held-out set: +0.71 chips/hand (> 100% of design set gain).
