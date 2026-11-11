"""The trained decision policy: preflop, postflop EV betting, softmax sizing, and range blending."""
import math
import random
from config import CFG
from cards import CARD_ID
from preflop_table import preflop_q
from opponent import clamp, nearest_grid_idx, bet_bucket

try:
    import numpy as np
    HAVE_NP = True
except Exception:
    HAVE_NP = False


def softmax(scores, tau=0.02):
    """Numerically stable softmax."""
    tau = max(0.01, float(tau))
    s = np.array(scores, dtype=np.float64) / tau
    s_max = np.max(s)
    exp_s = np.exp(s - s_max)
    total = np.sum(exp_s)
    if total <= 0:
        return np.ones(len(scores)) / len(scores)
    return exp_s / total


def decide_policy(req, brain, mode, x, pf_raises, params=None, rng=None):
    """Entry point for policy decisions."""
    if params is None:
        from policy_params import PARAMS
        params = PARAMS
    if rng is None:
        rng = brain.rng if brain.rng is not None else np.random.default_rng()

    street_name = req.get("street")
    if street_name == "preflop":
        return decide_preflop(req, brain, pf_raises, params)
    return decide_postflop(req, brain, mode, x, params, rng)


def decide_preflop(req, brain, pf_raises, params):
    legal = req["legal_actions"]
    q = preflop_q(*brain.hole)
    to_call = req.get("to_call", 0)
    opp_bet = req.get("opp_bet", 0)
    can_raise = "raise" in legal
    hi = req.get("max_raise", 0)

    steal = (brain.opp.pf_raises_faced >= CFG["EXPLOIT_MIN_BETS"] and
             brain.opp.fold_to_pf_raise() >= CFG["PF_STEAL_FOLD"])

    if to_call == 0:
        if can_raise and q <= (CFG["PF_ISO_Q_STEAL"] if steal else params.get("PF_ISO_Q", 0.30)):
            return {"action": "raise", "amount": int(round(params.get("PF_ISO_SIZE", 6.0)))}
        return {"action": "check"}

    if pf_raises == 0:
        if can_raise and q <= (1.0 if steal else params.get("PF_OPEN_Q", 0.75)):
            return {"action": "raise", "amount": int(round(params.get("PF_OPEN_SIZE", 5.0)))}
        return {"action": "call"}

    shove_q = clamp(params.get("PF_SHOVE_ADAPT", 0.47) * brain.opp.big_pf_freq(),
                    params.get("PF_CALL_Q_ALLIN", 0.05), params.get("PF_SHOVE_ADAPT", 0.47))

    if opp_bet <= 8:
        call_q = params.get("PF_CALL_Q_SMALL", 0.80)
    elif opp_bet <= 16:
        call_q = params.get("PF_CALL_Q_MED", 0.55)
    elif opp_bet <= 40:
        call_q = max(params.get("PF_CALL_Q_BIG", 0.30), shove_q)
    elif opp_bet <= 80:
        call_q = max(params.get("PF_CALL_Q_HUGE", 0.14), shove_q)
    else:
        call_q = shove_q

    if brain.seat == "big_blind" and pf_raises == 1:
        nominal = params.get("PF_CALL_PFR_MULT", 1.30) * 0.45 + 0.05
        adapted = clamp(params.get("PF_CALL_PFR_MULT", 1.30) * brain.opp.pfr_btn() + 0.05,
                        nominal - 0.20, nominal + 0.20)
        call_q = min(call_q, adapted)

    if can_raise:
        if pf_raises == 1:
            t3 = params.get("PF_3BET_Q", 0.08)
            if brain.seat == "big_blind":
                t3 = min(t3, 0.30 * brain.opp.pfr_btn())
            if q <= t3:
                return {"action": "raise", "amount": min(hi, 3 * opp_bet)}
        if pf_raises == 2 and q <= params.get("PF_4BET_Q", 0.03):
            return {"action": "raise", "amount": min(hi, int(2.5 * opp_bet))}
        if pf_raises >= 3 and q <= params.get("PF_5BET_Q", 0.012):
            return {"action": "raise", "amount": hi}

    if q <= call_q:
        return {"action": "call"}
    return {"action": "fold"}


def decide_postflop(req, brain, mode, x, params, rng):
    legal = req["legal_actions"]
    board_cards = req.get("board") or []
    street = len(board_cards)

    # 1. Equity evaluation with RANGE_BLEND
    blend = float(params.get("RANGE_BLEND", 0.0))
    e_all, top = brain.get_blended_equity(req, mode, x, blend)

    x_eff = (1.0 - blend) * x + blend * 1.0
    u = params.get("UNCERTAINTY", 0.25)
    e_r = (1.0 - u) * top(x_eff) + u * e_all
    if brain.seat != "button":
        e_r -= params.get("OOP_PENALTY", 0.02)

    to_call = req.get("to_call", 0)
    pot = req["pot"]
    can_raise = "raise" in legal

    # Facing check: evaluate bet sizing over grid
    if to_call == 0:
        if can_raise:
            station = brain.opp.is_station()
            R = 1.0 if brain.seat == "button" else 0.85
            ev_check = R * e_r * pot

            use_grid = CFG.get("USE_SIZE_GRID", False)
            bet_sizes = CFG["BET_GRID"] if use_grid else CFG["EV_BET_SIZES"]
            candidate_actions = []
            ev_scores = []

            for frac in bet_sizes:
                if frac > 1.0:
                    target_amt = req.get("opp_bet", 0) + frac * (pot + to_call)
                    if target_amt > req["max_raise"]:
                        continue
                b_action = brain._bet(req, frac, e_r)
                if b_action is None:
                    continue
                b = b_action["amount"]
                if use_grid:
                    grid_idx = nearest_grid_idx(b / max(1.0, pot))
                    f_b, c_b, r_b = brain.opp.grid_response_rates(grid_idx)
                else:
                    bucket = bet_bucket(b / max(1.0, pot))
                    f_b, c_b, r_b = brain.opp.response_rates(bucket)
                x_call = (1.0 - blend) * max(CFG["SHRINK_FLOOR"], x * (1.0 - f_b)) + blend * max(CFG["SHRINK_FLOOR"], 1.0 - f_b)
                e_call_b = top(x_call)
                if station and e_call_b < 0.50:
                    continue

                # Multi-street value term: future pot growth when called
                rem_streets = max(0, 5 - street)
                delta_pot = (0.50 * (pot + 2.0 * b) if rem_streets == 2 else 0.25 * (pot + 2.0 * b) if rem_streets == 1 else 0.0)
                beta_multi = float(params.get("BETA_MULTI", 0.0))
                ev_future = c_b * beta_multi * delta_pot

                ev_b = f_b * pot + c_b * (e_call_b * (pot + 2.0 * b) - b) + ev_future - r_b * b
                candidate_actions.append(b_action)
                ev_scores.append(ev_b)

            if candidate_actions:
                tau_bet = float(params.get("TAU_BET", 0.02))
                if tau_bet <= 0.025 or len(candidate_actions) == 1:
                    best_idx = int(np.argmax(ev_scores))
                else:
                    probs = softmax(ev_scores, tau_bet)
                    best_idx = int(rng.choice(len(candidate_actions), p=probs))

                best_bet = candidate_actions[best_idx]
                best_ev = ev_scores[best_idx]

                tau_act = float(params.get("TAU_ACT", 0.02))
                should_bet = best_ev > ev_check
                if tau_act > 0.025:
                    diff = (best_ev - ev_check) / max(1.0, pot)
                    p_bet = 1.0 / (1.0 + math.exp(-clamp(diff / tau_act, -20.0, 20.0)))
                    should_bet = (rng.random() < p_bet)

                if should_bet:
                    if street == 5 and (best_ev - ev_check) < params.get("EV_MIX_MARGIN", 0.03) * pot:
                        if random.random() < 0.50:
                            return {"action": "check"}
                    return best_bet
        return {"action": "check"}

    # Facing bet
    need = to_call / float(pot + to_call)
    big_call = to_call > 0.4 * max(1, req.get("my_stack", 200))
    margin = params.get("BIG_CALL_MARGIN", 0.07) if big_call else params.get("CALL_MARGIN", 0.04)

    if can_raise and e_r >= params.get("RAISE_VALUE", 0.78):
        b = brain._bet(req, CFG["BET_BIG"], e_r)
        if b:
            return b

    tau_act = float(params.get("TAU_ACT", 0.02))
    diff = e_r - (need + margin)
    if tau_act <= 0.025:
        if diff >= 0:
            return {"action": "call"}
        return {"action": "fold"}
    else:
        p_call = 1.0 / (1.0 + math.exp(-clamp(diff / tau_act, -20.0, 20.0)))
        if rng.random() < p_call:
            return {"action": "call"}
        return {"action": "fold"}
