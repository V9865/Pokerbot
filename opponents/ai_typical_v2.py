"""A stronger AI-written design: equity vs random, value raises, a safety margin
against big bets, some flop bluffs, simulated discard."""
import random
from zoocommon import run, pot_raise, raise_to, call_or_check, fold_or_check, equity_discard, equity_random, price


def act(req, me):
    e = equity_random(me.hole, req["board"], me.dead, 150)
    p = price(req)
    if req["street"] == "preflop":
        if e > 0.60 and req["opp_bet"] <= 20:
            return raise_to(req, max(6, 3 * req["opp_bet"]))
        if e > 0.52 and req["opp_bet"] < 5:
            return raise_to(req, 5)
        return call_or_check(req) if e > p + (0.08 if req["to_call"] > 20 else 0.0) else fold_or_check(req)
    if req["to_call"] == 0:
        if e > 0.60:
            return pot_raise(req, 0.5)
        if req["street"] == "flop" and e < 0.40 and random.random() < 0.15:
            return pot_raise(req, 0.5)
        return call_or_check(req)
    if e > 0.80:
        return pot_raise(req, 0.75)
    big = req["to_call"] > 0.5 * req["pot"]
    return call_or_check(req) if e > p + (0.10 if big else 0.03) else fold_or_check(req)


run(act, lambda req, me: equity_discard(req["hole_cards"], req["board"]))
