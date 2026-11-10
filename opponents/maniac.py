"""Hyper-aggressive: raises the pot 70% of the time, otherwise mostly calls."""
import random
from zoocommon import run, pot_raise, call_or_check, fold_or_check, lowest


def act(req, me):
    r = random.random()
    if "raise" in req["legal_actions"] and r < 0.70:
        return pot_raise(req, 1.0)
    return call_or_check(req) if r < 0.955 else fold_or_check(req)


def discard(req, me):
    low = lowest(req["hole_cards"])
    rest = [c for c in req["hole_cards"] if c != low]
    return low if random.random() < 0.5 else lowest(rest)


run(act, discard)
