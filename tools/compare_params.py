"""Compare T_mean (initial), T5_mean, and T5_best parameters, flagging STAGE_A_NAMES and bound hits."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from policy_params import STAGE_A_NAMES, PARAMS, BOUNDS

RUNS_ROOT = r"C:\pokerbot_runs"
STAGE_A_V5 = os.path.join(RUNS_ROOT, "train", "stage_a_v5")

with open(os.path.join(STAGE_A_V5, "mean.json")) as f:
    t5_mean = json.load(f)
with open(os.path.join(STAGE_A_V5, "best.json")) as f:
    t5_best = json.load(f)

print(f"{'PARAM':<20} {'T_mean (start)':<15} {'T5_mean':<15} {'T5_best':<15} {'Bounds':<20} {'Status'}")
print("-" * 95)

key_params = ["RANGE_BLEND", "BETA_MULTI", "TAU_BET", "TAU_ACT", "UNCERTAINTY", "OOP_PENALTY"]

for name in sorted(PARAMS.keys()):
    v_start = PARAMS[name]
    v_mean = t5_mean.get(name, v_start)
    v_best = t5_best.get(name, v_start)
    b = BOUNDS.get(name)
    b_str = f"[{b[0]:.2f}, {b[1]:.2f}]" if b else "None"
    
    hit_flags = []
    if b:
        if abs(v_mean - b[0]) < 1e-4: hit_flags.append("mean@LOWER")
        if abs(v_mean - b[1]) < 1e-4: hit_flags.append("mean@UPPER")
        if abs(v_best - b[0]) < 1e-4: hit_flags.append("best@LOWER")
        if abs(v_best - b[1]) < 1e-4: hit_flags.append("best@UPPER")
        
    status = " ".join(hit_flags)
    trained = "*" if name in STAGE_A_NAMES else " "
    
    # Show if trained or hit bound or changed
    if name in STAGE_A_NAMES or abs(v_mean - v_start) > 1e-4 or abs(v_best - v_start) > 1e-4 or status:
        print(f"{trained}{name:<19} {v_start:<15.4f} {v_mean:<15.4f} {v_best:<15.4f} {b_str:<20} {status}")

