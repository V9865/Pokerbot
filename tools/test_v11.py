"""Unit tests for v1.1 adaptive fixes."""
import os
import sys
import time
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from cards import CARD_ID
from strategy import OppModel, Brain, bet_bucket
from evaluator import HAVE_NP


def test_synthetic_showdowns():
    print("Testing synthetic showdowns (Fix A)...")
    opp = OppModel()
    # Large bets show top 10% hands (p <= 0.05)
    for _ in range(15):
        opp.opp_bet_sum_p[2] += 0.03
        opp.opp_bet_count[2] += 1
    s_large = opp.shrink(1.0)
    print(f"s_large after 15 showdowns with top hands: {s_large:.3f}")
    assert s_large < 0.3, f"Expected s_large < 0.3, got {s_large}"

    # Small bets show weak hands (p >= 0.85)
    for _ in range(15):
        opp.opp_bet_sum_p[0] += 0.90
        opp.opp_bet_count[0] += 1
    s_small = opp.shrink(0.25)
    print(f"s_small after 15 showdowns with weak hands: {s_small:.3f}")
    assert s_small > 0.8, f"Expected s_small > 0.8, got {s_small}"
    print("PASS: synthetic showdowns")


def test_synthetic_fold_counts():
    print("Testing synthetic fold counts and EV betting (Fix B)...")
    brain = Brain()
    # Mock hole cards
    brain.hole = [CARD_ID["2h"], CARD_ID["3d"]]
    brain.seat = "button"

    # Set fold rate 0.8 to medium bets
    # our_bet_counts: [fold, call, raise]
    brain.opp.our_bet_counts[1] = [80, 15, 5]

    req = {
        "type": "action_request",
        "hand_id": 1,
        "street": "flop",
        "board": ["8s", "8h", "Kd"],
        "pot": 20,
        "my_bet": 0,
        "opp_bet": 0,
        "to_call": 0,
        "my_stack": 190,
        "opp_stack": 190,
        "legal_actions": ["check", "raise"],
        "min_raise": 2,
        "max_raise": 190,
        "raises_left": 4,
    }

    # Mock _equity to return low equity e_r ~ 0.2
    brain._equity = lambda r, mode, x: (0.20, (lambda share: 0.20))

    bets = 0
    for _ in range(200):
        act = brain._postflop(req, 0, 1.0)
        if act.get("action") == "raise":
            bets += 1

    print(f"Bets placed when opponent folds 80% (low equity 0.2): {bets} / 200")
    assert bets > 160, f"Expected > 80% bets (> 160), got {bets}"

    # Station: fold rate 0.05, is_station True
    brain.opp.bets_faced = 25
    brain.opp.folds_to_bet = 1  # 1/25 < STATION_FOLD
    assert brain.opp.is_station()
    brain.opp.our_bet_counts[1] = [2, 95, 3]

    station_bets = 0
    for _ in range(200):
        act = brain._postflop(req, 0, 1.0)
        if act.get("action") == "raise":
            station_bets += 1

    print(f"Bets placed vs station when e_r < 0.5: {station_bets} / 200")
    assert station_bets == 0, f"Expected 0 bets vs station with e_r < 0.5, got {station_bets}"
    print("PASS: synthetic fold counts")


def test_pfr_adaptation():
    print("Testing preflop PFR adaptation (Fix C)...")
    brain = Brain()
    # Hand with q ~ 0.45
    brain.hole = [CARD_ID["2s"], CARD_ID["6h"], CARD_ID["Ah"]]
    brain.seat = "big_blind"
    from preflop_table import preflop_q
    q = preflop_q(*brain.hole)
    print(f"Hand q: {q:.3f}")

    req = {
        "type": "action_request",
        "hand_id": 1,
        "street": "preflop",
        "board": [],
        "pot": 8,
        "my_bet": 2,
        "opp_bet": 6,
        "to_call": 4,
        "my_stack": 198,
        "opp_stack": 194,
        "legal_actions": ["fold", "call", "raise"],
        "min_raise": 10,
        "max_raise": 198,
        "raises_left": 3,
    }

    # With no data: pfr_btn is prior 0.45 -> should call raise to 6
    act = brain._preflop(req, 1)
    print(f"Action with no data (prior pfr 0.45): {act}")
    assert act["action"] == "call", f"Expected call with no data, got {act}"

    # After 60 hands with pfr = 0.15 (9 raises in 60 button opportunities)
    brain.opp.btn_opps = 60
    brain.opp.btn_raises = 9
    pfr = brain.opp.pfr_btn()
    print(f"Learned pfr_btn: {pfr:.3f}")

    act2 = brain._preflop(req, 1)
    print(f"Action with pfr 0.15: {act2}")
    assert act2["action"] == "fold", f"Expected fold against tight raiser, got {act2}"
    print("PASS: preflop PFR adaptation")


def test_showdown_timing():
    print("Testing showdown observation timing...")
    if not HAVE_NP:
        print("SKIP: showdown timing (numpy unavailable)")
        return
    opp = OppModel()
    hist = [
        {"street": "preflop", "actor": "me", "action": "raise", "amount": 6},
        {"street": "preflop", "actor": "opp", "action": "call", "amount": 6},
        {"street": "flop", "actor": "me", "action": "check"},
        {"street": "flop", "actor": "opp", "action": "raise", "amount": 8},
        {"street": "flop", "actor": "me", "action": "call", "amount": 8},
        {"street": "turn", "actor": "me", "action": "check"},
        {"street": "turn", "actor": "opp", "action": "raise", "amount": 25},
        {"street": "turn", "actor": "me", "action": "call", "amount": 25},
    ]
    board = ["Ks", "9h", "4d", "2c", "Jh"]
    opp_hole = ["Ah", "Qd"]
    opp_disc = "7s"

    # Warmup
    opp.observe_showdown(opp_hole, opp_disc, board, hist, "big_blind")

    t0 = time.perf_counter()
    N = 500
    for _ in range(N):
        opp.observe_showdown(opp_hole, opp_disc, board, hist, "big_blind")
    dt = (time.perf_counter() - t0) * 1000.0 / N
    print(f"Average observe_showdown time over {N} showdowns: {dt:.3f} ms")
    assert dt < 3.0, f"Showdown observation took too long: {dt:.3f} ms (budget 3.0 ms)"
    print("PASS: showdown timing")


def main():
    test_synthetic_showdowns()
    test_synthetic_fold_counts()
    test_pfr_adaptation()
    test_showdown_timing()
    print("\nRESULT: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
