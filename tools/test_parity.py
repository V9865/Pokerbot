"""Verify that dist/bot.py decisions match snapshots/v1_1_bot.py exactly on 200 spots."""
import importlib.util
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    path_v11 = os.path.join(ROOT, "snapshots", "v1_1_bot.py")
    path_dist = os.path.join(ROOT, "dist", "bot.py")

    mod_v11 = load_module_from_path("v11_bot", path_v11)
    mod_dist = load_module_from_path("dist_bot", path_dist)

    print("Verifying CFG['USE_SIZE_GRID'] is False in dist/bot.py...")
    assert mod_dist.CFG.get("USE_SIZE_GRID") is False, "USE_SIZE_GRID must be False"

    # Fix random seed so any tie-breaking or random mixing is deterministic
    RANKS = "23456789TJQKA"
    SUITS = "shdc"
    DECK = [r + s for r in RANKS for s in SUITS]

    random.seed(12345)
    import numpy as np
    brain_v11 = mod_v11.Brain()
    brain_dist = mod_dist.Brain()
    brain_v11.rng = np.random.default_rng(12345)
    brain_dist.rng = np.random.default_rng(12345)

    matches = 0
    spots = 0

    print("Running 200 decision spots comparing v1.1 vs dist/bot.py...")

    while spots < 200:
        hand_id = spots + 1
        seat = "button" if spots % 2 == 0 else "big_blind"
        shuffled = list(DECK)
        random.shuffle(shuffled)
        hole3 = shuffled[:3]
        board = shuffled[3:8]

        start_msg = {
            "type": "new_hand",
            "hand_id": hand_id,
            "seat": seat,
            "hole_cards": hole3,
            "stack": 200,
            "opp_stack": 200,
        }

        # Sync random state before observe
        mod_v11.random.seed(spots * 100)
        mod_dist.random.seed(spots * 100)
        brain_v11.observe(start_msg)
        brain_dist.observe(start_msg)

        # 1. Preflop action request
        to_call = random.choice([0, 1, 2, 4, 8, 16, 40])
        pot = 3 + to_call
        act_req_pf = {
            "type": "action_request",
            "hand_id": hand_id,
            "street": "preflop",
            "pot": pot,
            "my_bet": 1 if seat == "button" else 2,
            "opp_bet": 1 + to_call if seat == "button" else 2 + to_call,
            "to_call": to_call,
            "my_stack": 200 - (1 if seat == "button" else 2),
            "opp_stack": 200,
            "legal_actions": ["fold", "call", "raise"] if to_call > 0 else ["call", "raise"],
            "min_raise": min(4, 200),
            "max_raise": 198,
            "history": [
                {"street": "preflop", "actor": "button", "action": "post", "amount": 1},
                {"street": "preflop", "actor": "big_blind", "action": "post", "amount": 2},
            ],
        }

        # Save RNG states so both bots see the exact same RNG sequence
        r_state = random.getstate()
        dec_v11 = brain_v11.decide(act_req_pf)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_pf)
        assert dec_v11 == dec_dist, f"Spot {spots} PF mismatch: {dec_v11} != {dec_dist}"
        spots += 1
        if spots >= 200:
            break

        # 2. Discard request
        disc_req = {
            "type": "discard_request",
            "hand_id": hand_id,
            "hole_cards": hole3,
            "board": board[:3],
        }
        r_state = random.getstate()
        disc_v11 = brain_v11.discard(disc_req)
        random.setstate(r_state)
        disc_dist = brain_dist.discard(disc_req)
        assert disc_v11 == disc_dist, f"Spot {spots} Discard mismatch: {disc_v11} != {disc_dist}"
        spots += 1
        if spots >= 200:
            break

        # Update hole cards after discard via discard_result
        kept = [c for c in hole3 if c != disc_v11["card"]]
        disc_res = {
            "type": "discard_result",
            "hand_id": hand_id,
            "hole_cards": kept,
            "my_discard": disc_v11["card"],
            "opp_discard": shuffled[8],
        }
        brain_v11.observe(disc_res)
        brain_dist.observe(disc_res)

        # 3. Flop action request
        to_call_flop = random.choice([0, 0, 5, 10, 20])
        pot_flop = 15 + to_call_flop
        act_req_flop = {
            "type": "action_request",
            "hand_id": hand_id,
            "street": "flop",
            "board": board[:3],
            "pot": pot_flop,
            "my_bet": 0,
            "opp_bet": to_call_flop,
            "to_call": to_call_flop,
            "my_stack": 190,
            "opp_stack": 190,
            "legal_actions": ["check", "raise"] if to_call_flop == 0 else ["fold", "call", "raise"],
            "min_raise": min(to_call_flop + 2, 190),
            "max_raise": 190,
            "history": [
                {"street": "preflop", "actor": "button", "action": "call", "amount": 2},
                {"street": "preflop", "actor": "big_blind", "action": "check", "amount": 2},
            ],
        }
        r_state = random.getstate()
        dec_v11 = brain_v11.decide(act_req_flop)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_flop)
        assert dec_v11 == dec_dist, f"Spot {spots} Flop mismatch: {dec_v11} != {dec_dist}"
        spots += 1
        if spots >= 200:
            break

        # 4. River action request (tests EV mix margin and river bet sizing)
        to_call_river = random.choice([0, 0, 15, 30])
        pot_river = 40 + to_call_river
        act_req_river = {
            "type": "action_request",
            "hand_id": hand_id,
            "street": "river",
            "board": board[:5],
            "pot": pot_river,
            "my_bet": 0,
            "opp_bet": to_call_river,
            "to_call": to_call_river,
            "my_stack": 160,
            "opp_stack": 160,
            "legal_actions": ["check", "raise"] if to_call_river == 0 else ["fold", "call", "raise"],
            "min_raise": min(to_call_river + 4, 160),
            "max_raise": 160,
            "history": [
                {"street": "preflop", "actor": "button", "action": "call", "amount": 2},
                {"street": "preflop", "actor": "big_blind", "action": "check", "amount": 2},
                {"street": "flop", "actor": "button", "action": "raise", "amount": 6},
                {"street": "flop", "actor": "big_blind", "action": "call", "amount": 6},
                {"street": "turn", "actor": "button", "action": "check", "amount": 0},
                {"street": "turn", "actor": "big_blind", "action": "check", "amount": 0},
            ],
        }
        r_state = random.getstate()
        dec_v11 = brain_v11.decide(act_req_river)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_river)
        assert dec_v11 == dec_dist, f"Spot {spots} River mismatch: {dec_v11} != {dec_dist}"
        spots += 1

    print(f"PASS: All {spots} spots matched 100% between dist/bot.py and snapshots/v1_1_bot.py!")


if __name__ == "__main__":
    main()
