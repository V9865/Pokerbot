"""rof_small: bets 0.25-0.4 pot, calls everything under 0.5 pot."""
import random
from zoocommon import run, pot_raise, raise_to, call_or_check, fold_or_check, cheap_discard, equity_random, q_of


def act(req, me):
    street = req["street"]
    to_call = req["to_call"]
    pot = req["pot"]
    if street == "preflop":
        q = q_of(me.hole)
        if me.seat == "button":
            if to_call <= 1:
                if q <= 0.15:
                    return raise_to(req, 6)
                if q > 0.82:
                    return fold_or_check(req)
                return call_or_check(req)
            if q > 0.82:
                return fold_or_check(req)
            return call_or_check(req)
        else:
            if to_call == 0:
                if q <= 0.15:
                    return raise_to(req, 6)
                return call_or_check(req)
            if q <= 0.05:
                return raise_to(req, int(3 * req["opp_bet"]))
            if q > 0.95:
                return fold_or_check(req)
            return call_or_check(req)

    s = equity_random(me.hole, req["board"], me.dead, 150)
    frac_bet = random.uniform(0.25, 0.40)
    if to_call == 0:
        if s >= 0.50 or random.random() < 0.25:
            return pot_raise(req, frac_bet)
        return call_or_check(req)
    else:
        frac = to_call / float(max(1, pot - to_call))
        if frac < 0.50:
            return call_or_check(req)
        if s >= 0.68:
            return pot_raise(req, frac_bet)
        return fold_or_check(req)


run(act, lambda req, me: cheap_discard(req["hole_cards"], req["board"]))

