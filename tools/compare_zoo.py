import csv, math, sys

def analyze(csv_path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    out = {}
    opps = []
    for r in rows:
        o = r['opp']
        if o not in opps:
            opps.append(o)
    for o in opps:
        rs = [r for r in rows if r['opp'] == o and r['net'] is not None]
        n = len(rs)
        per = [float(r['net']) / float(r['hands'] or 400) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        ci = 1.96 * sd / math.sqrt(n)
        w = sum(1 for r in rs if float(r['net']) > 0)
        d = sum(1 for r in rs if float(r['net']) == 0)
        l = sum(1 for r in rs if float(r['net']) < 0)
        cap = sum(float(r['cap'] or 0) for r in rs) / sum(float(r['hands'] or 400) for r in rs)
        out[o] = {'n': n, 'wdl': f'{w}-{d}-{l}', 'mean': mean, 'sd': sd, 'ci': ci, 'cap': cap}
    return out

for stage, tag_v11, tag_v1 in [
    (1, 'runs/v11_zoo_s1/results.csv', 'runs/v1_zoo_s1/results.csv'),
    (2, 'runs/v11_zoo_s2/results.csv', 'runs/v1_zoo_s2/results.csv')
]:
    res_v11 = analyze(tag_v11)
    res_v1 = analyze(tag_v1)
    print(f'=== STAGE {stage} (seeds 1-10) ===')
    print(f'{"opponent":<16} | {"v1.1 W-D-L":<10} {"v1.1 chips":<11} {"95% CI":<8} | {"v1 W-D-L":<10} {"v1 chips":<11} {"95% CI":<8} | {"gain vs v1":<11} {"status"}')
    print('-' * 95)
    for o in res_v11:
        d11 = res_v11[o]
        d1 = res_v1[o]
        gain = d11['mean'] - d1['mean']
        # CI of the difference: sqrt(ci11^2 + ci1^2)
        ci_diff = math.sqrt(d11['ci']**2 + d1['ci']**2)
        flag = 'OK'
        # Check both condition interpretations: gain < -2 * d11['ci'] or gain < -2 * ci_diff
        if gain < -2 * d11['ci']:
            flag = 'WORSE > 2x CI'
        elif gain < 0:
            flag = 'lower'
        print(f'{o:<16} | {d11["wdl"]:<10} {d11["mean"]:>+8.2f}    +-{d11["ci"]:<5.2f} | {d1["wdl"]:<10} {d1["mean"]:>+8.2f}    +-{d1["ci"]:<5.2f} | {gain:>+8.2f}    {flag}')
    print()
