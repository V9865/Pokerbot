"""Unit tests for Phase 3 policy:
- softmax probabilities sum to 1 and numerical stability
- parameter packing/unpacking and bounds
- legal actions and bet amounts on all streets
- decision speed (< 5ms / decision)
"""
import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Test src directly
from config import CFG
from strategy import Brain
from policy import softmax, decide_policy
from policy_params import STAGE_A_NAMES, PARAMS, BOUNDS, pack_stage_a, unpack_stage_a

def test_softmax():
    print("Testing softmax...")
    # Basic sum to 1
    scores = [1.0, 2.0, 3.0]
    p = softmax(scores, 0.5)
    assert abs(np.sum(p) - 1.0) < 1e-6, "Softmax does not sum to 1"
    assert p[2] > p[1] > p[0], "Softmax ordering broken"

    # Extreme values (numerical stability)
    scores_big = [1000.0, 1005.0, 1010.0]
    p_big = softmax(scores_big, 1.0)
    assert not np.any(np.isnan(p_big)), "NaN in softmax with large values"
    assert abs(np.sum(p_big) - 1.0) < 1e-6, "Large scores do not sum to 1"

    # Extreme low temperature
    p_cold = softmax(scores, 0.01)
    assert p_cold[2] > 0.95, "Cold softmax should peak on highest score"
    print("  softmax: PASS")

def test_param_bounds():
    print("Testing parameter packing/unpacking and bounds...")
    vec = pack_stage_a(PARAMS)
    assert len(vec) == len(STAGE_A_NAMES), f"Packed vector length {len(vec)} != {len(STAGE_A_NAMES)}"
    assert np.all((vec >= -1e-6) & (vec <= 1.0 + 1e-6)), "Packed parameters outside [0, 1]"

    unpacked = unpack_stage_a(vec)
    for name in STAGE_A_NAMES:
        val = unpacked[name]
        lo, hi = BOUNDS[name]
        assert lo - 1e-5 <= val <= hi + 1e-5, f"{name} unpacked value {val} outside bounds [{lo}, {hi}]"
        assert abs(val - PARAMS[name]) < 1e-4, f"{name} roundtrip error: {val} vs {PARAMS[name]}"
    print("  param bounds: PASS")

def test_policy_decisions_and_timing():
    print("Testing policy decisions, action legality, and execution speed...")
    b = Brain()
    # Mock hole cards
    b.hole = [0, 13, 26] # 2c, 2d, 2h
    b.hole_str = ["2c", "2d", "2h"]
    b.seat = "button"

    # 1. Preflop request
    req_pf = {
        "hand_id": 1,
        "street": "preflop",
        "my_bet": 1,
        "opp_bet": 2,
        "pot": 3,
        "to_call": 1,
        "min_raise": 4,
        "max_raise": 200,
        "legal_actions": ["fold", "call", "raise"],
        "history": []
    }
    r_pf = b.decide(req_pf)
    assert r_pf["action"] in req_pf["legal_actions"], f"Illegal action {r_pf}"
    if r_pf["action"] == "raise":
        assert req_pf["min_raise"] <= r_pf["amount"] <= req_pf["max_raise"]

    # Discard
    req_disc = {
        "hand_id": 1,
        "hole_cards": ["2c", "2d", "2h"],
        "board": ["Ah", "Kd", "Qc"]
    }
    disc = b.discard(req_disc)
    assert disc["type"] == "discard"
    assert disc["card"] in req_disc["hole_cards"]

    # Postflop facing check
    b.hole = [0, 13]
    b.hole_str = ["2c", "2d"]
    req_flop_check = {
        "hand_id": 1,
        "street": "flop",
        "board": ["Ah", "Kd", "Qc"],
        "my_bet": 0,
        "opp_bet": 0,
        "pot": 10,
        "to_call": 0,
        "min_raise": 2,
        "max_raise": 195,
        "legal_actions": ["check", "raise"],
        "history": [
            {"street": "preflop", "actor": "me", "action": "raise", "amount": 5},
            {"street": "preflop", "actor": "opp", "action": "call", "amount": 5}
        ]
    }
    r_fc = b.decide(req_flop_check)
    assert r_fc["action"] in req_flop_check["legal_actions"], f"Illegal action {r_fc}"
    if r_fc["action"] == "raise":
        assert req_flop_check["min_raise"] <= r_fc["amount"] <= req_flop_check["max_raise"]

    # Postflop facing bet
    req_flop_bet = {
        "hand_id": 1,
        "street": "flop",
        "board": ["Ah", "Kd", "Qc"],
        "my_bet": 0,
        "opp_bet": 8,
        "pot": 18,
        "to_call": 8,
        "min_raise": 16,
        "max_raise": 195,
        "legal_actions": ["fold", "call", "raise"],
        "history": [
            {"street": "preflop", "actor": "me", "action": "raise", "amount": 5},
            {"street": "preflop", "actor": "opp", "action": "call", "amount": 5},
            {"street": "flop", "actor": "opp", "action": "raise", "amount": 8}
        ]
    }
    r_fb = b.decide(req_flop_bet)
    assert r_fb["action"] in req_flop_bet["legal_actions"], f"Illegal action {r_fb}"

    # Timing 100 postflop decisions
    t0 = time.perf_counter()
    N = 100
    for i in range(N):
        b.decide(req_flop_check)
    dt = (time.perf_counter() - t0) * 1000.0 / N
    print(f"  average postflop decision time: {dt:.3f} ms (budget < 5.0 ms)")
    assert dt < 5.0, f"Decision time {dt:.2f} ms exceeds 5 ms"
    print("  decisions and timing: PASS")

def test_range_blend():
    print("Testing RANGE_BLEND smooth transition...")
    b = Brain()
    b.hole = [0, 13]
    b.seat = "button"
    req = {
        "hand_id": 2,
        "street": "flop",
        "board": ["Ah", "Kd", "Qc"],
        "pot": 20,
        "to_call": 0,
        "min_raise": 2,
        "max_raise": 190,
        "legal_actions": ["check", "raise"],
        "history": []
    }
    for blend in [0.0, 0.25, 0.5, 0.75, 1.0]:
        PARAMS["RANGE_BLEND"] = blend
        r = b.decide(req)
        assert r["action"] in req["legal_actions"]
    PARAMS["RANGE_BLEND"] = 0.0
    print("  range blend: PASS")

if __name__ == "__main__":
    test_softmax()
    test_param_bounds()
    test_policy_decisions_and_timing()
    test_range_blend()
    print("ALL POLICY TESTS PASSED!")
