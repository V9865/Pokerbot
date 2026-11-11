import csv
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_res(rel_path):
    rows = []
    path = os.path.join(ROOT, rel_path)
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def summarize(rows):
    by_opp = {}
    for r in rows:
        o = r['opp']
        if o not in by_opp:
            by_opp[o] = []
        by_opp[o].append(r)
    res = {}
    for o, rs in by_opp.items():
        n = len(rs)
        w = sum(1 for r in rs if int(r['net']) > 0)
        d = sum(1 for r in rs if int(r['net']) == 0)
        l = sum(1 for r in rs if int(r['net']) < 0)
        per = [int(r['net']) / float(r['hands']) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean)**2 for x in per) / (n - 1)) if n > 1 else 0.0
        ci = 1.96 * sd / math.sqrt(n)
        cap = sum(int(r['cap']) for r in rs) / float(sum(int(r['hands']) for r in rs))
        res[o] = {'n': n, 'wdl': f'{w}-{d}-{l}', 'mean': mean, 'ci': ci, 'cap': cap, 'per': per}
    return res

def main():
    v11_s1 = summarize(load_res('runs/v11_zoo_s1/results.csv'))
    v2_s1  = summarize(load_res('runs/v2_zoo_s1/results.csv'))
    v11_s2 = summarize(load_res('runs/v11_zoo_s2/results.csv'))
    v2_s2  = summarize(load_res('runs/v2_zoo_s2/results.csv'))

    print('=== STAGE 1 (seeds 1-10) ===')
    print(f"{'opponent':16} {'W-D-L(v2)':10} {'chips(v2)':10} {'95% CI':8} {'cap(v2)':8} | {'W-D-L(v1.1)':12} {'chips(v1.1)':12} {'95% CI':8} {'cap(v1.1)':9} | {'gain':7} {'gain CI':8}")
    for o in v2_s1:
        r2 = v2_s1[o]
        r1 = v11_s1[o]
        gain = r2['mean'] - r1['mean']
        gain_ci = math.sqrt(r2['ci']**2 + r1['ci']**2)
        print(f"{o:16} {r2['wdl']:10} {r2['mean']:+10.2f} +- {r2['ci']:4.2f} {r2['cap']:+8.2f} | {r1['wdl']:12} {r1['mean']:+12.2f} +- {r1['ci']:4.2f} {r1['cap']:+9.2f} | {gain:+7.2f} +- {gain_ci:4.2f}")

    print('\n=== STAGE 2 (seeds 1-10) ===')
    print(f"{'opponent':16} {'W-D-L(v2)':10} {'chips(v2)':10} {'95% CI':8} {'cap(v2)':8} | {'W-D-L(v1.1)':12} {'chips(v1.1)':12} {'95% CI':8} {'cap(v1.1)':9} | {'gain':7} {'gain CI':8}")
    for o in v2_s2:
        r2 = v2_s2[o]
        r1 = v11_s2[o]
        gain = r2['mean'] - r1['mean']
        gain_ci = math.sqrt(r2['ci']**2 + r1['ci']**2)
        print(f"{o:16} {r2['wdl']:10} {r2['mean']:+10.2f} +- {r2['ci']:4.2f} {r2['cap']:+8.2f} | {r1['wdl']:12} {r1['mean']:+12.2f} +- {r1['ci']:4.2f} {r1['cap']:+9.2f} | {gain:+7.2f} +- {gain_ci:4.2f}")

    # Friend held out (seeds 1-20)
    fr_v11_s1 = summarize(load_res('runs/friend_s1_20/results.csv'))['friend']
    fr_v2_s1  = summarize(load_res('runs/v2_friend_s1_20/results.csv'))['friend']
    fr_v11_s2 = summarize(load_res('runs/friend_s2_20_final/results.csv'))['friend']
    fr_v2_s2  = summarize(load_res('runs/v2_friend_s2_20/results.csv'))['friend']

    print('\n=== FRIEND HELD-OUT CHECK (seeds 1-20) ===')
    g1 = fr_v2_s1['mean'] - fr_v11_s1['mean']
    g1_ci = math.sqrt(fr_v2_s1['ci']**2 + fr_v11_s1['ci']**2)
    print(f"Stage 1: v2 {fr_v2_s1['wdl']} {fr_v2_s1['mean']:+.2f} +- {fr_v2_s1['ci']:.2f} (cap {fr_v2_s1['cap']:+.2f}) vs v1.1 {fr_v11_s1['wdl']} {fr_v11_s1['mean']:+.2f} +- {fr_v11_s1['ci']:.2f} (cap {fr_v11_s1['cap']:+.2f}) | Gain: {g1:+.2f} +- {g1_ci:.2f}")

    g2 = fr_v2_s2['mean'] - fr_v11_s2['mean']
    g2_ci = math.sqrt(fr_v2_s2['ci']**2 + fr_v11_s2['ci']**2)
    print(f"Stage 2: v2 {fr_v2_s2['wdl']} {fr_v2_s2['mean']:+.2f} +- {fr_v2_s2['ci']:.2f} (cap {fr_v2_s2['cap']:+.2f}) vs v1.1 {fr_v11_s2['wdl']} {fr_v11_s2['mean']:+.2f} +- {fr_v11_s2['ci']:.2f} (cap {fr_v11_s2['cap']:+.2f}) | Gain: {g2:+.2f} +- {g2_ci:.2f}")

    # Head to head (seeds 1-40)
    h2h = summarize(load_res('runs/h2h_bayes_vs_v11/results.csv'))['v1_1_bot']
    print('\n=== HEAD-TO-HEAD VS V1_1 (seeds 1-40, Stage 2) ===')
    print(f"W-D-L: {h2h['wdl']}, chips/hand: {h2h['mean']:+.2f} +- {h2h['ci']:.2f}, capped: {h2h['cap']:+.2f}")

if __name__ == '__main__':
    main()

