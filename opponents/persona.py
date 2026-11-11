"""opponents/persona.py: A parametric bot with ~10 style knobs sampled deterministically by seed.
Knobs:
1. VPIP in [0.20, 0.80]
2. PFR in [0.05, 0.65] (PFR <= VPIP)
3. 3-bet frequency in [0.03, 0.25]
4. Bet frequency per street: flop [0.25, 0.75], turn [0.20, 0.70], river [0.15, 0.65]
5. Bluff share: fraction of bets that are bluffs with weak hands in [0.05, 0.45]
6. Bet-size mix: distribution over {0.33, 0.66, 1.00, 1.40, allin}
7. Fold-to-bet by size: fold rates to small [0.10, 0.60], med [0.25, 0.75], large [0.40, 0.85]
8. Check-raise frequency in [0.00, 0.35]
9. Slowplay frequency in [0.00, 0.35]
10. Discard rule: choice among 'lowest', 'cheap', 'random'
"""
import os
import random
import sys
from zoocommon import (
    run, raise_to, pot_raise, call_or_check, fold_or_check, price,
    equity_random, cheap_discard, lowest, q_of
)


class PersonaConfig:
    def __init__(self, seed):
        self.seed = seed
        prng = random.Random(seed ^ 0x9e3779b9)
        self.vpip = prng.uniform(0.20, 0.80)
        self.pfr = min(prng.uniform(0.05, 0.65), self.vpip * 0.95)
        self.pfr_3bet = prng.uniform(0.03, 0.25)
        self.bet_freq = {
            "flop": prng.uniform(0.25, 0.75),
            "turn": prng.uniform(0.20, 0.70),
            "river": prng.uniform(0.15, 0.65),
        }
        self.bluff_share = prng.uniform(0.05, 0.45)
        raw_mix = [prng.uniform(0.1, 1.0) for _ in range(5)]
        s_mix = sum(raw_mix)
        self.size_mix = [w / s_mix for w in raw_mix]  # [0.33, 0.66, 1.00, 1.40, allin]
        f_s = prng.uniform(0.10, 0.50)
        f_m = prng.uniform(max(f_s, 0.25), 0.75)
        f_l = prng.uniform(max(f_m, 0.40), 0.85)
        self.fold_to_bet = {"small": f_s, "med": f_m, "large": f_l}
        self.check_raise_freq = prng.uniform(0.00, 0.35)
        self.slowplay_freq = prng.uniform(0.00, 0.35)
        d_roll = prng.random()
        if d_roll < 0.50:
            self.discard_rule = "cheap"
        elif d_roll < 0.85:
            self.discard_rule = "lowest"
        else:
            self.discard_rule = "random"


# Initialize configuration from MATCH_SEED
SEED = int(os.environ.get("MATCH_SEED", 1))
CFG = PersonaConfig(SEED)


def pick_bet_size(req, cfg):
    sizes = [0.33, 0.66, 1.00, 1.40, "allin"]
    choice = random.choices(sizes, weights=cfg.size_mix)[0]
    if choice == "allin":
        return raise_to(req, req["max_raise"])
    return pot_raise(req, choice)


def act(req, me):
    street = req.get("street", "preflop")
    to_call = req.get("to_call", 0)
    opp_bet = req.get("opp_bet", 0)
    pot = req.get("pot", 1)

    if street == "preflop":
        q = q_of(me.hole)
        if to_call == 0:
            # Button opening or BB checking over limp
            if q <= CFG.pfr and "raise" in req["legal_actions"]:
                return raise_to(req, min(req["max_raise"], max(5, int(round(3 * req.get("opp_bet", 2))))))
            if q <= CFG.vpip:
                return call_or_check(req)
            return fold_or_check(req)

        # Facing preflop raise
        if opp_bet > 2:
            if q <= CFG.pfr_3bet and "raise" in req["legal_actions"]:
                return raise_to(req, min(req["max_raise"], max(6, int(round(2.8 * opp_bet)))))
            # Call threshold scales with VPIP and price
            p = price(req)
            call_thresh = CFG.vpip * (0.8 if opp_bet <= 12 else 0.5 if opp_bet <= 30 else 0.25)
            if q <= call_thresh:
                return call_or_check(req)
            return fold_or_check(req)

        # Button limped to BB (to_call == 0 or 1)
        if q <= CFG.pfr and "raise" in req["legal_actions"]:
            return raise_to(req, 6)
        if q <= CFG.vpip:
            return call_or_check(req)
        return fold_or_check(req)

    # Postflop
    e = equity_random(me.hole, req.get("board", []), me.dead, 80)
    p = price(req)

    if to_call == 0:
        # Checked to us
        if e >= 0.80 and random.random() < CFG.slowplay_freq and street != "river":
            return call_or_check(req)
        bf = CFG.bet_freq.get(street, 0.40)
        # Value bet
        if e >= 0.58 and random.random() < bf:
            return pick_bet_size(req, CFG)
        # Bluff bet
        if e <= 0.40 and random.random() < (bf * CFG.bluff_share):
            return pick_bet_size(req, CFG)
        return call_or_check(req)

    # Facing a postflop bet
    frac = to_call / max(1.0, pot)
    b_key = "small" if frac < 0.45 else "med" if frac < 0.85 else "large"
    base_fold = CFG.fold_to_bet[b_key]

    # Monster holding: raise / check-raise
    if e >= 0.85 and "raise" in req["legal_actions"]:
        return pick_bet_size(req, CFG)

    # Check-raise bluff with decent equity
    if e >= 0.45 and random.random() < CFG.check_raise_freq and "raise" in req["legal_actions"]:
        return pick_bet_size(req, CFG)

    # Calling threshold based on price + fold tendency
    need = p + (base_fold * 0.25)
    if e >= need:
        return call_or_check(req)
    return fold_or_check(req)


def discard(req, me):
    cards = req.get("hole_cards", me.hole)
    flop = req.get("board", [])[:3]
    if CFG.discard_rule == "cheap":
        return cheap_discard(cards, flop)
    if CFG.discard_rule == "lowest":
        return lowest(cards)
    return random.choice(cards)


if __name__ == "__main__":
    run(act, discard)

