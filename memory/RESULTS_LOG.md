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
