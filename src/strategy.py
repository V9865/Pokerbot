"""Decision logic. Baseline v1: table preflop, range-narrowed equity postflop,
value-heavy betting, simulated discard, minimal opponent statistics.
Later phases replace the narrowing heuristic with the Bayesian range model."""
import random
from config import CFG
from cards import CARD_ID
from evaluator import eval7, cheap_keep, HAVE_NP
from preflop_table import preflop_q
from equity import scalar_equity
from safety import Governor
if HAVE_NP:
    import numpy as np
    from evaluator import eval_batch
    from equity import flop_equity, turn_equity, river_equity, top_share_equity
    from ranges import BayesRange
from opponent import clamp, bet_bucket, nearest_grid_idx, OppModel
from policy_params import PARAMS
from policy import decide_policy

KEEPS = ((0, 1, 2), (0, 2, 1), (1, 2, 0))      # (keep, keep, discard) indices


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
                if opp is not None and hasattr(opp, "shrink"):
                    m = opp.shrink(frac)
                else:
                    m = (CFG["SHRINK_BET_SMALL"] if frac < 0.4 else CFG["SHRINK_BET_MED"] if frac < 0.8 else
                         CFG["SHRINK_BET_LARGE"] if frac < 1.3 else CFG["SHRINK_BET_OVER"])
                if my_bet > 0:
                    m *= CFG["SHRINK_RAISE_EXTRA"]
                if opp is not None and CFG.get("USE_FREQ_FLOOR", False) and hasattr(opp, "action_floor"):
                    m = max(m, opp.action_floor(st, my_bet > 0, frac))
                x *= m
            pot += amt - opp_bet
            opp_bet = amt
        elif act == "call":
            amt = my_bet if amt is None else amt
            pot += amt - opp_bet
            opp_bet = amt
            if st != "preflop":
                x *= CFG["SHRINK_CALL"]
    # trust the narrowing less against opponents who bet a lot, more against passive ones
    aggr = opp.aggression() if opp is not None else 0.30
    k = clamp(1.6 - 2.0 * aggr, 0.3, 1.2)
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
        self.bayes_range = None
        self.bayes_history_idx = 0
        self.bayes_street = "preflop"
        self.bayes_pf_raises = 0
        self.bayes_my_bet = 0
        self.bayes_opp_bet = 0
        self.bayes_pot = 3
        self.bayes_flop_replayed = False
        self.my_discard = None
        self.opp_discard = None
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
            self.my_discard = None
            self.opp_discard = None
            self.cache = {}
            if HAVE_NP and CFG.get("USE_BAYES", False):
                self.bayes_range = BayesRange(self.opp, self.hole)
            else:
                self.bayes_range = None
            self.bayes_history_idx = 0
            self.bayes_street = "preflop"
            self.bayes_pf_raises = 0
            self.bayes_my_bet, self.bayes_opp_bet = (1, 2) if self.seat == "button" else (2, 1)
            self.bayes_pot = 3
            self.bayes_flop_replayed = False
        elif t == "discard_result":
            self.hole_str = list(msg.get("hole_cards") or self.hole_str)
            self.hole = [CARD_ID[c] for c in self.hole_str]
            self.dead = [CARD_ID[c] for c in (msg.get("my_discard"), msg.get("opp_discard")) if c in CARD_ID]
            self.my_discard = CARD_ID.get(msg.get("my_discard"))
            self.opp_discard = CARD_ID.get(msg.get("opp_discard"))
            if HAVE_NP and self.bayes_range is not None and self.opp_discard is not None and "board" in self.cache:
                board3 = [CARD_ID[c] for c in self.cache["board"][:3]]
                self.bayes_range.init_range2(self.hole, board3, self.my_discard, self.opp_discard, self.opp.discard_rule_probs)
        elif t == "hand_result":
            self.opp.observe_hand(msg.get("history"), self.seat)
            if msg.get("opp_hole_cards"):
                self.opp.observe_showdown(
                    msg.get("opp_hole_cards"), msg.get("opp_discard"),
                    msg.get("board"), msg.get("history"), self.seat
                )
        elif t == "notice":
            self.notices += 1

    def _update_bayes_from_history(self, history, board_cards):
        if not HAVE_NP or self.bayes_range is None:
            return
        hist = history or []
        board_ids = [CARD_ID[c] for c in board_cards if c in CARD_ID]

        # Initialize Range2 if discard is known and board is available but Range2 not created yet
        if self.bayes_range.w2 is None and self.opp_discard is not None and len(board_ids) >= 3 and len(self.hole) == 2:
            self.bayes_range.init_range2(self.hole, board_ids[:3], self.my_discard, self.opp_discard, self.opp.discard_rule_probs)

        # If Range2 is initialized and flop actions haven't been applied to Range2 yet, apply them
        if self.bayes_range.w2 is not None and not self.bayes_flop_replayed:
            self.bayes_flop_replayed = True
            flop_my_bet, flop_opp_bet = 0, 0
            flop_pot = 3
            for e in hist:
                st = e.get("street")
                if st == "preflop":
                    amt = e.get("amount")
                    if amt is not None:
                        flop_pot = max(flop_pot, 2 * amt)
                elif st == "flop":
                    act = e.get("action")
                    who = e.get("actor")
                    amt = e.get("amount")
                    if who == "me":
                        if act == "raise" and amt is not None:
                            flop_pot += amt - flop_my_bet
                            flop_my_bet = amt
                        elif act == "call":
                            amt = flop_opp_bet if amt is None else amt
                            flop_pot += amt - flop_my_bet
                            flop_my_bet = amt
                    else:  # opp
                        if act == "raise" and amt is not None:
                            self.bayes_range.update_range2(board_ids[:3], "raise", amt - flop_opp_bet, flop_pot,
                                                           street="flop", facing=flop_my_bet > 0)
                            flop_pot += amt - flop_opp_bet
                            flop_opp_bet = amt
                        elif act == "call":
                            self.bayes_range.update_range2(board_ids[:3], "call", 0, flop_pot)
                            amt = flop_my_bet if amt is None else amt
                            flop_pot += amt - flop_opp_bet
                            flop_opp_bet = amt
                        elif act in ("check", "limp"):
                            self.bayes_range.update_range2(board_ids[:3], "check", 0, flop_pot)

        # Process new events incrementally
        for e in hist[self.bayes_history_idx:]:
            st, who, act = e.get("street"), e.get("actor"), e.get("action")
            if st != self.bayes_street:
                self.bayes_street = st
                self.bayes_my_bet, self.bayes_opp_bet = 0, 0
            amt = e.get("amount")
            if who == "me":
                if act == "raise" and amt is not None:
                    self.bayes_pot += amt - self.bayes_my_bet
                    self.bayes_my_bet = amt
                    if st == "preflop":
                        self.bayes_pf_raises += 1
                elif act == "call":
                    amt = self.bayes_opp_bet if amt is None else amt
                    self.bayes_pot += amt - self.bayes_my_bet
                    self.bayes_my_bet = amt
                continue
            # who == "opp"
            if act == "raise" and amt is not None:
                if st == "preflop":
                    self.bayes_pf_raises += 1
                    is_3bet = (self.bayes_pf_raises == 2)
                    is_4bet = (self.bayes_pf_raises >= 3)
                    self.bayes_range.update_preflop("raise", amt, is_3bet, is_4bet)
                else:
                    if self.bayes_range.w2 is not None and st in ("turn", "river"):
                        st_board = board_ids[:4] if st == "turn" else board_ids[:5]
                        self.bayes_range.update_range2(st_board, "raise", amt - self.bayes_opp_bet, self.bayes_pot,
                                                       street=st, facing=self.bayes_my_bet > 0)
                self.bayes_pot += amt - self.bayes_opp_bet
                self.bayes_opp_bet = amt
            elif act == "call":
                amt = self.bayes_my_bet if amt is None else amt
                if st == "preflop":
                    self.bayes_range.update_preflop("call")
                else:
                    if self.bayes_range.w2 is not None and st in ("turn", "river"):
                        st_board = board_ids[:4] if st == "turn" else board_ids[:5]
                        self.bayes_range.update_range2(st_board, "call", 0, self.bayes_pot)
                self.bayes_pot += amt - self.bayes_opp_bet
                self.bayes_opp_bet = amt
            elif act in ("check", "limp"):
                if st == "preflop":
                    self.bayes_range.update_preflop("check")
                else:
                    if self.bayes_range.w2 is not None and st in ("turn", "river"):
                        st_board = board_ids[:4] if st == "turn" else board_ids[:5]
                        self.bayes_range.update_range2(st_board, "check", 0, self.bayes_pot)
        self.bayes_history_idx = len(hist)

    # ---------------------------------------------------------------- equity
    def get_blended_equity(self, req, mode, x, blend=0.0):
        """Returns (e_all, top) with range blending between Bayesian and v1.1."""
        board = [CARD_ID[c] for c in req.get("board") or []]
        street = len(board)
        if not HAVE_NP or mode == Governor.PANIC:
            e = scalar_equity(self.hole, board, self.dead, 40)
            return e, (lambda share: max(0.0, e - (1.0 - share) * 0.30))
        use_bayes = CFG.get("USE_BAYES", False) and self.bayes_range is not None and blend > 0.0
        if street == 3 and len(self.hole) == 3:
            sim = self.cache.get("flop")
            if sim is None:
                n = CFG["MC_FLOP"] >> mode
                opp3 = self.bayes_range.sample_opp3(n, self.rng, self.hole + board) if use_bayes else None
                sim = flop_equity(self.hole, board, n, self.rng, opp3=opp3)
                self.cache["flop"] = sim
            eq, key, win = sim
            w = np.ones(key.size)
            by_keep = [top_share_equity(win[k], key, w, x) for k in range(3)]
            best = int(np.argmax(by_keep))
            self.cache["keep"] = best
            return float(eq[best]), (lambda share: top_share_equity(win[best], key, w, share))

        b_key = int(round(blend * 100))
        ck = "s%d_b%d" % (street, b_key)
        got = self.cache.get(ck)
        if got is None:
            weights = None
            if use_bayes and self.bayes_range.w2 is not None:
                w2 = self.bayes_range.get_weights2(board)
                if w2 is not None and blend > 0.0:
                    w_v1 = np.ones(len(w2)) / float(len(w2))
                    weights = blend * w2 + (1.0 - blend) * w_v1
                    s = weights.sum()
                    if s > 0:
                        weights /= s
            if street == 4:
                step = (1, 2, 4)[mode]
                e, hands, strength, res = turn_equity(self.hole, board, self.dead, weights, step)
            else:
                e, hands, strength, res = river_equity(self.hole, board, self.dead, weights)
            got = (e, strength, res, weights if weights is not None else np.ones(res.size))
            self.cache[ck] = got
        e, strength, res, w = got
        return e, (lambda share: top_share_equity(res, strength, w, share))

    def _equity(self, req, mode, x):
        """Returns (e_all, top): top(share) = equity against the strongest
        `share` of the opponent's range. Also caches the flop keep choice."""
        blend = float(PARAMS.get("RANGE_BLEND", 0.0)) if CFG.get("POLICY", "learned") == "learned" else (1.0 if CFG.get("USE_BAYES", False) else 0.0)
        return self.get_blended_equity(req, mode, x, blend)

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
        if self.seat == "big_blind" and pf_raises == 1:
            nominal = CFG["PF_CALL_PFR_MULT"] * 0.45 + 0.05
            adapted = clamp(CFG["PF_CALL_PFR_MULT"] * self.opp.pfr_btn() + 0.05, nominal - 0.20, nominal + 0.20)
            call_q = min(call_q, adapted)
        if can_raise:
            if pf_raises == 1:
                t3 = CFG["PF_3BET_Q"]
                if self.seat == "big_blind":
                    t3 = t3 * clamp(self.opp.pfr_btn() / 0.45, 0.5, 2.0)
                if q <= t3:
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
            if e_r >= float(PARAMS.get("STACK_OFF_EQ", CFG["STACK_OFF_EQ"])):
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
        if to_call == 0:
            if can_raise:
                station = self.opp.is_station()
                R = 1.0 if self.seat == "button" else 0.85
                ev_check = R * e_r * pot
                best_bet = None
                best_ev = -1e9
                use_grid = CFG.get("USE_SIZE_GRID", False)
                bet_sizes = CFG["BET_GRID"] if use_grid else CFG["EV_BET_SIZES"]
                for frac in bet_sizes:
                    if frac > 1.0:
                        # 1.4 only when remaining stack covers it
                        target_amt = req.get("opp_bet", 0) + frac * (req["pot"] + req.get("to_call", 0))
                        if target_amt > req["max_raise"]:
                            continue
                    b_action = self._bet(req, frac, e_r)
                    if b_action is None:
                        continue
                    b = b_action["amount"]
                    if use_grid:
                        grid_idx = nearest_grid_idx(b / max(1.0, pot))
                        f_b, c_b, r_b = self.opp.grid_response_rates(grid_idx)
                    else:
                        bucket = bet_bucket(b / max(1.0, pot))
                        f_b, c_b, r_b = self.opp.response_rates(bucket)
                    e_call_b = top(max(CFG["SHRINK_FLOOR"], x * (1.0 - f_b)))
                    if station and e_call_b < 0.50:
                        continue
                    ev_b = f_b * pot + c_b * (e_call_b * (pot + 2.0 * b) - b) - r_b * b
                    if ev_b > best_ev:
                        best_ev = ev_b
                        best_bet = b_action
                if best_bet is not None and best_ev > ev_check:
                    if street == 5 and (best_ev - ev_check) < CFG["EV_MIX_MARGIN"] * pot:
                        if random.random() < 0.50:
                            return {"action": "check"}
                    return best_bet
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
        use_bayes = CFG.get("USE_BAYES", False) and HAVE_NP and mode != Governor.PANIC
        x, pf_raises = read_history(req.get("history"), self.seat, self.opp)
        if use_bayes:
            self._update_bayes_from_history(req.get("history"), req.get("board") or [])
        policy_mode = CFG.get("POLICY", "learned")
        if policy_mode == "learned" and mode != Governor.PANIC and HAVE_NP:
            r = decide_policy(req, self, mode, x, pf_raises, PARAMS, self.rng)
        elif req.get("street") == "preflop":
            r = self._preflop(req, pf_raises)
        else:
            if use_bayes and self.bayes_range.w2 is not None:
                x = 1.0  # NO DOUBLE COUNTING: opponent bets already narrowed the Bayesian range
            r = self._postflop(req, mode, x)
        r["type"] = "action"
        return r

    def discard(self, req):
        hid = int(req.get("hand_id") or self.hand_id)
        mode = self.gov.start(req, hid)
        cards = list(req.get("hole_cards") or self.hole_str)
        ids3 = [CARD_ID[c] for c in cards]
        flop = [CARD_ID[c] for c in (req.get("board") or [])[:3]]
        self.cache["board"] = list(req.get("board") or [])
        if HAVE_NP and mode != Governor.PANIC:
            self.hole, self.hole_str = ids3, cards
            if "keep" not in self.cache:
                self._equity({"board": req.get("board")}, mode, 1.0)
            return {"type": "discard", "card": cards[KEEPS[self.cache["keep"]][2]]}
        _, _, d = cheap_keep(ids3, flop)
        return {"type": "discard", "card": cards[ids3.index(d)]}
