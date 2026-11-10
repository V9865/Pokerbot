"""Hand evaluation. Scalar eval7 (pure Python) and eval_batch (numpy), which
return IDENTICAL scores. Higher score wins; equal scores tie.
score = category << 20 | tie-break bits; category 0 high card .. 8 straight flush.
"""
try:
    import numpy as np
    HAVE_NP = True
except Exception:  # the bot must still run (degraded) without numpy
    np = None
    HAVE_NP = False

BITS = [bin(m).count("1") for m in range(8192)]
STRAIGHT = [0] * 8192   # 0 = none, else high-card rank + 1 (wheel = 4)
TOP5 = [0] * 8192       # mask with only its 5 highest bits kept
TOP3 = [0] * 8192
TOP2 = [0] * 8192
HIBIT = [-1] * 8192     # index of the highest set bit, -1 for 0
DRAW = [0] * 8192       # 2 = two or more ranks complete a straight, 1 = one, 0 = none


def _top(m, n):
    t = 0
    while n and m:
        b = 1 << (m.bit_length() - 1)
        t |= b
        m ^= b
        n -= 1
    return t


for _m in range(8192):
    for _hi in range(12, 3, -1):
        if (_m >> (_hi - 4)) & 31 == 31:
            STRAIGHT[_m] = _hi + 1
            break
    else:
        if _m & 0x100F == 0x100F:          # A-2-3-4-5
            STRAIGHT[_m] = 4
    TOP5[_m] = _top(_m, 5)
    TOP3[_m] = _top(_m, 3)
    TOP2[_m] = _top(_m, 2)
    HIBIT[_m] = _m.bit_length() - 1
for _m in range(8192):
    if STRAIGHT[_m] == 0:
        _n = sum(1 for _r in range(13) if not (_m >> _r) & 1 and STRAIGHT[_m | (1 << _r)])
        DRAW[_m] = 2 if _n >= 2 else _n


def eval7(cards):
    """Score 5 to 7 card ids."""
    s0 = s1 = s2 = s3 = 0
    cnt = [0] * 13
    for c in cards:
        r = c >> 2
        b = 1 << r
        cnt[r] += 1
        s = c & 3
        if s == 0:
            s0 |= b
        elif s == 1:
            s1 |= b
        elif s == 2:
            s2 |= b
        else:
            s3 |= b
    for m in (s0, s1, s2, s3):
        if BITS[m] >= 5:
            sh = STRAIGHT[m]
            return (8 << 20) | sh if sh else (5 << 20) | TOP5[m]
    rm = s0 | s1 | s2 | s3
    quad = trip = trip2 = p1 = p2 = -1
    for r in range(12, -1, -1):
        n = cnt[r]
        if n == 4:
            quad = r
        elif n == 3:
            if trip < 0:
                trip = r
            elif trip2 < 0:
                trip2 = r
        elif n == 2:
            if p1 < 0:
                p1 = r
            elif p2 < 0:
                p2 = r
    if quad >= 0:
        return (7 << 20) | (quad << 4) | HIBIT[rm & ~(1 << quad)]
    if trip >= 0 and (trip2 >= 0 or p1 >= 0):
        return (6 << 20) | (trip << 4) | max(trip2, p1)
    sh = STRAIGHT[rm]
    if sh:
        return (4 << 20) | sh
    if trip >= 0:
        return (3 << 20) | (trip << 13) | TOP2[rm & ~(1 << trip)]
    if p2 >= 0:
        return (2 << 20) | (p1 << 8) | (p2 << 4) | HIBIT[rm & ~(1 << p1) & ~(1 << p2)]
    if p1 >= 0:
        return (1 << 20) | (p1 << 13) | TOP3[rm & ~(1 << p1)]
    return TOP5[rm]


def cheap_key(cards5):
    """Ordering key for a keep (2 cards) + flop (3 cards): made-hand category,
    then flush draw, then straight draw, then the exact score."""
    sc = eval7(cards5)
    cat = sc >> 20
    suit_n = [0, 0, 0, 0]
    rm = 0
    for c in cards5:
        suit_n[c & 3] += 1
        rm |= 1 << (c >> 2)
    fd = 1 if max(suit_n) == 4 else 0
    sd = DRAW[rm]
    return (cat << 26) | (fd << 25) | (sd << 23) | (sc & 0xFFFFF)


def cheap_keep(hole3, flop3):
    """The cheap discard rule. Returns (keep_a, keep_b, discard)."""
    a, b, c = hole3
    f = list(flop3)
    best = None
    for keep, out in (((a, b), c), ((a, c), b), ((b, c), a)):
        k = cheap_key([keep[0], keep[1]] + f)
        if best is None or k > best[0]:
            best = (k, keep, out)
    return best[1][0], best[1][1], best[2]


if HAVE_NP:
    BITS_NP = np.array(BITS, dtype=np.int64)
    STRAIGHT_NP = np.array(STRAIGHT, dtype=np.int64)
    TOP5_NP = np.array(TOP5, dtype=np.int64)
    TOP3_NP = np.array(TOP3, dtype=np.int64)
    TOP2_NP = np.array(TOP2, dtype=np.int64)
    HIBIT_NP = np.array(HIBIT, dtype=np.int64)
    DRAW_NP = np.array(DRAW, dtype=np.int64)
    _POW = (1 << np.arange(13, dtype=np.int64))

    def _masks(c):
        n = c.shape[0]
        r = c >> 2
        s = c & 3
        rows = np.arange(n, dtype=np.int64)[:, None]
        cnt = np.bincount((rows * 13 + r).ravel(), minlength=n * 13).reshape(n, 13)
        bit = (np.int64(1) << r).astype(np.float64)
        sm = np.bincount((rows * 4 + s).ravel(), weights=bit.ravel(),
                         minlength=n * 4).reshape(n, 4).astype(np.int64)
        return cnt, sm

    def eval_batch(c, _pre=None):
        """c: int64 array (N, K), K = 5..7. Returns int64 scores (N,), equal to
        eval7 on each row."""
        cnt, sm = _pre if _pre is not None else _masks(c)
        rm = sm[:, 0] | sm[:, 1] | sm[:, 2] | sm[:, 3]
        fm = (sm * (BITS_NP[sm] >= 5)).sum(1)
        m4 = ((cnt == 4) * _POW).sum(1)
        m3 = ((cnt == 3) * _POW).sum(1)
        m2 = ((cnt == 2) * _POW).sum(1)
        one = np.int64(1)
        score = TOP5_NP[rm]
        p1 = np.maximum(HIBIT_NP[m2], 0)
        b1 = one << p1
        score = np.where(m2 > 0, (1 << 20) | (p1 << 13) | TOP3_NP[rm & ~b1], score)
        m2b = m2 & ~b1
        p2 = np.maximum(HIBIT_NP[m2b], 0)
        b2 = one << p2
        score = np.where(m2b > 0, (2 << 20) | (p1 << 8) | (p2 << 4) | HIBIT_NP[rm & ~b1 & ~b2], score)
        t = np.maximum(HIBIT_NP[m3], 0)
        bt = one << t
        score = np.where(m3 > 0, (3 << 20) | (t << 13) | TOP2_NP[rm & ~bt], score)
        sh = STRAIGHT_NP[rm]
        score = np.where(sh > 0, (4 << 20) | sh, score)
        rest = (m3 & ~bt) | m2
        score = np.where((m3 > 0) & (rest > 0), (6 << 20) | (t << 4) | HIBIT_NP[rest], score)
        q = np.maximum(HIBIT_NP[m4], 0)
        score = np.where(m4 > 0, (7 << 20) | (q << 4) | HIBIT_NP[rm & ~(one << q)], score)
        shf = STRAIGHT_NP[fm]
        score = np.where(fm > 0, np.where(shf > 0, (8 << 20) | shf, (5 << 20) | TOP5_NP[fm]), score)
        return score

    def cheap_key_batch(c5):
        """Batch version of cheap_key for (N, 5) arrays."""
        pre = _masks(c5)
        cnt, sm = pre
        sc = eval_batch(c5, pre)
        rm = sm[:, 0] | sm[:, 1] | sm[:, 2] | sm[:, 3]
        fd = (BITS_NP[sm].max(1) == 4).astype(np.int64)
        return ((sc >> 20) << 26) | (fd << 25) | (DRAW_NP[rm] << 23) | (sc & 0xFFFFF)

    _KEEPS = ((0, 1, 2), (0, 2, 1), (1, 2, 0))   # (keep, keep, discard) column indices

    def cheap_keep_batch(hole3, flop3):
        """hole3 (N,3), flop3 (N,3) -> keep (N,2), discard (N,) by the cheap rule.
        Ties resolve to the first keep in the order (0,1), (0,2), (1,2), like cheap_keep."""
        keys = np.stack([cheap_key_batch(np.concatenate([hole3[:, [i, j]], flop3], axis=1))
                         for i, j, _ in _KEEPS], axis=1)
        best = keys.argmax(1)
        ki = np.array([[i, j] for i, j, _ in _KEEPS])[best]
        di = np.array([d for _, _, d in _KEEPS])[best]
        rows = np.arange(hole3.shape[0])
        return hole3[rows[:, None], ki], hole3[rows, di]
