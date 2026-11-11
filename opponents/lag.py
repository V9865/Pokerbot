"""lag: loose-aggressive barreler (stand-in for an aggressive real bot).
Raises preflop often, bets 0.7-1.1 pot most of the time when checked to with
any hand, keeps barrelling, raises some bets as bluffs. Folds weak hands to
big bets, calls medium ones."""
import random
from zoocommon import run, pot_raise, raise_to, call_or_check, fold_or_check, cheap_discard, equity_random, q_of


def act(req, me):
    street = req["street"]
    to_call = req["to_call"]
    pot = req["pot"]
    if street == "preflop":
        q = q_of(me.hole)
        if to_call <= 1 and me.seat == "button":
            if q <= 0.60:
                return raise_to(req, 6)
            return call_or_check(req)
        if to_call == 0:
            if q <= 0.35:
                return raise_to(req, 7)
            return call_or_check(req)
        if q <= 0.15 or (q <= 0.45 and random.random() < 0.25):
            return raise_to(req, int(3 * req["opp_bet"]))
        if q > 0.80 and req["opp_bet"] > 8:
            return fold_or_check(req)
        return call_or_check(req)

    s = equity_random(me.hole, req["board"], me.dead, 150)
    frac_bet = random.uniform(0.7, 1.1)
    if to_call == 0:
        if s >= 0.60 or random.random() < 0.70:
            return pot_raise(req, frac_bet)
        return call_or_check(req)
    frac = to_call / float(max(1, pot - to_call))
    if s >= 0.70 or (s < 0.45 and random.random() < 0.15):
        return pot_raise(req, 1.0)
    if s >= 0.42 or frac < 0.35:
        return call_or_check(req)
    return fold_or_check(req)


run(act, lambda req, me: cheap_discard(req["hole_cards"], req["board"]))
