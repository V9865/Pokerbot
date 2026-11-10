"""Tight-passive: plays the top 25% of hands, bets only two pair or better."""
from zoocommon import run, pot_raise, call_or_check, fold_or_check, cheap_discard, q_of, ids, raise_to
from evaluator import eval7


def act(req, me):
    if req["street"] == "preflop":
        q = q_of(me.hole)
        if q <= 0.06:
            return raise_to(req, max(6, 3 * req["opp_bet"]))
        if q <= 0.25 or req["to_call"] <= 1 and q <= 0.5:
            return call_or_check(req)
        return fold_or_check(req)
    cat = eval7(ids(me.hole) + ids(req["board"])) >> 20
    if cat >= 2:
        return pot_raise(req, 0.67)
    if cat == 1 and req["to_call"] <= req["pot"] / 3.0:
        return call_or_check(req)
    return fold_or_check(req)


run(act, lambda req, me: cheap_discard(req["hole_cards"], req["board"]))
