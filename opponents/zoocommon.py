"""Shared helpers for the test opponents (the zoo). Not part of the submission.
Each zoo bot defines act(req, me) and discard(req, me) and calls run(act, discard)."""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from cards import CARD_ID                                   # noqa: E402
from evaluator import eval7, cheap_keep                     # noqa: E402
from preflop_table import preflop_q                         # noqa: E402

RANKS = "23456789TJQKA"


class Me:
    def __init__(self):
        self.hole = []      # card strings
        self.seat = "button"
        self.dead = []


def ids(cards):
    return [CARD_ID[c] for c in cards]


def lowest(cards):
    return min(cards, key=lambda c: (RANKS.index(c[0]), "shdc".index(c[1])))


def raise_to(req, amount):
    if "raise" not in req["legal_actions"]:
        return call_or_check(req)
    return {"type": "action", "action": "raise",
            "amount": int(max(req["min_raise"], min(req["max_raise"], amount)))}


def pot_raise(req, frac):
    return raise_to(req, req["opp_bet"] + frac * (req["pot"] + req["to_call"]))


def call_or_check(req):
    return {"type": "action", "action": "check" if "check" in req["legal_actions"] else "call"}


def fold_or_check(req):
    return {"type": "action", "action": "check" if "check" in req["legal_actions"] else "fold"}


def price(req):
    return req["to_call"] / float(req["pot"] + req["to_call"]) if req["to_call"] else 0.0


def equity_random(hole, board, dead, n=150):
    """Monte Carlo equity against a RANDOM hand (what a typical AI-coded bot uses).
    With 3 hole cards (before the discard) both sides keep by the cheap rule after
    the flop is known."""
    hole, board, dead = ids(hole), ids(board), ids(dead)
    seen = set(hole) | set(board) | set(dead)
    deck = [c for c in range(52) if c not in seen]
    three = len(hole) == 3
    need = 5 - len(board)
    tot = 0.0
    for _ in range(n):
        pick = random.sample(deck, (3 if three else 2) + need)
        opp, extra = (pick[:3], pick[3:]) if three else (pick[:2], pick[2:])
        full = board + extra
        if three:
            a, b, _ = cheap_keep(hole, full[:3])
            x, y, _ = cheap_keep(opp, full[:3])
            mine, theirs = [a, b], [x, y]
        else:
            mine, theirs = hole, opp
        m, o = eval7(mine + full), eval7(theirs + full)
        tot += 1.0 if m > o else 0.5 if m == o else 0.0
    return tot / n


def cheap_discard(hole, flop):
    h = ids(hole)
    _, _, d = cheap_keep(h, ids(flop))
    return hole[h.index(d)]


def equity_discard(hole, flop, n=80):
    """Discard chosen by simulated equity against a random hand."""
    best, card = -1.0, hole[0]
    for i in range(3):
        keep = hole[:i] + hole[i + 1:]
        e = equity_random(keep, flop, [hole[i]], n)
        if e > best:
            best, card = e, hole[i]
    return card


def q_of(hole):
    return preflop_q(*ids(hole))


def run(act, discard):
    me = Me()
    out = sys.stdout
    sys.stdout = sys.stderr
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "new_hand":
            me.hole, me.seat, me.dead = list(msg["hole_cards"]), msg["seat"], []
            continue
        if t == "discard_result":
            me.hole = list(msg["hole_cards"])
            me.dead = [msg["my_discard"], msg["opp_discard"]]
            continue
        if t == "match_end":
            break
        if t == "action_request":
            try:
                r = act(msg, me)
                if r["action"] not in msg["legal_actions"]:
                    r = fold_or_check(msg)
            except Exception as e:
                print("ERR", repr(e), file=sys.stderr)
                r = fold_or_check(msg)
        elif t == "discard_request":
            try:
                c = discard(msg, me)
                r = {"type": "discard", "card": c if c in msg["hole_cards"] else lowest(msg["hole_cards"])}
            except Exception as e:
                print("ERR", repr(e), file=sys.stderr)
                r = {"type": "discard", "card": lowest(msg["hole_cards"])}
        else:
            continue
        out.write(json.dumps(r) + "\n")
        out.flush()
