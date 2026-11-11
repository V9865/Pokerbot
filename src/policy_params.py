"""Parameters and bounds for the trained policy.
Stage A trains at most ~15 parameters. Residual weights stay fixed at 0.
Initial values reproduce v1.1 behavior.
"""
try:
    import numpy as np
except Exception:
    np = None

STAGE_A_NAMES = [
    "RANGE_BLEND",
    "BETA_MULTI",
    "TAU_BET",
    "TAU_ACT",
    "VALUE_MIN",
    "CALL_MARGIN",
    "BIG_CALL_MARGIN",
    "BLUFF_SCALE",
    "STACK_OFF_EQ",
    "PF_OPEN_Q",
    "PF_CALL_Q_MED",
    "PF_3BET_Q",
    "PF_CALL_PFR_MULT",
    "RAISE_VALUE",
]

PARAMS = {
    # Phase 3 trainable parameters
    "RANGE_BLEND": 0.0,         # 0.0 = pure v1.1 range, 1.0 = pure Bayesian range
    "BETA_MULTI": 0.0,          # learned weight on multi-street expected pot growth
    "TAU_BET": 0.02,            # softmax temperature over bet sizes (0.02 = argmax v1.1)
    "TAU_ACT": 0.02,            # softmax temperature over actions (0.02 = argmax v1.1)
    "BLUFF_SCALE": 1.0,         # scale factor on bluff frequencies
    # Key postflop thresholds
    "VALUE_MIN": 0.53,
    "VALUE_BIG": 0.66,
    "CALL_MARGIN": 0.04,
    "BIG_CALL_MARGIN": 0.07,
    "RAISE_VALUE": 0.78,
    "STACK_OFF_EQ": 0.62,
    "OOP_PENALTY": 0.02,
    "UNCERTAINTY": 0.25,
    "EV_MIX_MARGIN": 0.03,
    "BLUFF_FLOP": 0.12,
    "BLUFF_TURN": 0.06,
    "BLUFF_RIVER": 0.04,
    "BLUFF_MAX_EQ": 0.40,
    "BLUFF_SIZE": 0.60,
    "ALLIN_IF_STACK_USE": 0.70,
    # Key preflop thresholds
    "PF_OPEN_Q": 0.75,
    "PF_OPEN_SIZE": 5.0,
    "PF_ISO_Q": 0.30,
    "PF_ISO_SIZE": 6.0,
    "PF_3BET_Q": 0.08,
    "PF_4BET_Q": 0.03,
    "PF_5BET_Q": 0.012,
    "PF_CALL_Q_SMALL": 0.80,
    "PF_CALL_Q_MED": 0.55,
    "PF_CALL_Q_BIG": 0.30,
    "PF_CALL_Q_HUGE": 0.14,
    "PF_CALL_Q_ALLIN": 0.05,
    "PF_SHOVE_ADAPT": 0.47,
    "PF_CALL_PFR_MULT": 1.30,
}

BOUNDS = {
    "RANGE_BLEND": (0.0, 1.0),
    "BETA_MULTI": (0.0, 1.0),
    "TAU_BET": (0.02, 0.40),
    "TAU_ACT": (0.02, 0.40),
    "BLUFF_SCALE": (0.0, 2.5),
    "VALUE_MIN": (0.45, 0.65),
    "VALUE_BIG": (0.55, 0.80),
    "CALL_MARGIN": (0.00, 0.12),
    "BIG_CALL_MARGIN": (0.02, 0.18),
    "RAISE_VALUE": (0.68, 0.90),
    "STACK_OFF_EQ": (0.50, 0.75),
    "OOP_PENALTY": (0.0, 0.08),
    "UNCERTAINTY": (0.05, 0.50),
    "EV_MIX_MARGIN": (0.00, 0.10),
    "BLUFF_FLOP": (0.0, 0.35),
    "BLUFF_TURN": (0.0, 0.25),
    "BLUFF_RIVER": (0.0, 0.20),
    "BLUFF_MAX_EQ": (0.20, 0.50),
    "BLUFF_SIZE": (0.33, 1.00),
    "ALLIN_IF_STACK_USE": (0.50, 0.90),
    "PF_OPEN_Q": (0.50, 0.95),
    "PF_OPEN_SIZE": (4.0, 8.0),
    "PF_ISO_Q": (0.15, 0.55),
    "PF_ISO_SIZE": (4.0, 9.0),
    "PF_3BET_Q": (0.03, 0.18),
    "PF_4BET_Q": (0.01, 0.08),
    "PF_5BET_Q": (0.005, 0.04),
    "PF_CALL_Q_SMALL": (0.60, 0.95),
    "PF_CALL_Q_MED": (0.35, 0.75),
    "PF_CALL_Q_BIG": (0.15, 0.55),
    "PF_CALL_Q_HUGE": (0.05, 0.35),
    "PF_CALL_Q_ALLIN": (0.01, 0.15),
    "PF_SHOVE_ADAPT": (0.20, 0.80),
    "PF_CALL_PFR_MULT": (0.60, 2.20),
}

# 60 residual weights (5 action classes x 12 features)
ACTION_CLASSES = ["passive", "small_bet", "big_bet", "allin", "fold"]
FEATURE_COUNT = 12

for act_name in ACTION_CLASSES:
    for f_idx in range(FEATURE_COUNT):
        p_name = f"r_{act_name}_{f_idx}"
        PARAMS[p_name] = 0.0
        BOUNDS[p_name] = (-0.50, 0.50)


def pack_params(param_dict=None, names=None):
    if param_dict is None:
        param_dict = PARAMS
    if names is None:
        names = STAGE_A_NAMES
    return [float(param_dict.get(k, PARAMS.get(k, 0.0))) for k in names]


def unpack_params(values, names=None):
    if names is None:
        names = STAGE_A_NAMES
    res = dict(PARAMS)
    for k, v in zip(names, values):
        lo, hi = BOUNDS[k]
        res[k] = max(lo, min(hi, float(v)))
    return res


def to_unit_cube(values, names=None):
    if names is None:
        names = STAGE_A_NAMES
    unit = []
    for k, v in zip(names, values):
        lo, hi = BOUNDS[k]
        unit.append((v - lo) / (hi - lo) if hi > lo else 0.5)
    return unit


def from_unit_cube(unit_vec, names=None):
    if names is None:
        names = STAGE_A_NAMES
    raw = []
    for k, u in zip(names, unit_vec):
        lo, hi = BOUNDS[k]
        u_clamped = max(0.0, min(1.0, float(u)))
        raw.append(lo + u_clamped * (hi - lo))
    return raw


def pack_stage_a(param_dict=None):
    raw = pack_params(param_dict, STAGE_A_NAMES)
    u = to_unit_cube(raw, STAGE_A_NAMES)
    return np.array(u, dtype=np.float64) if np is not None else u


def unpack_stage_a(unit_vec):
    raw = from_unit_cube(unit_vec, STAGE_A_NAMES)
    return unpack_params(raw, STAGE_A_NAMES)
