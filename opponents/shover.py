"""All-in every hand."""
from zoocommon import run, raise_to, lowest
run(lambda req, me: raise_to(req, req.get("max_raise", 0)), lambda req, me: lowest(req["hole_cards"]))
