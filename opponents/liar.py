"""liar: big bets with weak hands, small bets with strong hands."""
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
                if q <= 0.20:
                    return raise_to(req, 6)
                if q > 0.85:
                    return fold_or_check(req)
                return call_or_check(req)
            if q > 0.85:
                return fold_or_check(req)
            return call_or_check(req)
        else:
            if to_call == 0:
                if q <= 0.20:
                    return raise_to(req, 6)
                return call_or_check(req)
            if q <= 0.08:
                return raise_to(req, int(3 * req["opp_bet"]))
            if q > 0.90:
                return fold_or_check(req)
            return call_or_check(req)

    s = equity_random(me.hole, req["board"], me.dead, 150)
    if to_call == 0:
        # Strong hands bet small; weak hands bet big
        if s >= 0.65:
            return pot_raise(req, 0.33)
        elif s < 0.40:
            return pot_raise(req, 1.0)
        return call_or_check(req)
    else:
        # Facing a bet
        if s >= 0.70:
            # Strong hand: small raise or call
            if random.random() < 0.5:
                return pot_raise(req, 0.33)
            return call_or_check(req)
        elif s < 0.35:
            # Weak hand: big raise bluff or fold
            if random.random() < 0.30:
                return pot_raise(req, 1.0)
            return fold_or_check(req)
        else:
            # Medium hand: call if cheap
            frac = to_call / float(max(1, pot - to_call))
            if frac <= 0.5:
                return call_or_check(req)
            return fold_or_check(req)


run(act, lambda req, me: cheap_discard(req["hole_cards"], req["board"]))

