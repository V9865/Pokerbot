"""Hand-strength, potential, blocker, and texture features.

Features are computed once per decision in FULL mode (under 15-25 ms) and cached.
In PANIC mode or pure-Python fallback, fast scalar approximations are used.
All returned features are floats within well-defined ranges [0, 1].
"""
import itertools, math, random
from cards import CARD_ID, CARD_STR
from evaluator import eval7, cheap_keep, HAVE_NP
import preflop_table

if HAVE_NP:
    import numpy as np
    from evaluator import eval_batch, cheap_keep_batch
    from equity import opp_hands, river_equity, top_share_equity

# ------------------------------------------------------------- Precomputed tables
# Precompute the unconditioned top 10% 3-card preflop hands (for block_top10)
_TOP10_PREFLOP_HANDS = None

def _get_top10_preflop_hands():
    global _TOP10_PREFLOP_HANDS
    if _TOP10_PREFLOP_HANDS is None:
        combos = list(itertools.combinations(range(52), 3))
        # Top 10% hands from preflop_table (q <= 0.10)
        top_list = [h for h in combos if preflop_table.preflop_q(*h) <= 0.10]
        if HAVE_NP:
            _TOP10_PREFLOP_HANDS = np.array(top_list, dtype=np.int64)
        else:
            _TOP10_PREFLOP_HANDS = [set(h) for h in top_list]
    return _TOP10_PREFLOP_HANDS


def blocker_top10(our_cards):
    """Share of the top 10% of opponent's unconditioned 3-card preflop range
    removed (blocked) by our cards. Float in [0.0, 1.0]."""
    top10 = _get_top10_preflop_hands()
    n = len(top10)
    if n == 0:
        return 0.0
    if HAVE_NP and isinstance(top10, np.ndarray):
        blocked = np.isin(top10, list(our_cards)).any(axis=1).sum()
        return float(blocked / n)
    else:
        our_set = set(our_cards)
        blocked = sum(1 for h in top10 if our_set.intersection(h))
        return float(blocked / n)


def board_texture(board):
    """Returns (tex_flush, tex_straight, tex_paired).
    - tex_flush: 0.0 (no flush possible), 0.5 (flush draw possible, 2 of suit), 1.0 (flush possible, >=3 of suit).
    - tex_straight: 0.0 (no straight possible), 0.5 (straight draw possible, 2 ranks in 5-rank window),
                    1.0 (straight possible with 2 hole cards, >=3 ranks in 5-rank window).
    - tex_paired: 1.0 if board has duplicate ranks, else 0.0.
    """
    if not board:
        return 0.0, 0.0, 0.0
    # Flush texture
    suits = [c & 3 for c in board]
    max_s = max(suits.count(s) for s in range(4)) if suits else 0
    tex_flush = 1.0 if max_s >= 3 else 0.5 if max_s == 2 else 0.0

    # Paired texture
    ranks = [c >> 2 for c in board]
    tex_paired = 1.0 if len(ranks) != len(set(ranks)) else 0.0

    # Straight texture
    if len(board) < 2:
        tex_straight = 0.0
    else:
        r_set = set(ranks)
        if 12 in r_set: # Ace can be low
            r_set.add(-1)
        max_in_window = 0
        for low in range(-1, 9):
            window = set(range(low, low + 5))
            cnt = len(r_set.intersection(window))
            if cnt > max_in_window:
                max_in_window = cnt
        tex_straight = 1.0 if max_in_window >= 3 else 0.5 if max_in_window == 2 else 0.0

    return tex_flush, tex_straight, tex_paired


# ------------------------------------------------------------- Features computation
_FEATURE_CACHE = {}

def clear_feature_cache():
    global _FEATURE_CACHE
    _FEATURE_CACHE.clear()


def compute_features(hole, board, dead=None, opp_weights=None, opp_discard=None, p_lowest=0.5, panic=False):
    """Compute hand-strength, potential, blocker, and texture features.
    
    Parameters:
      hole: list of 2 or 3 card ids
      board: list of card ids (flop, turn, or river)
      dead: list of known dead card ids (e.g. discards)
      opp_weights: optional weights over opp 2-card hands (for turn/river)
      opp_discard: optional card id of opponent's discard
      p_lowest: posterior probability that opponent discards by LOWEST rule
      panic: if True, returns cheap approximations
      
    Returns dict:
      e_show, e_now, ehs2, ppot, npot, e_top25, e_top50, rank_in_range,
      block_top10, tex_flush, tex_straight, tex_paired, opp_disc_rank, p_lowest
    """
    dead_tuple = tuple(sorted(dead)) if dead else ()
    cache_key = (tuple(hole), tuple(board), dead_tuple, id(opp_weights), opp_discard, panic)
    if cache_key in _FEATURE_CACHE:
        return _FEATURE_CACHE[cache_key]

    tex_flush, tex_straight, tex_paired = board_texture(board)
    block_top = blocker_top10(hole)
    opp_disc_r = (opp_discard >> 2) / 12.0 if opp_discard is not None else 0.5

    # Base dictionary for preflop or cheap fallback
    st = len(board)
    if st == 0 or panic or not HAVE_NP:
        # Preflop or panic/fallback approximation
        if len(hole) == 3:
            e_base = preflop_table.preflop_equity(*hole) if st == 0 else 0.50
        else:
            e_base = 0.50
        out = {
            "e_show": float(e_base),
            "e_now": float(e_base),
            "ehs2": float(e_base ** 2),
            "ppot": 0.0,
            "npot": 0.0,
            "e_top25": float(max(0.0, e_base * 0.6)),
            "e_top50": float(max(0.0, e_base * 0.8)),
            "rank_in_range": float(e_base),
            "block_top10": float(block_top),
            "tex_flush": float(tex_flush),
            "tex_straight": float(tex_straight),
            "tex_paired": float(tex_paired),
            "opp_disc_rank": float(opp_disc_r),
            "p_lowest": float(p_lowest),
        }
        _FEATURE_CACHE[cache_key] = out
        return out

    # ------------------------------------------------------------- River (5 board cards)
    if st == 5:
        # 2 hole cards on river
        h2 = hole[:2] if len(hole) > 2 else hole
        e_show, hands, osc, res = river_equity(h2, board, dead or [], weights=opp_weights)
        msc = eval7(list(h2) + list(board))
        w = np.ones(hands.shape[0]) if opp_weights is None else opp_weights
        
        # rank_in_range: weighted fraction of opponent hands strictly beaten
        beaten = (msc > osc).astype(np.float64)
        rank_in_range = float((beaten * w).sum() / w.sum()) if w.sum() > 0 else e_show

        # e_top25, e_top50
        e_top25 = top_share_equity(res, osc, w, 0.25)
        e_top50 = top_share_equity(res, osc, w, 0.50)

        out = {
            "e_show": float(e_show),
            "e_now": float(e_show),
            "ehs2": float(e_show ** 2),
            "ppot": 0.0,
            "npot": 0.0,
            "e_top25": float(e_top25),
            "e_top50": float(e_top50),
            "rank_in_range": float(rank_in_range),
            "block_top10": float(block_top),
            "tex_flush": float(tex_flush),
            "tex_straight": float(tex_straight),
            "tex_paired": float(tex_paired),
            "opp_disc_rank": float(opp_disc_r),
            "p_lowest": float(p_lowest),
        }
        _FEATURE_CACHE[cache_key] = out
        return out

    # ------------------------------------------------------------- Turn (4 board cards)
    if st == 4:
        h2 = hole[:2] if len(hole) > 2 else hole
        hands, unseen = opp_hands(h2, board, dead or [])
        m = hands.shape[0]
        u = unseen.size
        b4 = np.array(board, dtype=np.int64)
        
        ok = (hands[:, 0:1] != unseen[None, :]) & (hands[:, 1:2] != unseen[None, :])
        hi, ri = np.nonzero(ok)
        
        rows = np.empty((hi.size, 7), dtype=np.int64)
        rows[:, 0:2] = hands[hi]
        rows[:, 2:6] = b4
        rows[:, 6] = unseen[ri]
        osc = eval_batch(rows)
        
        mine = np.empty((u, 7), dtype=np.int64)
        mine[:, 0:2] = np.array(h2, dtype=np.int64)
        mine[:, 2:6] = b4
        mine[:, 6] = unseen
        msc = eval_batch(mine)[ri]
        
        res = (msc > osc).astype(np.float32) + 0.5 * (msc == osc)
        res_mat = np.zeros((m, u), dtype=np.float32)
        res_mat[hi, ri] = res
        
        # Current 6-card scores on turn board
        my_now = eval_batch(np.concatenate([np.array([h2], dtype=np.int64), np.tile(b4, (1, 1))], axis=1))[0]
        opp_now = eval_batch(np.concatenate([hands, np.tile(b4, (m, 1))], axis=1))
        
        w = np.ones(m) if opp_weights is None else opp_weights
        w_sum = w.sum()
        
        # e_now and rank_in_range
        e_now = float((((my_now > opp_now) + 0.5 * (my_now == opp_now)) * w).sum() / w_sum)
        rank_in_range = float(((my_now > opp_now) * w).sum() / w_sum)
        
        # e_show
        per_hand = np.bincount(hi, weights=res, minlength=m) / np.maximum(ok.sum(1), 1)
        e_show = float((per_hand * w).sum() / w_sum)
        
        # ehs2
        eq_by_river = (res_mat * w[:, None]).sum(axis=0) / np.maximum((ok * w[:, None]).sum(axis=0), 1e-6)
        ehs2 = float(np.mean(eq_by_river ** 2))
        
        # ppot and npot
        behind = opp_now > my_now
        ahead = opp_now < my_now
        
        w_behind = (ok[behind] * w[behind, None]).sum()
        ppot = float((res_mat[behind] * w[behind, None] * ok[behind]).sum() / w_behind) if w_behind > 0 else 0.0
        
        w_ahead = (ok[ahead] * w[ahead, None]).sum()
        npot = float(((1.0 - res_mat[ahead]) * w[ahead, None] * ok[ahead]).sum() / w_ahead) if w_ahead > 0 else 0.0
        
        # e_top25 and e_top50
        e_top25 = top_share_equity(per_hand, opp_now, w, 0.25)
        e_top50 = top_share_equity(per_hand, opp_now, w, 0.50)
        
        out = {
            "e_show": float(e_show),
            "e_now": float(e_now),
            "ehs2": float(ehs2),
            "ppot": float(ppot),
            "npot": float(npot),
            "e_top25": float(e_top25),
            "e_top50": float(e_top50),
            "rank_in_range": float(rank_in_range),
            "block_top10": float(block_top),
            "tex_flush": float(tex_flush),
            "tex_straight": float(tex_straight),
            "tex_paired": float(tex_paired),
            "opp_disc_rank": float(opp_disc_r),
            "p_lowest": float(p_lowest),
        }
        _FEATURE_CACHE[cache_key] = out
        return out

    # ------------------------------------------------------------- Flop (3 board cards)
    if st == 3:
        # Hole can be 3 cards (before discard) or 2 cards (after discard)
        if len(hole) == 3:
            a, b, _ = cheap_keep(hole, board)
            my_keep = np.array([a, b], dtype=np.int64)
        else:
            my_keep = np.array(hole[:2], dtype=np.int64)

        seen = set(hole) | set(board) | set(dead or [])
        unseen = np.array([c for c in range(52) if c not in seen], dtype=np.int64)
        rng = np.random.default_rng(42)

        N = min(120, unseen.size * (unseen.size - 1) // 2)
        K = 40
        
        # Sample N opponent 3-card hands
        opp3 = np.empty((N, 3), dtype=np.int64)
        for i in range(N):
            opp3[i] = rng.choice(unseen, size=3, replace=False)
            
        flop_tile = np.tile(np.array(board, dtype=np.int64), (N, 1))
        opp_keep, _ = cheap_keep_batch(opp3, flop_tile)
        
        # Flop scores (5-card hands)
        my_flop_score = eval_batch(np.concatenate([my_keep[None, :], np.array([board], dtype=np.int64)], axis=1))[0]
        opp_flop_scores = eval_batch(np.concatenate([opp_keep, flop_tile], axis=1))
        
        e_now = float(((my_flop_score > opp_flop_scores) + 0.5 * (my_flop_score == opp_flop_scores)).mean())
        rank_in_range = float((my_flop_score > opp_flop_scores).mean())
        
        # Sample K=40 runouts per hand without card clash
        tr_runouts = np.empty((N, K, 2), dtype=np.int64)
        for i in range(N):
            avail = unseen[~np.isin(unseen, opp3[i])]
            idx = rng.choice(avail.size, size=(K, 2), replace=True)
            r_idx = idx[:, 1]
            same = idx[:, 0] == r_idx
            r_idx[same] = (r_idx[same] + 1) % avail.size
            tr_runouts[i, :, 0] = avail[idx[:, 0]]
            tr_runouts[i, :, 1] = avail[r_idx]
            
        tr_flat = tr_runouts.reshape((N * K, 2))
        opp_rep = np.repeat(opp_keep, K, axis=0)
        flop_rep = np.tile(np.array(board, dtype=np.int64), (N * K, 1))

        rows_opp = np.concatenate([opp_rep, flop_rep, tr_flat], axis=1)
        rows_mine = np.concatenate([np.tile(my_keep, (N * K, 1)), flop_rep, tr_flat], axis=1)

        osc = eval_batch(rows_opp)
        msc = eval_batch(rows_mine)
        res = ((msc > osc).astype(np.float32) + 0.5 * (msc == osc)).reshape((N, K))
        
        e_show = float(res.mean())
        
        behind = opp_flop_scores > my_flop_score
        ahead = opp_flop_scores < my_flop_score

        ppot = float(res[behind].mean()) if behind.any() else 0.0
        npot = float((1.0 - res[ahead]).mean()) if ahead.any() else 0.0

        eq_by_runout = res.mean(axis=0)
        ehs2 = float(np.mean(eq_by_runout ** 2))
        
        # e_top25 and e_top50
        per_opp = res.mean(axis=1)
        e_top25 = top_share_equity(per_opp, opp_flop_scores, np.ones(N), 0.25)
        e_top50 = top_share_equity(per_opp, opp_flop_scores, np.ones(N), 0.50)

        out = {
            "e_show": float(e_show),
            "e_now": float(e_now),
            "ehs2": float(ehs2),
            "ppot": float(ppot),
            "npot": float(npot),
            "e_top25": float(e_top25),
            "e_top50": float(e_top50),
            "rank_in_range": float(rank_in_range),
            "block_top10": float(block_top),
            "tex_flush": float(tex_flush),
            "tex_straight": float(tex_straight),
            "tex_paired": float(tex_paired),
            "opp_disc_rank": float(opp_disc_r),
            "p_lowest": float(p_lowest),
        }
        _FEATURE_CACHE[cache_key] = out
        return out

    # Default fallback
    return {
        "e_show": 0.5, "e_now": 0.5, "ehs2": 0.25, "ppot": 0.0, "npot": 0.0,
        "e_top25": 0.3, "e_top50": 0.4, "rank_in_range": 0.5,
        "block_top10": float(block_top), "tex_flush": float(tex_flush),
        "tex_straight": float(tex_straight), "tex_paired": float(tex_paired),
        "opp_disc_rank": float(opp_disc_r), "p_lowest": float(p_lowest),
    }

