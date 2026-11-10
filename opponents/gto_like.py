"""A 'balanced heuristic' stand-in for GTO-style bots: wide opens, minimum
defence frequency when facing bets, polarised betting with a fixed bluff ratio,
two bet sizes, randomised mixing, equity-maximising discard."""
import random
from zoocommon import run, pot_raise, raise_to, call_or_check, fold_or_check, equity_discard, equity_random, q_of


def act(req, me):
    pot, to_call, legal = req["pot"], req["to_call"], req["legal_actions"]
    if req["street"] == "preflop":
        q = q_of(me.hole)
        if to_call == 0:
            return raise_to(req, 6) if q <= 0.30 else call_or_check(req)
        bet = req["opp_bet"]
        mdf = (pot - to_call) / float(pot)          # share of hands that must continue
        if bet <= 2:
            return raise_to(req, 5) if q <= 0.80 else call_or_check(req)
        if q <= 0.10 * min(1.0, 12.0 / bet) and "raise" in legal:
            return raise_to(req, 3 * bet)
        return call_or_check(req) if q <= max(0.04, mdf) else fold_or_check(req)
    e = equity_random(me.hole, req["board"], me.dead, 150)
    if to_call == 0:
        if "raise" not in legal:
            return call_or_check(req)
        big = random.random() < 0.30
        frac = 1.0 if big else 0.33
        if e >= (0.78 if big else 0.66):
            return pot_raise(req, frac)
        bluff_share = frac / (1.0 + 2.0 * frac)     # bluffs per bet at this size
        if e < 0.35 and random.random() < bluff_share * 0.6:
            return pot_raise(req, frac)
        return call_or_check(req)
    mdf = (pot - to_call) / float(pot)
    if e >= 0.88 and "raise" in legal:
        return pot_raise(req, 1.0)
    if e < 0.30 and "raise" in legal and random.random() < 0.04:
        return pot_raise(req, 1.0)
    return call_or_check(req) if e >= 1.0 - mdf * 0.85 else fold_or_check(req)


run(act, lambda req, me: equity_discard(req["hole_cards"], req["board"]))
