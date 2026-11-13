"""Verify that dist/bot.py decisions match C:/pokerbot_runs/variants/v5_A_untrained.py exactly on 1,000 spots."""
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
    path_variant = r"C:\pokerbot_runs\variants\v5_A_untrained.py"
    path_dist = os.path.join(ROOT, "dist", "bot.py")

    assert os.path.isfile(path_variant), f"Missing {path_variant}"
    assert os.path.isfile(path_dist), f"Missing {path_dist}"

    mod_var = load_module_from_path("var_bot", path_variant)
    mod_dist = load_module_from_path("dist_bot", path_dist)

    print("Verifying configuration matches between variant and dist/bot.py...")
    assert mod_dist.CFG.get("FIX_BUCKET") == mod_var.CFG.get("FIX_BUCKET") == True
    assert mod_dist.CFG.get("PF_3BET_SCALE") == mod_var.CFG.get("PF_3BET_SCALE") == True
    assert mod_dist.CFG.get("RAISE_EV") == mod_var.CFG.get("RAISE_EV") == False
    assert mod_dist.CFG.get("USE_FREQ_FLOOR") == mod_var.CFG.get("USE_FREQ_FLOOR") == False

    for k, v in mod_var.PARAMS.items():
        assert mod_dist.PARAMS.get(k) == v, f"PARAM mismatch on {k}: {mod_dist.PARAMS.get(k)} != {v}"

    RANKS = "23456789TJQKA"
    SUITS = "shdc"
    DECK = [r + s for r in RANKS for s in SUITS]

    random.seed(98765)
    import numpy as np

    brain_var = mod_var.Brain()
    brain_dist = mod_dist.Brain()
    brain_var.rng = np.random.default_rng(98765)
    brain_dist.rng = np.random.default_rng(98765)

    spots = 0
    target_spots = 1000

    print(f"Running {target_spots} decision spots comparing v5_A_untrained vs dist/bot.py...")

    while spots < target_spots:
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

        mod_var.random.seed(spots * 100)
        mod_dist.random.seed(spots * 100)
        brain_var.observe(start_msg)
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

        r_state = random.getstate()
        dec_var = brain_var.decide(act_req_pf)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_pf)
        assert dec_var == dec_dist, f"Spot {spots} PF mismatch: {dec_var} != {dec_dist}"
        spots += 1
        if spots >= target_spots:
            break

        # 2. Discard request
        disc_req = {
            "type": "discard_request",
            "hand_id": hand_id,
            "hole_cards": hole3,
            "board": board[:3],
        }
        r_state = random.getstate()
        disc_var = brain_var.discard(disc_req)
        random.setstate(r_state)
        disc_dist = brain_dist.discard(disc_req)
        assert disc_var == disc_dist, f"Spot {spots} Discard mismatch: {disc_var} != {disc_dist}"
        spots += 1
        if spots >= target_spots:
            break

        # Update hole cards after discard via discard_result
        kept = [c for c in hole3 if c != disc_var["card"]]
        disc_res = {
            "type": "discard_result",
            "hand_id": hand_id,
            "hole_cards": kept,
            "my_discard": disc_var["card"],
            "opp_discard": shuffled[8],
        }
        brain_var.observe(disc_res)
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
        dec_var = brain_var.decide(act_req_flop)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_flop)
        assert dec_var == dec_dist, f"Spot {spots} Flop mismatch: {dec_var} != {dec_dist}"
        spots += 1
        if spots >= target_spots:
            break

        # 4. Turn action request
        to_call_turn = random.choice([0, 0, 10, 25])
        pot_turn = 30 + to_call_turn
        act_req_turn = {
            "type": "action_request",
            "hand_id": hand_id,
            "street": "turn",
            "board": board[:4],
            "pot": pot_turn,
            "my_bet": 0,
            "opp_bet": to_call_turn,
            "to_call": to_call_turn,
            "my_stack": 175,
            "opp_stack": 175,
            "legal_actions": ["check", "raise"] if to_call_turn == 0 else ["fold", "call", "raise"],
            "min_raise": min(to_call_turn + 4, 175),
            "max_raise": 175,
            "history": [
                {"street": "preflop", "actor": "button", "action": "call", "amount": 2},
                {"street": "preflop", "actor": "big_blind", "action": "check", "amount": 2},
                {"street": "flop", "actor": "button", "action": "raise", "amount": 6},
                {"street": "flop", "actor": "big_blind", "action": "call", "amount": 6},
            ],
        }
        r_state = random.getstate()
        dec_var = brain_var.decide(act_req_turn)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_turn)
        assert dec_var == dec_dist, f"Spot {spots} Turn mismatch: {dec_var} != {dec_dist}"
        spots += 1
        if spots >= target_spots:
            break

        # 5. River action request
        to_call_river = random.choice([0, 0, 15, 30])
        pot_river = 50 + to_call_river
        act_req_river = {
            "type": "action_request",
            "hand_id": hand_id,
            "street": "river",
            "board": board[:5],
            "pot": pot_river,
            "my_bet": 0,
            "opp_bet": to_call_river,
            "to_call": to_call_river,
            "my_stack": 150,
            "opp_stack": 150,
            "legal_actions": ["check", "raise"] if to_call_river == 0 else ["fold", "call", "raise"],
            "min_raise": min(to_call_river + 4, 150),
            "max_raise": 150,
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
        dec_var = brain_var.decide(act_req_river)
        random.setstate(r_state)
        dec_dist = brain_dist.decide(act_req_river)
        assert dec_var == dec_dist, f"Spot {spots} River mismatch: {dec_var} != {dec_dist}"
        spots += 1

    print(f"PASS: All {spots} spots matched 100% identically between dist/bot.py and C:/pokerbot_runs/variants/v5_A_untrained.py!")


if __name__ == "__main__":
    main()

