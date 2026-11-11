"""Equity against a (weighted) opponent range.

flop_equity   : sampled; scores all 3 of our keeps on the same samples
turn_equity   : exact over every opponent 2-card hand and every river card
river_equity  : exact over every opponent 2-card hand
All need numpy; scalar_equity is the slow fallback used without numpy.
Equity = P(win) + P(tie) / 2.
"""
import random
from evaluator import eval7, cheap_keep, HAVE_NP
if HAVE_NP:
    import numpy as np
    from evaluator import eval_batch, cheap_keep_batch, cheap_key_batch
    _KEEP_IDX = ((0, 1), (0, 2), (1, 2))
    _PAIR_CACHE = {}

    def _pairs(k):
        """All index pairs (i < j) for k cards, cached."""
        p = _PAIR_CACHE.get(k)
        if p is None:
            i, j = np.triu_indices(k, 1)
            p = (i.astype(np.int64), j.astype(np.int64))
            _PAIR_CACHE[k] = p
        return p

    def flop_equity(hole3, flop3, n, rng, opp3=None):
        """Our 3 hole cards and the flop (card ids). Returns
        (eq, opp_key, win): eq = equity of keeps (0,1), (0,2), (1,2);
        opp_key (n,) = cheap key of the opponent's best keep on the flop (their
        flop strength, for filtering 'hands that continue'); win (3, n) = per
        sample result of each keep (1 win, 0.5 tie, 0 loss).
        opp3: optional (n, 3) array of sampled opponent hands (from a weighted
        range); default = uniform random hands."""
        dead = list(hole3) + list(flop3)
        rest = np.array([c for c in range(52) if c not in dead], dtype=np.int64)
        if opp3 is None:
            pick = rest[np.argsort(rng.random((n, rest.size)), axis=1)[:, :5]]
            opp, tr = pick[:, :3], pick[:, 3:]
        else:
            opp = opp3
            n = opp.shape[0]
            keys = rng.random((n, 52))
            keys[:, dead] = 9.0
            keys[np.arange(n)[:, None], opp] = 9.0
            tr = np.argpartition(keys, 2, axis=1)[:, :2].astype(np.int64)
        flop = np.tile(np.array(flop3, dtype=np.int64), (n, 1))
        okeep, _ = cheap_keep_batch(opp, flop)
        board = np.concatenate([flop, tr], axis=1)
        osc = eval_batch(np.concatenate([okeep, board], axis=1))
        opp_key = np.maximum.reduce([cheap_key_batch(np.concatenate([opp[:, [i, j]], flop], axis=1))
                                     for i, j in _KEEP_IDX])
        win = np.empty((3, n))
        for k, (i, j) in enumerate(_KEEP_IDX):
            mine = np.tile(np.array([hole3[i], hole3[j]], dtype=np.int64), (n, 1))
            msc = eval_batch(np.concatenate([mine, board], axis=1))
            win[k] = (msc > osc) + 0.5 * (msc == osc)
        return win.mean(1), opp_key, win

    def opp_hands(hole2, board, dead):
        """All opponent 2-card hands from the unseen cards. Returns (hands (M,2), unseen)."""
        seen = set(hole2) | set(board) | set(dead)
        unseen = np.array([c for c in range(52) if c not in seen], dtype=np.int64)
        i, j = _pairs(unseen.size)
        return np.stack([unseen[i], unseen[j]], axis=1), unseen

    def river_equity(hole2, board5, dead, weights=None):
        """Exact. Returns (equity, hands (M,2), opp_scores (M,), result (M,))."""
        hands, _ = opp_hands(hole2, board5, dead)
        m = hands.shape[0]
        b = np.tile(np.array(board5, dtype=np.int64), (m, 1))
        osc = eval_batch(np.concatenate([hands, b], axis=1))
        msc = eval7(list(hole2) + list(board5))
        res = (msc > osc) + 0.5 * (msc == osc)
        w = np.ones(m) if weights is None else weights
        w_sum = w.sum()
        return float((res * w).sum() / (w_sum if w_sum > 0 else 1.0)), hands, osc, res

    def turn_equity(hole2, board4, dead, weights=None, river_step=1):
        """Exact over all opponent hands and river cards (river_step > 1 uses
        every n-th river card to save time). Returns
        (equity, hands (M,2), opp_now (M,), per_hand (M,)): opp_now = each hand's
        score on the turn board (6 cards); per_hand = our equity against each hand."""
        hands, unseen = opp_hands(hole2, board4, dead)
        m = hands.shape[0]
        rivers = unseen[::river_step]
        u = rivers.size
        b4 = np.array(board4, dtype=np.int64)
        ok = (hands[:, 0:1] != rivers[None, :]) & (hands[:, 1:2] != rivers[None, :])
        hi, ri = np.nonzero(ok)                      # only combos without a card clash
        rows = np.empty((hi.size, 7), dtype=np.int64)
        rows[:, 0:2] = hands[hi]
        rows[:, 2:6] = b4
        rows[:, 6] = rivers[ri]
        osc = eval_batch(rows)
        mine = np.empty((u, 7), dtype=np.int64)
        mine[:, 0:2] = np.array(hole2, dtype=np.int64)
        mine[:, 2:6] = b4
        mine[:, 6] = rivers
        msc = eval_batch(mine)[ri]
        res = (msc > osc) + 0.5 * (msc == osc)
        per_hand = np.bincount(hi, weights=res, minlength=m) / np.maximum(ok.sum(1), 1)
        opp_now = eval_batch(np.concatenate([hands, np.tile(b4, (m, 1))], axis=1))
        w = np.ones(m) if weights is None else weights
        w_sum = w.sum()
        return float((per_hand * w).sum() / (w_sum if w_sum > 0 else 1.0)), hands, opp_now, per_hand

    def top_share_equity(result, strength, weights, share):
        """Equity against only the strongest `share` (by weight) of the range.
        result: our outcome vs each hand/sample; strength: opponent strength."""
        w_sum = weights.sum()
        if share >= 0.999 or w_sum <= 0:
            return float((result * weights).sum() / (w_sum if w_sum > 0 else 1.0))
        order = np.argsort(-strength, kind="stable")
        w = weights[order]
        cum = np.cumsum(w)
        cut = share * cum[-1]
        k = int(np.searchsorted(cum, cut)) + 1
        k = max(1, min(k, w.size))
        k_sum = w[:k].sum()
        return float((result[order][:k] * w[:k]).sum() / (k_sum if k_sum > 0 else 1.0))


def scalar_equity(hole, board, dead, n, rnd=random):
    """Fallback without numpy: plain Monte Carlo vs a uniform random hand.
    hole: our 2 or 3 cards; if 3 (flop, before the discard) both sides discard
    by the cheap rule. Returns the equity of the cheap-rule keep."""
    seen = set(hole) | set(board) | set(dead)
    deck = [c for c in range(52) if c not in seen]
    need = 5 - len(board)
    pre = len(hole) == 3
    if pre:
        a, b, _ = cheap_keep(hole, board[:3])
        mine = [a, b]
    else:
        mine = list(hole)
    tot = 0.0
    for _ in range(n):
        pick = rnd.sample(deck, (3 if pre else 2) + need)
        if pre:
            x, y, _ = cheap_keep(pick[:3], board[:3])
            opp, extra = [x, y], pick[3:]
        else:
            opp, extra = pick[:2], pick[2:]
        full = list(board) + extra
        m, o = eval7(mine + full), eval7(opp + full)
        tot += 1.0 if m > o else (0.5 if m == o else 0.0)
    return tot / max(1, n)
