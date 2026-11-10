"""Test helper: plays like a mild random bot and prints every request it receives
to stderr, so tools\test_history.py can check our reading of the action history."""
import json, random, sys
from zoocommon import run, call_or_check, pot_raise, fold_or_check, lowest


def act(req, me):
    print("REQ " + json.dumps({"seat": me.seat, "req": req}), file=sys.stderr)
    r = random.random()
    if r < 0.30:
        return pot_raise(req, random.choice([0.3, 0.6, 1.0, 1.5]))
    return call_or_check(req) if r < 0.92 else fold_or_check(req)


run(act, lambda req, me: lowest(req["hole_cards"]))
