"""Decision logic. Baseline v1: table preflop, range-narrowed equity postflop,
value-heavy betting, simulated discard, minimal opponent statistics.
Later phases replace the narrowing heuristic with the Bayesian range model."""
import random
from config import CFG
from cards import CARD_ID
from evaluator import cheap_keep, HAVE_NP
from preflop_table import preflop_q
from equity import scalar_equity
from safety import Governor
if HAVE_NP:
    import numpy as np
    from equity import flop_equity, turn_equity, river_equity, top_share_equity

KEEPS = ((0, 1, 2), (0, 2, 1), (1, 2, 0))      # (keep, keep, discard) indices


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class OppModel:
    """Per-leg statistics about the opponent (resets with the process)."""

    def __init__(self):
        self.hands = 0
        self.bets_faced = 0
        self.folds_to_bet = 0
        self.post_actions = 0
        self.post_aggr = 0
        self.big_pf = 0
        self.pf_raises_faced = 0
        self.pf_folds = 0

    @staticmethod
    def _freq(k, n, prior):
        n0 = CFG["STAT_N0"]
        return (k + n0 * prior) / (n + n0)

    def fold_to_bet(self):
        return self._freq(self.folds_to_bet, self.bets_faced, 0.40)

    def aggression(self):
        return self._freq(self.post_aggr, self.post_actions, 0.30)

    def big_pf_freq(self):
        return self._freq(self.big_pf, self.hands, 0.02)

    def fold_to_pf_raise(self):
        return self._freq(self.pf_folds, self.pf_raises_faced, 0.25)

    def folds_enough(self, size):
        """True when a bluff of `size` (pot fraction) is profitable on fold rate alone."""
        return (self.bets_faced >= CFG["EXPLOIT_MIN_BETS"] and
                self.fold_to_bet() >= size / (1.0 + size) + CFG["EXPLOIT_MARGIN"])

    def is_station(self):
        return self.bets_faced >= CFG["STATION_MIN"] and self.fold_to_bet() < CFG["STATION_FOLD"]

    def observe_hand(self, history):
        self.hands += 1
        street = None
        facing = False          # opponent is facing our postflop bet or raise
        big = False
        for e in history or []:
            st, who, act = e.get("street"), e.get("actor"), e.get("action")
            if st != street:
                street, facing = st, False
            if who == "me":
                facing = (act == "raise")
                continue
            if st == "preflop":
                if act == "raise" and (e.get("amount") or 0) >= 40:
                    big = True
                if facing:
                    self.pf_raises_faced += 1
                    if act == "fold":
                        self.pf_folds += 1
                facing = False
                continue
            self.post_actions += 1
            if act == "raise":
                self.post_aggr += 1
            if facing:
                self.bets_faced += 1
                if act == "fold":
                    self.folds_to_bet += 1
            facing = False
        if big:
            self.big_pf += 1


def read_history(history, seat, opp):
    """Replay the hand so far. Returns (x, pf_raises): x = share of the
    opponent's range that their actions leave (strongest hands first)."""
    my_bet, opp_bet = (1, 2) if seat == "button" else (2, 1)
    pot = 3
    street = "preflop"
    x = 1.0
    pf_raises = 0
    for e in history or []:
        st, who, act = e.get("street"), e.get("actor"), e.get("action")
        if st != street:
            street, my_bet, opp_bet = st, 0, 0
        amt = e.get("amount")
        if who == "me":
            if act == "raise" and amt is not None:
                pot += amt - my_bet
                my_bet = amt
                if st == "preflop":
                    pf_raises += 1
            elif act == "call":
                amt = opp_bet if amt is None else amt
                pot += amt - my_bet
                my_bet = amt
            continue
        if act == "raise" and amt is not None:
            if st == "preflop":
                pf_raises += 1
                x *= (CFG["SHRINK_PF_RAISE"] if pf_raises == 1 else
                      CFG["SHRINK_PF_3BET"] if pf_raises == 2 else CFG["SHRINK_PF_4BET"])
            else:
                frac = (amt - my_bet) / max(1.0, pot + (my_bet - opp_bet))
                x *= (CFG["SHRINK_BET_SMALL"] if frac < 0.4 else CFG["SHRINK_BET_MED"] if frac < 0.8 else
                      CFG["SHRINK_BET_LARGE"] if frac < 1.3 else CFG["SHRINK_BET_OVER"])
                if my_bet > 0:
                    x *= CFG["SHRINK_RAISE_EXTRA"]
            pot += amt - opp_bet
            opp_bet = amt
        elif act == "call":
            amt = my_bet if amt is None else amt
            pot += amt - opp_bet
            opp_bet = amt
            if st != "preflop":
                x *= CFG["SHRINK_CALL"]
    # trust the narrowing less against opponents who bet a lot, more against passive ones
    k = clamp(1.6 - 2.0 * opp.aggression(), 0.3, 1.2)
    return max(CFG["SHRINK_FLOOR"], x ** k), pf_raises


class Brain:
    def __init__(self):
        self.gov = Governor()
        self.opp = OppModel()
        self.rng = np.random.default_rng() if HAVE_NP else None
        self.hand_id = 0
        self.seat = "button"
        self.hole = []              # card ids we currently hold (3, then 2)
        self.hole_str = []
        self.dead = []              # both discards once known
        self.cache = {}
        self.errors = 0
        self.notices = 0

    # ------------------------------------------------------------ observation
    def observe(self, msg):
        t = msg.get("type")
        if t == "init":
            self.gov.total_hands = int(msg.get("total_hands") or 200)
        elif t == "new_hand":
            self.hand_id = int(msg.get("hand_id") or self.hand_id + 1)
            self.seat = msg.get("seat") or "button"
            self.hole_str = list(msg.get("hole_cards") or [])
            self.hole = [CARD_ID[c] for c in self.hole_str]
            self.dead = []
            self.cache = {}
        elif t == "discard_result":
            self.hole_str = list(msg.get("hole_cards") or self.hole_str)
            self.hole = [CARD_ID[c] for c in self.hole_str]
            self.dead = [CARD_ID[c] for c in (msg.get("my_discard"), msg.get("opp_discard")) if c in CARD_ID]
        elif t == "hand_result":
            self.opp.observe_hand(msg.get("history"))
        elif t == "notice":
            self.notices += 1

    # ---------------------------------------------------------------- equity
    def _equity(self, req, mode, x):
        """Returns (e_all, top): top(share) = equity against the strongest
        `share` of the opponent's range. Also caches the flop keep choice."""
        board = [CARD_ID[c] for c in req.get("board") or []]
        street = len(board)
        if not HAVE_NP or mode == Governor.PANIC:
            e = scalar_equity(self.hole, board, self.dead, 40)
            return e, (lambda share: max(0.0, e - (1.0 - share) * 0.30))
        if street == 3 and len(self.hole) == 3:
            sim = self.cache.get("flop")
            if sim is None:
                n = CFG["MC_FLOP"] >> mode
                sim = flop_equity(self.hole, board, n, self.rng)
                self.cache["flop"] = sim
            eq, key, win = sim
            w = np.ones(key.size)
            by_keep = [top_share_equity(win[k], key, w, x) for k in range(3)]
            best = int(np.argmax(by_keep))
            self.cache["keep"] = best
            return float(eq[best]), (lambda share: top_share_equity(win[best], key, w, share))
        ck = "s%d" % street
        got = self.cache.get(ck)
        if got is None:
            if street == 4:
                step = (1, 2, 4)[mode]
                e, hands, strength, res = turn_equity(self.hole, board, self.dead, None, step)
            else:
                e, hands, strength, res = river_equity(self.hole, board, self.dead, None)
            got = (e, strength, res, np.ones(res.size))
            self.cache[ck] = got
        e, strength, res, w = got
        return e, (lambda share: top_share_equity(res, strength, w, share))

    # --------------------------------------------------------------- preflop
    def _preflop(self, req, pf_raises):
        legal = req["legal_actions"]
        q = preflop_q(*self.hole)
        to_call = req.get("to_call", 0)
        opp_bet = req.get("opp_bet", 0)
        can_raise = "raise" in legal
        hi = req.get("max_raise", 0)
        steal = self.opp.pf_raises_faced >= CFG["EXPLOIT_MIN_BETS"] and self.opp.fold_to_pf_raise() >= CFG["PF_STEAL_FOLD"]
        if to_call == 0:
            if can_raise and q <= (CFG["PF_ISO_Q_STEAL"] if steal else CFG["PF_ISO_Q"]):
                return {"action": "raise", "amount": CFG["PF_ISO_SIZE"]}
            return {"action": "check"}
        if pf_raises == 0:
            if can_raise and q <= (1.0 if steal else CFG["PF_OPEN_Q"]):
                return {"action": "raise", "amount": CFG["PF_OPEN_SIZE"]}
            return {"action": "call"}
        shove_q = clamp(CFG["PF_SHOVE_ADAPT"] * self.opp.big_pf_freq(), CFG["PF_CALL_Q_ALLIN"], CFG["PF_SHOVE_ADAPT"])
        if opp_bet <= 8:
            call_q = CFG["PF_CALL_Q_SMALL"]
        elif opp_bet <= 16:
            call_q = CFG["PF_CALL_Q_MED"]
        elif opp_bet <= 40:
            call_q = max(CFG["PF_CALL_Q_BIG"], shove_q)
        elif opp_bet <= 80:
            call_q = max(CFG["PF_CALL_Q_HUGE"], shove_q)
        else:
            call_q = shove_q
        if can_raise:
            if pf_raises == 1 and q <= CFG["PF_3BET_Q"]:
                return {"action": "raise", "amount": min(hi, 3 * opp_bet)}
            if pf_raises == 2 and q <= CFG["PF_4BET_Q"]:
                return {"action": "raise", "amount": min(hi, int(2.5 * opp_bet))}
            if pf_raises >= 3 and q <= CFG["PF_5BET_Q"]:
                return {"action": "raise", "amount": hi}
        if q <= call_q:
            return {"action": "call"}
        return {"action": "fold"}

    # -------------------------------------------------------------- postflop
    def _bet(self, req, frac, e_r):
        """Build a bet or raise of `frac` of the pot; None if not sensible."""
        lo, hi = req["min_raise"], req["max_raise"]
        amount = int(round(req.get("opp_bet", 0) + frac * (req["pot"] + req.get("to_call", 0))))
        if amount >= CFG["ALLIN_IF_STACK_USE"] * hi:
            if e_r >= CFG["STACK_OFF_EQ"]:
                amount = hi
            else:
                amount = int(0.45 * hi)
                if amount < lo:
                    return None
        return {"action": "raise", "amount": clamp(amount, lo, hi)}

    def _postflop(self, req, mode, x):
        legal = req["legal_actions"]
        e_all, top = self._equity(req, mode, x)
        u = CFG["UNCERTAINTY"]
        e_r = (1.0 - u) * top(x) + u * e_all
        if self.seat != "button":
            e_r -= CFG["OOP_PENALTY"]
        to_call = req.get("to_call", 0)
        pot = req["pot"]
        street = len(req.get("board") or [])
        can_raise = "raise" in legal
        station = self.opp.is_station()
        if to_call == 0:
            if can_raise:
                floor = CFG["SHRINK_FLOOR"]
                e_c = top(max(floor, x * (0.90 if station else CFG["CALLER_SHARE"])))
                if e_c >= (CFG["STATION_VALUE_MIN"] if station else CFG["VALUE_MIN"]):
                    big = station or e_c >= CFG["VALUE_BIG"]
                    b = self._bet(req, CFG["BET_BIG"] if big else CFG["BET_SMALL"], e_r)
                    if b:
                        return b
                elif e_r < CFG["BLUFF_MAX_EQ"] and not station:
                    p = (CFG["BLUFF_FLOP"], CFG["BLUFF_TURN"], CFG["BLUFF_RIVER"])[street - 3]
                    p *= clamp(self.opp.fold_to_bet() / 0.40, 0.0, 2.0)
                    if self.opp.folds_enough(CFG["BLUFF_SIZE"]):
                        p = CFG["EXPLOIT_BLUFF_P"]      # they fold too much: bet almost always
                    if random.random() < p:
                        b = self._bet(req, CFG["BLUFF_SIZE"], 0.0)
                        if b:
                            return b
            return {"action": "check"}
        need = to_call / float(pot + to_call)
        big_call = to_call > 0.4 * max(1, req.get("my_stack", 200))
        margin = CFG["BIG_CALL_MARGIN"] if big_call else CFG["CALL_MARGIN"]
        if can_raise and e_r >= CFG["RAISE_VALUE"]:
            b = self._bet(req, CFG["BET_BIG"], e_r)
            if b:
                return b
        if e_r >= need + margin:
            return {"action": "call"}
        return {"action": "fold"}

    # ----------------------------------------------------------- entry points
    def decide(self, req):
        hid = int(req.get("hand_id") or self.hand_id)
        mode = self.gov.start(req, hid)
        if not self.hole:
            raise RuntimeError("no hole cards")
        x, pf_raises = read_history(req.get("history"), self.seat, self.opp)
        if req.get("street") == "preflop":
            r = self._preflop(req, pf_raises)
        else:
            r = self._postflop(req, mode, x)
        r["type"] = "action"
        return r

    def discard(self, req):
        hid = int(req.get("hand_id") or self.hand_id)
        mode = self.gov.start(req, hid)
        cards = list(req.get("hole_cards") or self.hole_str)
        ids3 = [CARD_ID[c] for c in cards]
        flop = [CARD_ID[c] for c in (req.get("board") or [])[:3]]
        if HAVE_NP and mode != Governor.PANIC:
            self.hole, self.hole_str = ids3, cards
            if "keep" not in self.cache:
                self._equity({"board": req.get("board")}, mode, 1.0)
            return {"type": "discard", "card": cards[KEEPS[self.cache["keep"]][2]]}
        _, _, d = cheap_keep(ids3, flop)
        return {"type": "discard", "card": cards[ids3.index(d)]}
