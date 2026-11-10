"""Verify eval7 and eval_batch against the starter engine's best_hand."""
import importlib.util, os, random, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from cards import RANKS, SUITS, card_id
from evaluator import eval7, cheap_keep, HAVE_NP
import evaluator as E

spec = importlib.util.spec_from_file_location("engine", os.path.join(ROOT, "starter", "engine.py"))
eng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eng)

deck = [r + s for r in RANKS for s in SUITS]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
random.seed(11)
bad = 0
t_e = t_f = 0.0
for _ in range(N):
    h = random.sample(deck, 14)
    a, b = h[:7], h[7:]
    t = time.perf_counter(); ea, eb = eng.best_hand(a[:2], a[2:]), eng.best_hand(b[:2], b[2:]); t_e += time.perf_counter() - t
    ia, ib = [card_id(c) for c in a], [card_id(c) for c in b]
    t = time.perf_counter(); fa, fb = eval7(ia), eval7(ib); t_f += time.perf_counter() - t
    if (ea > eb) - (ea < eb) != (fa > fb) - (fa < fb):
        bad += 1
print(f"head-to-head pairs: {N}, mismatches: {bad}")
print(f"engine.best_hand {t_e / N / 2 * 1e6:.1f} us/hand, eval7 {t_f / N / 2 * 1e6:.2f} us/hand")

def sc(s): return eval7([card_id(c) for c in s.split()])
cases = [
    ("wheel beats ace high", sc("As 2d 3c 4h 5s Kd 9c") > sc("As Kd Qc 9h 7s 3d 2c")),
    ("six-high straight beats wheel", sc("2d 3c 4h 5s 6d Kc 9h") > sc("As 2d 3c 4h 5s Kd 9c")),
    ("straight flush beats quads", sc("5h 6h 7h 8h 9h 9s 9d") > sc("9h 9s 9d 9c Ah Kh 2d")),
    ("wheel straight flush", sc("Ah 2h 3h 4h 5h Kd Kc") >> 20 == 8),
    ("two trips make a full house", sc("7h 7s 7d 4c 4h 4s Kd") >> 20 == 6),
    ("three pairs use best kicker", sc("Ah As Kd Kc 4h 4s Qd") == sc("Ah As Kd Kc Qd 3s 2d")),
    ("quads with board kicker", sc("9h 9s 9d 9c Ah 3s 2d") > sc("9h 9s 9d 9c Kh 3s 2d")),
    ("flush beats straight", sc("2h 7h 9h Jh Kh 3s 4d") > sc("5s 6d 7c 8h 9s Kd 2c")),
    ("board plays: split", sc("Ts Js Qd Kh Ac 9c 9d") == sc("Ts Js Qd Kh Ac 4c 4h")),
    ("kicker decides pair", sc("Ac Qs Ah Kd 8c 5s 2h") > sc("Ad Js Ah Kd 8c 5s 2h")),
]
for name, ok in cases:
    print(("PASS " if ok else "FAIL ") + name)
    bad += 0 if ok else 1

if HAVE_NP:
    import numpy as np
    rng = np.random.default_rng(5)
    for K in (5, 6, 7):
        M = 200000
        c = np.argsort(rng.random((M, 52)), axis=1)[:, :K].astype(np.int64)
        t = time.perf_counter(); bs = E.eval_batch(c); dt = time.perf_counter() - t
        ss = np.array([eval7(row) for row in c.tolist()])
        mm = int((bs != ss).sum()); bad += mm
        print(f"eval_batch K={K}: {M} hands, mismatches vs eval7: {mm}, {dt / M * 1e6:.3f} us/hand")
    M = 50000
    c = np.argsort(rng.random((M, 52)), axis=1)[:, :6].astype(np.int64)
    kb, db = E.cheap_keep_batch(c[:, :3], c[:, 3:])
    mm = 0
    for row, k, d in zip(c.tolist(), kb.tolist(), db.tolist()):
        a, b, x = cheap_keep(row[:3], row[3:])
        mm += (d != x)
    bad += mm
    print(f"cheap_keep_batch: {M} flops, mismatches vs cheap_keep: {mm}")
print("RESULT:", "OK" if bad == 0 else f"{bad} PROBLEMS")
sys.exit(0 if bad == 0 else 1)
