"""Opponent modeling and statistics tracking (per-leg)."""
import math
import random
from config import CFG
from cards import CARD_ID
from evaluator import cheap_keep

try:
    import numpy as np
    from evaluator import eval_batch
    HAVE_NP = True
except Exception:
    HAVE_NP = False


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def bet_bucket(frac):
    """0 = small (< 0.40 pot), 1 = med (0.40 - 0.80), 2 = large (0.80 - 1.30), 3 = overbet (> 1.30)."""
    if frac < 0.40:
        return 0
    if frac < 0.80:
        return 1
    if frac < 1.30:
        return 2
    return 3


def nearest_grid_idx(frac):
    """Index of the nearest bet-size grid point in CFG['BET_GRID']."""
    grid = CFG["BET_GRID"]
    best_i = 0
    best_d = abs(frac - grid[0])
    for i in range(1, len(grid)):
        d = abs(frac - grid[i])
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


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
        # Fix A: learned opponent bet size meaning
        self.opp_bet_sum_p = [0.0, 0.0, 0.0, 0.0]
        self.opp_bet_count = [0, 0, 0, 0]
        # Fix B: response rates to our bets [fold, call, raise] per bucket
        self.our_bet_counts = [[0, 0, 0] for _ in range(4)]
        # Bet-size grid counts (kept for features / Phase 3)
        self.grid_counts = [[0, 0, 0] for _ in range(len(CFG.get("BET_GRID", (0.25, 0.33, 0.45, 0.60, 0.75, 1.00, 1.40))))]
        # Fix C: opponent button first-in raise tracking
        self.btn_opps = 0
        self.btn_raises = 0
        # Discard rule posterior: [P(LOWEST), P(CHEAP), P(RANDOM)]
        self.discard_rule_probs = [0.40, 0.40, 0.20]
        # Big bet honesty tracking: fraction of big bets (> 0.8 pot) showing top 30% strength
        self.opp_big_bets_faced = 0
        self.opp_big_bet_showdown_strong = 0
        # Betting frequency (no showdown needed): [opportunities, bets] per street when
        # not facing a bet, and [times facing our bet, raises]. Floors the range share
        # kept after a bet, so an opponent who bets most hands is not read as strong.
        self.bet_opps = {"flop": [0, 0], "turn": [0, 0], "river": [0, 0]}
        self.raise_opps = [0, 0]
        self.bet_size_counts = [0, 0, 0, 0]   # their bets (not facing ours) by size bucket

    def p_lowest(self):
        return self.discard_rule_probs[0]

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

    def pfr_btn(self):
        return (self.btn_raises + 10.0 * 0.45) / (self.btn_opps + 10.0)

    def big_bet_honesty(self):
        return (self.opp_big_bet_showdown_strong + 2.0 * 0.50) / (self.opp_big_bets_faced + 2.0)

    def bet_freq(self, street):
        n, k = self.bet_opps.get(street, (0, 0))
        w = float(CFG["FREQ_PRIOR_WEIGHT"])
        return (k + w * CFG["FREQ_PRIOR_BET"]) / (n + w)

    def raise_freq(self):
        n, k = self.raise_opps
        w = float(CFG["FREQ_PRIOR_WEIGHT"])
        return (k + w * CFG["FREQ_PRIOR_RAISE"]) / (n + w)

    def size_freq(self, frac):
        """How often they bet THIS size when they could bet (all streets pooled)."""
        n = sum(v[0] for v in self.bet_opps.values())
        k = self.bet_size_counts[bet_bucket(frac)]
        w = float(CFG["FREQ_PRIOR_WEIGHT"])
        return (k + w * 0.08) / (n + w)

    def action_floor(self, street, facing, frac=None):
        """Minimum share of their range that an opponent bet (facing=False) or
        raise (facing=True) can represent, from how often they take that action.
        For bets the frequency of that bet SIZE is used, so a bot that bets often
        but makes big bets rarely still has its big bets read as strong."""
        if facing:
            f = self.raise_freq()
        elif frac is not None and CFG.get("FREQ_FLOOR_BY_SIZE", True):
            f = self.size_freq(frac)
        else:
            f = self.bet_freq(street)
        return clamp(CFG["FREQ_FLOOR_MULT"] * f, 0.0, 0.95)

    def shrink(self, frac):
        k = bet_bucket(frac)
        priors = (CFG["SHRINK_BET_SMALL"], CFG["SHRINK_BET_MED"], CFG["SHRINK_BET_LARGE"], CFG["SHRINK_BET_OVER"])
        prior = priors[k]
        cnt = self.opp_bet_count[k]
        if cnt == 0:
            return prior
        mean_p = self.opp_bet_sum_p[k] / cnt
        s_raw = clamp(2.0 * mean_p, 0.08, 1.0)
        w = float(CFG["SHRINK_PRIOR_WEIGHT"])
        s = clamp((cnt * s_raw + w * prior) / (cnt + w), 0.08, 1.0)
        if cnt < 30:
            s = clamp(s, prior - 0.22, prior + 0.22)
        return s

    def response_rates(self, bucket):
        k = clamp(bucket, 0, 3)
        priors = ((0.30, 0.60, 0.10), (0.40, 0.50, 0.10), (0.50, 0.42, 0.08), (0.60, 0.38, 0.02))[k]
        counts = self.our_bet_counts[k]
        w = float(CFG["EV_PRIOR_WEIGHT"])
        denom = sum(counts) + w
        f = (counts[0] + w * priors[0]) / denom
        c = (counts[1] + w * priors[1]) / denom
        r = (counts[2] + w * priors[2]) / denom
        if sum(counts) < 40:
            f_clamped = clamp(f, priors[0] - 0.30, priors[0] + 0.30)
            if f != f_clamped:
                diff = f_clamped - f
                f = f_clamped
                c_r = c + r
                if c_r > 0:
                    c -= diff * (c / c_r)
                    r -= diff * (r / c_r)
        return f, c, r

    def grid_response_rates(self, idx):
        grid = CFG["BET_GRID"]
        priors_list = CFG["BET_GRID_PRIORS"]
        k = clamp(idx, 0, len(grid) - 1)
        prior = priors_list[k]

        nbrs = []
        if k > 0:
            nbrs.append(k - 1)
        if k < len(grid) - 1:
            nbrs.append(k + 1)

        counts_k = self.grid_counts[k]
        eff_f = counts_k[0] + 0.5 * sum(self.grid_counts[n][0] for n in nbrs)
        eff_c = counts_k[1] + 0.5 * sum(self.grid_counts[n][1] for n in nbrs)
        eff_r = counts_k[2] + 0.5 * sum(self.grid_counts[n][2] for n in nbrs)

        w = float(CFG["EV_PRIOR_WEIGHT"])
        denom = eff_f + eff_c + eff_r + w
        f = (eff_f + w * prior[0]) / denom
        c = (eff_c + w * prior[1]) / denom
        r = (eff_r + w * prior[2]) / denom

        total_obs = sum(counts_k) + sum(sum(self.grid_counts[n]) for n in nbrs)
        if total_obs < 40:
            f_clamped = clamp(f, prior[0] - 0.30, prior[0] + 0.30)
            if f != f_clamped:
                diff = f_clamped - f
                f = f_clamped
                c_r = c + r
                if c_r > 0:
                    c -= diff * (c / c_r)
                    r -= diff * (r / c_r)
        return f, c, r

    def folds_enough(self, size):
        return (self.bets_faced >= CFG["EXPLOIT_MIN_BETS"] and
                self.fold_to_bet() >= size / (1.0 + size) + CFG["EXPLOIT_MARGIN"])

    def is_station(self):
        return self.bets_faced >= CFG["STATION_MIN"] and self.fold_to_bet() < CFG["STATION_FOLD"]

    def observe_hand(self, history, my_seat="button"):
        self.hands += 1
        if my_seat == "big_blind":
            self.btn_opps += 1
            first_pf = None
            for e in history or []:
                if e.get("street") == "preflop":
                    first_pf = e
                    break
            if first_pf and first_pf.get("actor") == "opp" and first_pf.get("action") == "raise":
                self.btn_raises += 1

        street = None
        facing = False
        big = False
        my_bet, opp_bet = 0, 0
        pot = 3
        last_our_bucket = None
        last_our_grid_idx = None

        for e in history or []:
            st, who, act = e.get("street"), e.get("actor"), e.get("action")
            if st != street:
                street, facing = st, False
                if st == "preflop" or (my_seat == "button" and not CFG.get("FIX_BUCKET", True)):
                    my_bet, opp_bet = (1, 2) if my_seat == "button" else (2, 1)
                else:
                    my_bet, opp_bet = 0, 0
                last_our_bucket = None
                last_our_grid_idx = None

            amt = e.get("amount")
            if who == "me":
                if act == "raise" and amt is not None:
                    if st != "preflop":
                        # size of our bet/raise relative to the pot after we call theirs
                        if CFG.get("FIX_BUCKET", True):
                            frac = (amt - opp_bet) / max(1.0, pot + (opp_bet - my_bet))
                        else:   # v1.1 behaviour (records sizes in the wrong bucket)
                            frac = (amt - opp_bet) / max(1.0, pot - (amt - my_bet))
                        last_our_bucket = bet_bucket(frac)
                        last_our_grid_idx = nearest_grid_idx(frac)
                    pot += amt - my_bet
                    my_bet = amt
                    facing = True
                elif act == "call":
                    amt = opp_bet if amt is None else amt
                    pot += amt - my_bet
                    my_bet = amt
                    facing = False
                    last_our_bucket = None
                    last_our_grid_idx = None
                else:
                    facing = False
                    last_our_bucket = None
                    last_our_grid_idx = None
                continue

            # who == "opp"
            if st == "preflop":
                if act == "raise" and (amt or 0) >= 40:
                    big = True
                if facing:
                    self.pf_raises_faced += 1
                    if act == "fold":
                        self.pf_folds += 1
                facing = False
            else:
                self.post_actions += 1
                if act == "raise":
                    self.post_aggr += 1
                if act in ("check", "raise", "call", "fold"):
                    if facing:
                        self.raise_opps[0] += 1
                        if act == "raise":
                            self.raise_opps[1] += 1
                    elif st in self.bet_opps and act in ("check", "raise"):
                        self.bet_opps[st][0] += 1
                        if act == "raise":
                            self.bet_opps[st][1] += 1
                            if amt is not None:
                                bf = (amt - my_bet) / max(1.0, pot + (my_bet - opp_bet))
                                self.bet_size_counts[bet_bucket(bf)] += 1
                if facing:
                    self.bets_faced += 1
                    if act == "fold":
                        self.folds_to_bet += 1
                if last_our_bucket is not None:
                    if act == "fold":
                        self.our_bet_counts[last_our_bucket][0] += 1
                        self.grid_counts[last_our_grid_idx][0] += 1
                    elif act == "call":
                        self.our_bet_counts[last_our_bucket][1] += 1
                        self.grid_counts[last_our_grid_idx][1] += 1
                    elif act == "raise":
                        self.our_bet_counts[last_our_bucket][2] += 1
                        self.grid_counts[last_our_grid_idx][2] += 1
                    last_our_bucket = None
                    last_our_grid_idx = None
                facing = False

            if act == "raise" and amt is not None:
                pot += amt - opp_bet
                opp_bet = amt
            elif act == "call":
                amt = my_bet if amt is None else amt
                pot += amt - opp_bet
                opp_bet = amt

        if big:
            self.big_pf += 1

    def observe_showdown(self, opp_hole_cards, opp_discard, board, history, my_seat="button"):
        if not HAVE_NP or not opp_hole_cards or not board:
            return
        opp_hole = [CARD_ID[c] for c in opp_hole_cards if c in CARD_ID]
        if len(opp_hole) < 2:
            return
        opp_disc_id = CARD_ID.get(opp_discard)
        opp3 = opp_hole + ([opp_disc_id] if opp_disc_id is not None else [])
        board_ids = [CARD_ID[c] for c in board if c in CARD_ID]

        # Learn discard rule
        if opp_disc_id is not None and len(opp_hole) == 2 and len(board_ids) >= 3:
            triplet = opp_hole + [opp_disc_id]
            low_match = (min(triplet) == opp_disc_id)
            _, _, cheap_d = cheap_keep(triplet, board_ids[:3])
            ch_match = (cheap_d == opp_disc_id)

            l_low = 0.90 if low_match else 0.05
            l_ch = 0.90 if ch_match else 0.05
            l_rnd = 1.0 / 3.0

            probs = [
                self.discard_rule_probs[0] * l_low,
                self.discard_rule_probs[1] * l_ch,
                self.discard_rule_probs[2] * l_rnd,
            ]
            s = sum(probs)
            if s > 0:
                probs = [p / s for p in probs]
            probs = [max(0.02, p) for p in probs]
            s2 = sum(probs)
            self.discard_rule_probs = [p / s2 for p in probs]

        my_bet, opp_bet = (1, 2) if my_seat == "button" else (2, 1)
        pot = 3
        street = "preflop"
        opp_bets = []

        for e in history or []:
            st, who, act = e.get("street"), e.get("actor"), e.get("action")
            if st != street:
                street, my_bet, opp_bet = st, 0, 0
            amt = e.get("amount")
            if who == "me":
                if act == "raise" and amt is not None:
                    pot += amt - my_bet
                    my_bet = amt
                elif act == "call":
                    amt = opp_bet if amt is None else amt
                    pot += amt - my_bet
                    my_bet = amt
                continue
            if act == "raise" and amt is not None:
                if st != "preflop":
                    frac = (amt - my_bet) / max(1.0, pot + (my_bet - opp_bet))
                    opp_bets.append((st, bet_bucket(frac), frac))
                pot += amt - opp_bet
                opp_bet = amt
            elif act == "call":
                amt = my_bet if amt is None else amt
                pot += amt - opp_bet
                opp_bet = amt

        if not opp_bets:
            return

        for st, bucket, frac in opp_bets:
            if st == "flop":
                b = board_ids[:3]
                if len(b) < 3:
                    continue
                if len(opp3) == 3:
                    a, b_k, _ = cheap_keep(opp3, b)
                    cards2 = [a, b_k]
                else:
                    cards2 = opp_hole
                b4_arr = np.array(b, dtype=np.int64)   # flop strength on the flop only (no future cards)
            elif st == "turn":
                if len(board_ids) < 4:
                    continue
                cards2 = opp_hole
                b4_arr = np.array(board_ids[:4], dtype=np.int64)
            else:
                if len(board_ids) < 5:
                    continue
                cards2 = opp_hole
                eval_row = np.array([cards2 + board_ids[:5]], dtype=np.int64)
                actual_score = eval_batch(eval_row)[0]
                seen = set(cards2) | set(board_ids[:5])
                unseen = [c for c in range(52) if c not in seen]
                opp_rows = []
                for i in range(len(unseen)):
                    for j in range(i + 1, len(unseen)):
                        opp_rows.append([unseen[i], unseen[j]] + board_ids[:5])
                all_scores = eval_batch(np.array(opp_rows, dtype=np.int64))
                p = float(np.mean(all_scores > actual_score) + 0.5 * np.mean(all_scores == actual_score))
                self.opp_bet_sum_p[bucket] += p
                self.opp_bet_count[bucket] += 1
                if frac > 0.8:
                    self.opp_big_bets_faced += 1
                    if p <= 0.30:
                        self.opp_big_bet_showdown_strong += 1
                continue

            seen = set(cards2) | set(board_ids[:len(b4_arr)])
            unseen = [c for c in range(52) if c not in seen]
            opp_rows = []
            for i in range(len(unseen)):
                for j in range(i + 1, len(unseen)):
                    opp_rows.append([unseen[i], unseen[j]] + list(b4_arr[:4]))
            all_scores = eval_batch(np.array(opp_rows, dtype=np.int64))
            actual_score = eval_batch(np.array([cards2 + list(b4_arr[:4])], dtype=np.int64))[0]
            p = float(np.mean(all_scores > actual_score) + 0.5 * np.mean(all_scores == actual_score))
            self.opp_bet_sum_p[bucket] += p
            self.opp_bet_count[bucket] += 1
            if frac > 0.8:
                self.opp_big_bets_faced += 1
                if p <= 0.30:
                    self.opp_big_bet_showdown_strong += 1

