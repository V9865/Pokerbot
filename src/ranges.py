"""Bayesian opponent range modeling for Discard Hold'em.

Range3: 22,100 combinations of 3 cards (preflop and flop before discard).
Range2: up to 990 combinations of 2 cards (turn, river, and post-discard flop).
Matches equity.opp_hands order so weights can be passed directly to
turn_equity, river_equity, and top_share_equity.
"""
import math
from config import CFG
from cards import CARD_ID
from preflop_table import hand_index, PF_Q, _C2, _C3
from evaluator import HAVE_NP, cheap_keep, cheap_keep_batch, cheap_key_batch

if HAVE_NP:
    import numpy as np
    from evaluator import eval_batch
    from equity import opp_hands

    # Precomputed combinations and masks
    ALL_COMBOS_3 = np.empty((22100, 3), dtype=np.int64)
    for _c in range(52):
        for _b in range(_c):
            for _a in range(_b):
                ALL_COMBOS_3[hand_index(_a, _b, _c)] = (_a, _b, _c)

    ALL_MASKS_3 = (1 << ALL_COMBOS_3[:, 0]) | (1 << ALL_COMBOS_3[:, 1]) | (1 << ALL_COMBOS_3[:, 2])
    _C2_ARR = np.array(_C2, dtype=np.int64)
    _C3_ARR = np.array(_C3, dtype=np.int64)
    Q3 = np.frombuffer(PF_Q, dtype=np.uint16) / 65535.0

    def sig(z):
        """Numerically stable sigmoid."""
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


class BayesRange:
    """Tracks opponent's Bayesian range through a hand."""

    def __init__(self, opp_model, dead_initial=None):
        self.opp_model = opp_model
        self.dead_initial = list(dead_initial) if dead_initial else []
        self.w3 = None
        self.w2 = None
        self.w2_hands = None

        if HAVE_NP:
            self.w3 = np.ones(22100, dtype=np.float64)
            if self.dead_initial:
                dead_mask = 0
                for c in self.dead_initial:
                    dead_mask |= (1 << c)
                clash = (ALL_MASKS_3 & dead_mask) != 0
                self.w3[clash] = 0.0
                live = ~clash
                if np.any(live):
                    self.w3[live] /= np.sum(self.w3[live])

    def update_preflop(self, action, amount=None, is_3bet=False, is_4bet=False):
        """Update Range3 on opponent preflop action."""
        if not HAVE_NP or self.w3 is None:
            return

        w = 0.06
        floor = 0.08

        if action == "raise":
            if is_4bet:
                t = 0.04
            elif is_3bet:
                t = 0.10
            else:
                t = self.opp_model.pfr_btn() if hasattr(self.opp_model, "pfr_btn") else 0.45
            lik = floor + (1.0 - floor) * sig((t - Q3) / w)
        elif action == "call":
            t_call = 0.80
            t_raise = self.opp_model.pfr_btn() if hasattr(self.opp_model, "pfr_btn") else 0.45
            lik = floor + (1.0 - floor) * sig((t_call - Q3) / w) * (1.0 - 0.6 * sig((0.5 * t_raise - Q3) / w))
        elif action in ("check", "limp"):
            t_raise = self.opp_model.pfr_btn() if hasattr(self.opp_model, "pfr_btn") else 0.45
            lik = 1.0 - 0.7 * sig((t_raise - Q3) / w)
        else:
            return

        live = (self.w3 > 0.0)
        self.w3[live] *= lik[live]
        # Weight floor at 0.05 * mean
        if np.any(live):
            mean_w = np.mean(self.w3[live])
            floor_w = 0.05 * mean_w
            self.w3[live] = np.maximum(self.w3[live], floor_w)
            total = np.sum(self.w3[live])
            if total > 0:
                self.w3[live] /= total

    def sample_opp3(self, n, rng, current_dead=None):
        """Sample n opponent 3-card hands from Range3."""
        if not HAVE_NP or self.w3 is None:
            return None

        p = self.w3.copy()
        if current_dead:
            dead_mask = 0
            for c in current_dead:
                dead_mask |= (1 << c)
            clash = (ALL_MASKS_3 & dead_mask) != 0
            p[clash] = 0.0

        total = np.sum(p)
        if total <= 0:
            live = (p > 0)
            if not np.any(live):
                live = ~clash
            p = live.astype(np.float64) / max(1, np.sum(live))
        else:
            p /= total

        cum = np.cumsum(p)
        r = rng.random(n) * cum[-1]
        indices = np.searchsorted(cum, r)
        indices = np.clip(indices, 0, len(ALL_COMBOS_3) - 1)
        return ALL_COMBOS_3[indices]

    def init_range2(self, hole2, board3, my_discard, opp_discard, discard_rule_probs=None):
        """Construct Range2 after opponent discard is revealed."""
        if not HAVE_NP:
            return

        dead_all = [c for c in (my_discard, opp_discard) if c is not None]
        hands, unseen = opp_hands(hole2, board3, dead_all)
        m = hands.shape[0]
        if m == 0:
            return

        self.w2_hands = hands

        # Find 3-card combination indices for triplets [opp_discard, c1, c2]
        triplets = np.column_stack([np.full(m, opp_discard, dtype=np.int64), hands])
        s_triplets = np.sort(triplets, axis=1)
        a, b, c = s_triplets[:, 0], s_triplets[:, 1], s_triplets[:, 2]
        idx3 = _C3_ARR[c] + _C2_ARR[b] + a

        prior_w = self.w3[idx3] if self.w3 is not None else np.ones(m)

        # Discard likelihood L(opp_discard | rule, hand)
        # 1. LOWEST rule: min card ID
        lowest_matches = (np.min(triplets, axis=1) == opp_discard)
        p_lowest = np.where(lowest_matches, 0.90, 0.05)

        # 2. CHEAP rule
        board_tile = np.tile(np.array(board3, dtype=np.int64), (m, 1))
        _, cheap_discs = cheap_keep_batch(triplets, board_tile)
        cheap_matches = (cheap_discs == opp_discard)
        p_cheap = np.where(cheap_matches, 0.90, 0.05)

        # 3. RANDOM rule
        p_random = 1.0 / 3.0

        probs = discard_rule_probs if discard_rule_probs is not None else [0.40, 0.40, 0.20]
        p_low, p_ch, p_rnd = probs[0], probs[1], probs[2]

        l_disc = p_low * p_lowest + p_ch * p_cheap + p_rnd * p_random

        w2 = prior_w * l_disc
        mean_w = np.mean(w2)
        floor_w = 0.05 * mean_w
        w2 = np.maximum(w2, floor_w)
        total = np.sum(w2)
        if total > 0:
            w2 /= total
        self.w2 = w2

    def get_weights2(self, board_ids):
        """Returns w2 aligned with opp_hands(hole, board_ids, dead). Filters out
        any cards that match board_ids (e.g. turn and river cards)."""
        if not HAVE_NP or self.w2 is None or self.w2_hands is None:
            return None
        board_raw = [b if isinstance(b, int) else CARD_ID[b] for b in board_ids]
        for b in board_raw[3:]:
            mask = (self.w2_hands[:, 0] != b) & (self.w2_hands[:, 1] != b)
            if not np.all(mask):
                self.w2_hands = self.w2_hands[mask]
                self.w2 = self.w2[mask]
                s = np.sum(self.w2)
                if s > 0:
                    self.w2 /= s
                else:
                    self.w2 = np.ones(len(self.w2)) / max(1, len(self.w2))
        return self.w2

    def update_range2(self, street_board, action, amount=None, pot=1.0, street=None, facing=False):
        """Update Range2 on opponent turn/river action.
        Follows no-double-counting rule: bet likelihood comes from Fix A s_k."""
        if not HAVE_NP or self.w2 is None or self.w2_hands is None:
            return

        board_raw = [b if isinstance(b, int) else CARD_ID[b] for b in street_board]
        self.get_weights2(board_raw)
        m = self.w2_hands.shape[0]
        b_tile = np.tile(np.array(board_raw, dtype=np.int64), (m, 1))
        eval_input = np.concatenate([self.w2_hands, b_tile], axis=1)
        scores = eval_batch(eval_input)

        # Strength percentile q (0 = strongest, 1 = weakest)
        ranks = np.argsort(np.argsort(-scores))
        q = ranks / float(max(1, m - 1))

        if action == "raise":
            frac = (amount or pot) / max(1.0, pot)
            # Learned bet size meaning s_k
            s_k = self.opp_model.shrink(frac) if hasattr(self.opp_model, "shrink") else 0.50
            if street and CFG.get("USE_FREQ_FLOOR", False) and hasattr(self.opp_model, "action_floor"):
                s_k = max(s_k, self.opp_model.action_floor(street, facing, frac))
            floor = float(CFG.get("SHRINK_FLOOR", 0.08))
            w = 0.05  # smoothed boundary over +-5 percentile points
            lik = floor + (1.0 - floor) * sig((s_k - q) / w)
        elif action == "call":
            w = 0.08
            floor = float(CFG.get("SHRINK_FLOOR", 0.08))
            t_call = 0.65
            lik = floor + (1.0 - floor) * sig((t_call - q) / w) * (1.0 - 0.5 * sig((0.10 - q) / w))
        elif action == "check":
            w = 0.08
            lik = 1.0 - 0.6 * sig((0.15 - q) / w)
        else:
            return

        self.w2 *= lik
        mean_w = np.mean(self.w2)
        floor_w = 0.05 * mean_w
        self.w2 = np.maximum(self.w2, floor_w)
        total = np.sum(self.w2)
        if total > 0:
            self.w2 /= total

