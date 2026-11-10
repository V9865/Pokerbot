"""Calling station: the unmodified starter bot. Checks or calls; discards the lowest card."""
from zoocommon import run, call_or_check, lowest
run(lambda req, me: call_or_check(req), lambda req, me: lowest(req["hole_cards"]))
