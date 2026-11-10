"""Reply sanitising, fallbacks and the time governor. Nothing here may raise."""
import sys
import json
import time
from cards import CARD_ID
from evaluator import cheap_keep

OUT = sys.stdout            # the only channel to the engine
sys.stdout = sys.stderr     # stray prints can never reach the engine


def send(obj):
    OUT.write(json.dumps(obj, separators=(",", ":")) + "\n")
    OUT.flush()


def log(*a):
    try:
        print(*a, file=sys.stderr, flush=True)
    except Exception:
        pass


def fallback_action(req):
    legal = req.get("legal_actions") or []
    if "check" in legal:
        return {"type": "action", "action": "check"}
    if "call" in legal and (req.get("to_call") or 99) <= 2:
        return {"type": "action", "action": "call"}
    if "fold" in legal:
        return {"type": "action", "action": "fold"}
    return {"type": "action", "action": legal[0] if legal else "fold"}


def sanitize_action(reply, req):
    legal = req.get("legal_actions") or []
    a = reply.get("action") if isinstance(reply, dict) else None
    if a == "fold" and "check" in legal:
        a = "check"
    if a not in legal:
        return fallback_action(req)
    if a == "raise":
        try:
            lo, hi = int(req["min_raise"]), int(req["max_raise"])
            amt = int(round(float(reply.get("amount", lo))))
            return {"type": "action", "action": "raise", "amount": max(lo, min(hi, amt))}
        except Exception:
            return fallback_action(req)
    return {"type": "action", "action": a}


def fallback_discard(req):
    cards = req.get("hole_cards") or []
    try:
        board = req.get("board") or []
        ids3 = [CARD_ID[c] for c in cards]
        _, _, d = cheap_keep(ids3, [CARD_ID[c] for c in board[:3]])
        return {"type": "discard", "card": cards[ids3.index(d)]}
    except Exception:
        return {"type": "discard", "card": cards[0] if cards else "2c"}


def sanitize_discard(reply, req):
    cards = req.get("hole_cards") or []
    c = reply.get("card") if isinstance(reply, dict) else None
    if c in cards:
        return {"type": "discard", "card": c}
    return fallback_discard(req)


class Governor:
    """Chooses how much to compute from the time left per remaining hand."""
    FULL, HALF, QUARTER, PANIC = 0, 1, 2, 3

    def __init__(self):
        self.total_hands = 200
        self.max_reply_ms = 0.0
        self.total_ms = 0.0
        self.mode_counts = [0, 0, 0, 0]
        self.t0 = 0.0

    def start(self, req, hand_id):
        self.t0 = time.perf_counter()
        left = req.get("time_left_ms")
        if left is None:
            mode = self.FULL
        else:
            per = left / max(1, self.total_hands - hand_id + 1)
            if left < 2000 or per < 25:
                mode = self.PANIC
            elif per < 50:
                mode = self.QUARTER
            elif per < 100:
                mode = self.HALF
            else:
                mode = self.FULL
        self.mode_counts[mode] += 1
        return mode

    def done(self):
        ms = (time.perf_counter() - self.t0) * 1000.0
        self.total_ms += ms
        if ms > self.max_reply_ms:
            self.max_reply_ms = ms
