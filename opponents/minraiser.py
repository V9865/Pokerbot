"""Min-raises 60% of the time when legal, otherwise calls."""
import random
from zoocommon import run, raise_to, call_or_check, lowest


def act(req, me):
    if "raise" in req["legal_actions"] and random.random() < 0.60:
        return raise_to(req, req["min_raise"])
    return call_or_check(req)


run(act, lambda req, me: lowest(req["hole_cards"]))
