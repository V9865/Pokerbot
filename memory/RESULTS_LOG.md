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
