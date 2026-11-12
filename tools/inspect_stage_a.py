"""Inspect Stage A training logs, safety stats, per-opponent performance, and parameter trajectory."""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from policy_params import STAGE_A_NAMES, PARAMS, BOUNDS

STAGE_DIR = r"C:\pokerbot_runs\train\stage_a"


def parse_match_log(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    tail = "".join(lines[-10:])
    m_h = re.search(r"\|\s*(\d+) of (\d+) hands played", tail)
    hands = int(m_h.group(2)) if m_h else None
    m_a = re.search(r"^\s*A\s+\S+\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+) s.*notices\s+(\d+)", tail, re.M)
    net = int(m_a.group(1)) if m_a else None
    time_a = float(m_a.group(2)) if m_a else 0.0
    notices_a = int(m_a.group(3)) if m_a else 0
    m_cap = re.search(r"Capped delta: A ([+-]?\d+)", tail)
    cap = int(m_cap.group(1)) if m_cap else None
    forfeit = ("forfeit" in tail.lower()) or ("disqualified" in tail.lower())
    return {
        "hands": hands,
        "net": net,
        "time_a": time_a,
        "notices_a": notices_a,
        "cap": cap,
        "forfeit": forfeit,
    }


def iter_match_dirs(cand_dir):
    """Yield (opp_name, seed, mdir) handling nested subdirs like snapshots/v1_1_bot.py_1000."""
    for root, dirs, files in os.walk(cand_dir):
        if "match.log" in files:
            base = os.path.basename(root)
            if "_" in base:
                opp, seed = base.rsplit("_", 1)
                yield opp, seed, root
            dirs[:] = []  # leaf match directory


def analyze_candidate(cand_dir):
    by_opp = {}
    for opp, seed, mdir in sorted(iter_match_dirs(cand_dir)):
        mlog = os.path.join(mdir, "match.log")
        info = parse_match_log(mlog)
        opp_key = opp[:-3] if opp.endswith(".py") else opp
        by_opp.setdefault(opp_key, []).append((seed, mdir, info))
    return by_opp


def find_cand_idx(gen_num, target_F):
    import math
    cfg = json.load(open(os.path.join(ROOT, "tools", "train_config.json")))
    raw_opps = cfg["training_opponents"]
    tot_w = sum(raw_opps.values())
    w_map = {os.path.splitext(os.path.basename(k))[0]: v / tot_w for k, v in raw_opps.items()}

    best_idx, best_diff, best_opp = None, 1e9, None
    for idx in range(12):
        cdir = os.path.join(STAGE_DIR, f"gen_{gen_num:03d}_cand_{idx:02d}")
        by_opp = analyze_candidate(cdir)
        f_val = 0.0
        for opp, items in by_opp.items():
            scores = []
            for _, _, r in items:
                n = r["net"] / float(r["hands"] or 400)
                scores.append(0.6 * math.tanh(n / 0.25) + 0.4 * max(-1.0, min(1.0, n)))
            f_val += w_map.get(opp, 0.0) * (sum(scores) / len(scores))
        diff = abs(f_val - target_F)
        if diff < best_diff:
            best_diff, best_idx, best_opp = diff, idx, by_opp
    return best_idx, best_opp


def main():
    files = sorted(glob.glob(os.path.join(STAGE_DIR, "gen_*.json")))
    gens_data = [json.load(open(f)) for f in files]
    best_overall = max(gens_data, key=lambda d: d["best_F"])
    gen_last = gens_data[-1]

    print(f"Checkpoints found: {len(gens_data)} (Gen {gens_data[0]['gen']:03d} to Gen {gen_last['gen']:03d})")
    total_time = sum(d["elapsed_s"] for d in gens_data)
    print(f"Total elapsed wall time: {total_time:.1f}s ({total_time / 3600:.2f} h)")

    # Scan all match logs & stderr files across all 6,600 matches
    total_matches = 0
    forfeits = 0
    notices_total = 0
    tracebacks = 0
    max_time = 0.0
    max_time_where = ""
    slow_matches = []

    for g in range(1, len(gens_data) + 1):
        for idx in range(12):
            cdir = os.path.join(STAGE_DIR, f"gen_{g:03d}_cand_{idx:02d}")
            for opp, seed, mdir in iter_match_dirs(cdir):
                total_matches += 1
                mlog = os.path.join(mdir, "match.log")
                info = parse_match_log(mlog)
                if info["forfeit"] or info["net"] is None:
                    forfeits += 1
                notices_total += info["notices_a"]
                if info["time_a"] > max_time:
                    max_time = info["time_a"]
                    max_time_where = mdir
                if info["time_a"] > 20.0:
                    slow_matches.append((info["time_a"], mdir))
                for errf in ("A_leg1_stderr.txt", "A_leg2_stderr.txt"):
                    ep = os.path.join(mdir, errf)
                    if os.path.isfile(ep) and os.path.getsize(ep) > 0:
                        txt = open(ep, "r", encoding="utf-8", errors="replace").read()
                        if "Traceback" in txt:
                            tracebacks += 1

    print(f"\nGlobal Safety Audit across all {total_matches} matches:")
    print(f"  Forfeits/unparsed:  {forfeits}")
    print(f"  Bot A notices:      {notices_total}")
    print(f"  Bot A tracebacks:   {tracebacks}")
    print(f"  Max Bot A time:     {max_time:.2f}s at {max_time_where}")
    print(f"  Matches > 20.0s:    {len(slow_matches)}")
    for t, w in sorted(slow_matches, reverse=True)[:5]:
        print(f"    {t:.2f}s  {w}")

    print("\nGeneration F Trajectory (100-hand phase: Gen 1-8; 400-hand phase: Gen 9-25):")
    for d in gens_data:
        phase = "100h" if d["gen"] <= 8 else "400h"
        print(f"  Gen {d['gen']:03d} ({phase}): Best F={d['best_F']:+.4f} | Mean F={d['mean_F']:+.4f} | Sigma={d['sigma']:.4f} | Time={d['elapsed_s']:6.1f}s")

    # Per-opponent breakdown for Gen 025 best vs Gen 009 best vs Gen 016 best
    for label, gd in [("Gen 009 (first 400h gen)", gens_data[8]), ("Gen 016 (peak F)", best_overall), ("Gen 025 (final best.json)", gen_last)]:
        cidx, by_opp = find_cand_idx(gd["gen"], gd["best_F"])
        print(f"\nPer-Opponent Breakdown for {label} (cand_{cidx:02d}, F={gd['best_F']:+.4f}):")
        print(f"  {'opponent':<16} {'W-D-L':<7} {'chips/h':>8} {'capped':>8} {'max_t':>6}")
        for opp, items in sorted(by_opp.items()):
            rows = [r for _, _, r in items]
            w = sum(1 for r in rows if (r["net"] or 0) > 0)
            d_cnt = sum(1 for r in rows if r["net"] == 0)
            l = sum(1 for r in rows if (r["net"] or 0) < 0)
            h_tot = sum(r["hands"] or 400 for r in rows)
            cph = sum(r["net"] or 0 for r in rows) / float(h_tot)
            cap = sum(r["cap"] or 0 for r in rows) / float(h_tot)
            mt = max(r["time_a"] for r in rows)
            print(f"  {opp:<16} {w}-{d_cnt}-{l:<3} {cph:+8.2f} {cap:+8.2f} {mt:5.2f}s")

    print("\nStage A Parameter Evolution (Init -> Gen025 best.json vs Gen016 peak [Bounds]):")
    for k in STAGE_A_NAMES:
        lo, hi = BOUNDS[k]
        g25_v = gen_last["best_params"][k]
        g16_v = best_overall["best_params"][k]
        delta = g25_v - PARAMS[k]
        print(f"  {k:<18}: {PARAMS[k]:7.4f} -> g25={g25_v:7.4f} ({delta:+7.4f}) | g16={g16_v:7.4f}  [{lo}, {hi}]")


if __name__ == "__main__":
    main()
