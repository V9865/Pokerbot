"""All tunable numbers. Percentile q: 0.0 = best hand, 1.0 = worst.
Change a value only with harness evidence (see the match-testing skill)."""
CFG = {
    # ---- preflop (q thresholds from the 3-card table)
    "PF_OPEN_Q": 0.75,          # button raises first in with q <= this, else calls (never folds for 1 chip)
    "PF_OPEN_SIZE": 5,          # button open raise-to
    "PF_ISO_Q": 0.30,           # big blind raises over a limp with q <= this
    "PF_ISO_SIZE": 6,           # raise-to over a limp
    "PF_3BET_Q": 0.08,          # re-raise a single raise
    "PF_4BET_Q": 0.03,          # raise again over a re-raise
    "PF_5BET_Q": 0.012,         # put the last bet in (pairs of aces)
    "PF_CALL_Q_SMALL": 0.80,    # call a raise-to of <= 8
    "PF_CALL_Q_MED": 0.55,      # call a raise-to of <= 16
    "PF_CALL_Q_BIG": 0.30,      # call a raise-to of <= 40
    "PF_CALL_Q_HUGE": 0.14,     # call a raise-to of <= 80
    "PF_CALL_Q_ALLIN": 0.05,    # call more than 80 (all-in territory), before adaptation
    "PF_SHOVE_ADAPT": 0.47,     # vs frequent big raisers: call q <= this * their big-raise frequency
    "PF_CALL_PFR_MULT": 1.3,    # scale preflop call threshold vs button raise by their PFR
    # ---- postflop
    "OOP_PENALTY": 0.02,        # equity discount when out of position
    "UNCERTAINTY": 0.25,        # weight on the unfiltered range when estimating equity
    "CALLER_SHARE": 0.60,       # share of their range assumed to call a bet (for value decisions)
    "VALUE_MIN": 0.53,          # bet for value if equity vs callers >= this
    "VALUE_BIG": 0.66,          # use the big size if equity vs callers >= this
    "BET_SMALL": 0.50,          # pot fraction
    "BET_BIG": 0.75,
    "RAISE_VALUE": 0.78,        # raise a bet for value at this range-adjusted equity
    "CALL_MARGIN": 0.04,        # extra equity over the price needed to call
    "BIG_CALL_MARGIN": 0.07,    # ... when the call is over 40% of our stack
    "STACK_OFF_EQ": 0.62,       # equity needed to commit the stack voluntarily
    "ALLIN_IF_STACK_USE": 0.70, # a bet using more than this share of the stack becomes all-in
    "BLUFF_FLOP": 0.12, "BLUFF_TURN": 0.06, "BLUFF_RIVER": 0.04,
    "BLUFF_MAX_EQ": 0.40,       # only bluff hands below this equity
    "BLUFF_SIZE": 0.60,
    "USE_SIZE_GRID": False,     # if False, decisions use v1.1 4-bucket sizing; grid counts kept as features
    "EV_BET_SIZES": (0.33, 0.50, 0.75, 1.0), # candidate pot fractions when betting by EV in v1.1
    "BET_GRID": (0.25, 0.33, 0.45, 0.60, 0.75, 1.00, 1.40),
    "BET_GRID_PRIORS": (
        (0.25, 0.65, 0.10),
        (0.30, 0.60, 0.10),
        (0.40, 0.50, 0.10),
        (0.45, 0.46, 0.09),
        (0.50, 0.42, 0.08),
        (0.55, 0.40, 0.05),
        (0.60, 0.38, 0.02),
    ),
    "EV_PRIOR_WEIGHT": 8,       # prior weight for learning fold/call/raise rates to our bets
    "EV_MIX_MARGIN": 0.03,      # river mix threshold: mix 50/50 if best bet beats check by < this * pot
    "USE_BAYES": True,          # switch for Bayesian opponent ranges (Phase 2 Step 2)
    # range narrowing: share of their range kept (strongest first) after each of their actions
    "SHRINK_PF_RAISE": 0.85, "SHRINK_PF_3BET": 0.50, "SHRINK_PF_4BET": 0.35,
    "SHRINK_BET_SMALL": 0.75, "SHRINK_BET_MED": 0.60, "SHRINK_BET_LARGE": 0.50, "SHRINK_BET_OVER": 0.40,
    "SHRINK_RAISE_EXTRA": 0.80, "SHRINK_CALL": 0.85, "SHRINK_FLOOR": 0.08,
    "SHRINK_PRIOR_WEIGHT": 6,
    "FIX_BUCKET": True,         # selected by v5 fix-set test (Variant A: ties field +0.9006 vs C +0.9052, crushes v4 H2H 33-0-7 +0.50 cap)
    "RAISE_EV": False,           # bet EV counts what we win when raised with a strong hand (v1.1: always -b)
    "PF_3BET_SCALE": True,      # BB 3-bet width scales with the button's raise frequency
    "USE_FREQ_FLOOR": False,     # range kept after their bet/raise >= FREQ_FLOOR_MULT x how often they bet/raise
    "FREQ_FLOOR_MULT": 0.9,
    "FREQ_FLOOR_BY_SIZE": True, # floor uses how often they bet that SIZE (False: any bet size)
    "FREQ_PRIOR_BET": 0.35, "FREQ_PRIOR_RAISE": 0.12, "FREQ_PRIOR_WEIGHT": 10,   # prior weight for learning opponent bet-size shrinkage
    # ---- opponent model
    "STAT_N0": 10,              # prior weight for smoothed frequencies
    "STATION_FOLD": 0.15,       # fold-to-bet below this (after STATION_MIN bets) = calling station
    "STATION_MIN": 12,
    "STATION_VALUE_MIN": 0.50,  # vs a station: bet any hand at or above this vs 90% of their range
    "EXPLOIT_MIN_BETS": 8,      # observations needed before a fold-rate exploit switches on
    "EXPLOIT_MARGIN": 0.10,     # fold rate must beat the bluff's break-even by this much
    "EXPLOIT_BLUFF_P": 0.85,    # bluff frequency once they are shown to fold too much
    "PF_STEAL_FOLD": 0.45,      # fold-to-preflop-raise at or above this: raise every button
    "PF_ISO_Q_STEAL": 0.60,     # ... and raise over limps this wide
    # ---- time
    "MC_FLOP": 1500,            # flop samples in FULL mode
    "DECISION_CAP_MS": 250,
}
