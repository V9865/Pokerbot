"""The most common AI-written design: equity against a RANDOM hand, fixed
thresholds, pot odds, cheap-rule discard. Deterministic apart from sampling."""
from zoocommon import run, pot_raise, raise_to, call_or_check, fold_or_check, cheap_discard, equity_random, price


def act(req, me):
    e = equity_random(me.hole, req["board"], me.dead, 150)
    if req["street"] == "preflop":
        if e > 0.55 and req["opp_bet"] < 6:
            return raise_to(req, 6)
        return call_or_check(req) if e > price(req) else fold_or_check(req)
    if req["to_call"] == 0:
        return pot_raise(req, 0.67) if e > 0.65 else call_or_check(req)
    return call_or_check(req) if e > price(req) else fold_or_check(req)


run(act, lambda req, me: cheap_discard(req["hole_cards"], req["board"]))
