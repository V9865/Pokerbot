import csv, math, os, sys

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
        mean = sum(per) / n if n else 0.0
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        ci = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
        w = sum(1 for r in rs if float(r['net']) > 0)
        d = sum(1 for r in rs if float(r['net']) == 0)
        l = sum(1 for r in rs if float(r['net']) < 0)
        
        # Capped chips: each match's net clipped to +-1.00 per hand
        capped_per = [max(-1.0, min(1.0, p)) for p in per]
        capped_mean = sum(capped_per) / n if n else 0.0
        
        out[o] = {'n': n, 'wdl': f'{w}-{d}-{l}', 'mean': mean, 'sd': sd, 'ci': ci, 'capped': capped_mean, 'per': per}
    return out

def print_comparison(new_path, base_path, title="Comparison", base_label="base", new_label="new"):
    res_new = analyze(new_path)
    res_base = analyze(base_path)
    print(f'=== {title} ===')
    print(f'{"opponent":<16} | {new_label + " W-D-L":<10} {new_label + " chips":<11} {"95% CI":<8} {"capped":<8} | {base_label + " W-D-L":<10} {base_label + " chips":<11} {"95% CI":<8} {"capped":<8} | {"gain raw":<10} {"gain cap":<10} {"gain CI"}')
    print('-' * 125)
    for o in res_new:
        dn = res_new[o]
        db = res_base.get(o, {'n': 0, 'wdl': '0-0-0', 'mean': 0.0, 'ci': 0.0, 'capped': 0.0})
        gain_raw = dn['mean'] - db['mean']
        gain_cap = dn['capped'] - db['capped']
        gain_ci = math.sqrt(dn['ci']**2 + db['ci']**2)
        print(f'{o:<16} | {dn["wdl"]:<10} {dn["mean"]:>+8.2f}    +-{dn["ci"]:<5.2f} {dn["capped"]:>+6.2f}  | {db["wdl"]:<10} {db["mean"]:>+8.2f}    +-{db["ci"]:<5.2f} {db["capped"]:>+6.2f}  | {gain_raw:>+8.2f}   {gain_cap:>+8.2f}   +-{gain_ci:.2f}')
    print()

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        print_comparison(sys.argv[1], sys.argv[2], title=sys.argv[3] if len(sys.argv) > 3 else "Comparison")
