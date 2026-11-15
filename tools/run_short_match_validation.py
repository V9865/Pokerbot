"""Validation suite for short-match branch against snapshots/v5_bot.py.
200-hand matches (--hands 200), seeds 95000-95039 for held-out opponents,
and seeds 95100-95199 for head-to-head vs v5.

Usage:
  py -3.11 tools/run_short_match_validation.py [--jobs 10] [--force]
"""
import argparse
import csv
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_ROOT = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
VAL_BASE = os.path.join(RUNS_ROOT, "val_short_match")


def run_batch(bot_path, opps_csv, seeds, hands, jobs, tag, force=False):
    out_dir = os.path.join(RUNS_ROOT, tag)
    csv_path = os.path.join(out_dir, "results.csv")
    if os.path.isfile(csv_path) and not force:
        print(f"[SKIP] {tag} already has results.csv", flush=True)
        return csv_path

    t0 = time.time()
    print(f"[RUN ] {tag}: bot={os.path.basename(bot_path)} opps={opps_csv} seeds={seeds} hands={hands} jobs={jobs}", flush=True)
    cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_matches.py"),
        "--bot", bot_path,
        "--opps", opps_csv,
        "--seeds", seeds,
        "--hands", str(hands),
        "--jobs", str(jobs),
        "--tag", tag,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.time() - t0
    print(f"[DONE] {tag} in {dt:.1f}s (exit={res.returncode})", flush=True)
    if res.stdout.strip():
        for line in res.stdout.strip().splitlines():
            print("  " + line, flush=True)
    if not os.path.isfile(csv_path):
        print(f"[ERR ] Missing {csv_path}!\n{res.stderr}", flush=True)
    return csv_path


def load_csv_stats(csv_path):
    """Return dict opp -> metrics dict."""
    if not os.path.isfile(csv_path):
        return {}
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    out = {}
    for opp in dict.fromkeys(r["opp"] for r in rows):
        rs = [r for r in rows if r["opp"] == opp and r["net"] not in (None, "")]
        all_opp = [r for r in rows if r["opp"] == opp]
        n = len(rs)
        probs_notices = sum(int(r["notices_a"] or 0) for r in all_opp)
        probs_forfeit = sum(1 for r in all_opp if (r.get("forfeit") or "").strip())
        probs_tb = sum(int(r["traceback"] or 0) for r in all_opp)
        if n == 0:
            out[opp] = {"n": 0, "w": 0, "d": 0, "l": 0, "mean": 0.0, "ci": 0.0, "cap": 0.0,
                        "notices": probs_notices, "forfeits": probs_forfeit, "tracebacks": probs_tb}
            continue
        per = [float(r["net"]) / float(r["hands"] or 200) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        ci = 1.96 * sd / math.sqrt(n)
        w_cnt = sum(1 for r in rs if float(r["net"]) > 0)
        d_cnt = sum(1 for r in rs if float(r["net"]) == 0)
        l_cnt = sum(1 for r in rs if float(r["net"]) < 0)
        cap = sum(float(r["cap"] or 0) for r in rs) / float(sum(int(r["hands"] or 200) for r in rs))
        out[opp] = {
            "n": n, "w": w_cnt, "d": d_cnt, "l": l_cnt,
            "mean": mean, "ci": ci, "cap": cap,
            "notices": probs_notices, "forfeits": probs_forfeit, "tracebacks": probs_tb,
            "per_list": per, "rows": rs,
        }
    return out


def fmt_cell(st):
    if not st or st["n"] == 0:
        return "NO DATA"
    wdl = f"{st['w']}-{st['d']}-{st['l']}"
    return f"{wdl:<8} {st['mean']:+6.2f}+-{st['ci']:4.2f} ({st['cap']:+5.2f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.makedirs(VAL_BASE, exist_ok=True)
    bots = {
        "v5": os.path.join(ROOT, "snapshots", "v5_bot.py"),
        "short_match": os.path.join(RUNS_ROOT, "variants", "short_match_bot.py"),
    }
    for k, p in bots.items():
        if not os.path.isfile(p):
            sys.exit(f"Missing bot {k}: {p}")

    fixed_opps = ["friend", "gto_like", "liar", "lag", "rof_big", "nit", "ai_typical", "exploiter2"]
    if os.path.isfile(os.path.join(ROOT, "opponents", "friend_b.py")):
        fixed_opps.insert(1, "friend_b")

    fixed_csv = ",".join(fixed_opps)

    t_start = time.time()

    # 1. Held-out fixed opponents (seeds 95000-95039, 200 hands)
    for name, bpath in bots.items():
        run_batch(bpath, fixed_csv, "95000-95039", 200, args.jobs, f"val_short_match/fixed_{name}", args.force)

    # 2. 40 Personas (seeds 95000-95039, 200 hands)
    for name, bpath in bots.items():
        run_batch(bpath, "persona", "95000-95039", 200, args.jobs, f"val_short_match/persona_{name}", args.force)

    # 3. Head-to-head short-match vs v5 (seeds 95100-95199, 200 hands)
    run_batch(bots["short_match"], "snapshots/v5_bot.py", "95100-95199", 200, args.jobs, "val_short_match/h2h_sm_vs_v5", args.force)

    total_dt = time.time() - t_start
    print(f"\nAll validation batches completed in {total_dt/60.0:.1f} min.", flush=True)

    # Report generation
    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("=" * 110)
    out("SHORT-MATCH (SM_LEARN) VALIDATION REPORT (200 hands/match; Fresh seeds 95000-95039 & 95100-95199)")
    out("=" * 110)

    all_held_opps = fixed_opps + ["persona"]
    summary_metrics = {b: {"cap_list": [], "wins": 0, "losses": 0, "total_matches": 0, "matchups": {}} for b in bots}

    out(f"\n--- HELD-OUT OPPONENTS (200 hands/match, 40 matches each, seeds 95000-95039) ---")
    out(f"{'Opponent':<13} | {'v5 Baseline (W-D-L chips+-CI cap)':<35} | {'short-match (W-D-L chips+-CI cap)':<35} | {'Win Diff (SM - v5)'}")
    out("-" * 110)

    drops_gt_3 = []
    for opp in all_held_opps:
        cells = []
        d_map = {}
        for bname in ("v5", "short_match"):
            tag = f"val_short_match/{'persona' if opp == 'persona' else 'fixed'}_{bname}"
            st_map = load_csv_stats(os.path.join(RUNS_ROOT, tag, "results.csv"))
            d = st_map.get(opp)
            d_map[bname] = d
            cells.append(fmt_cell(d))
            if d and d["n"] > 0:
                summary_metrics[bname]["cap_list"].append(d["cap"])
                summary_metrics[bname]["wins"] += d["w"]
                summary_metrics[bname]["losses"] += d["l"]
                summary_metrics[bname]["total_matches"] += d["n"]
                summary_metrics[bname]["matchups"][opp] = d

        w_v5 = d_map["v5"]["w"] if d_map.get("v5") else 0
        w_sm = d_map["short_match"]["w"] if d_map.get("short_match") else 0
        diff_w = w_sm - w_v5
        if diff_w < -3:
            drops_gt_3.append((opp, w_v5, w_sm, diff_w))
        out(f"{opp:<13} | {cells[0]:<35} | {cells[1]:<35} | {diff_w:+d} wins")

    # Overall summary
    out("\n--- OVERALL HELD-OUT TOTALS ---")
    w_tot_v5 = summary_metrics["v5"]["wins"]
    n_tot_v5 = summary_metrics["v5"]["total_matches"]
    w_tot_sm = summary_metrics["short_match"]["wins"]
    n_tot_sm = summary_metrics["short_match"]["total_matches"]

    avg_cap_v5 = sum(summary_metrics["v5"]["cap_list"]) / len(summary_metrics["v5"]["cap_list"]) if summary_metrics["v5"]["cap_list"] else 0.0
    avg_cap_sm = sum(summary_metrics["short_match"]["cap_list"]) / len(summary_metrics["short_match"]["cap_list"]) if summary_metrics["short_match"]["cap_list"] else 0.0

    out(f"  v5 Baseline : {w_tot_v5}/{n_tot_v5} wins ({w_tot_v5/n_tot_v5*100:.2f}%) | Avg Capped: {avg_cap_v5:+.4f} chips/hand")
    out(f"  short-match : {w_tot_sm}/{n_tot_sm} wins ({w_tot_sm/n_tot_sm*100:.2f}%) | Avg Capped: {avg_cap_sm:+.4f} chips/hand")
    out(f"  Total Win Delta (SM - v5): {w_tot_sm - w_tot_v5:+d} wins")

    # Head-to-Head
    out("\n--- HEAD-TO-HEAD vs snapshots/v5_bot.py (200 hands, seeds 95100-95199, n=100) ---")
    st_map = load_csv_stats(os.path.join(RUNS_ROOT, "val_short_match/h2h_sm_vs_v5", "results.csv"))
    h2h_res = st_map.get("v5_bot") or (list(st_map.values())[0] if st_map else None)
    if h2h_res:
        out(f"  short-match vs v5_bot: W-D-L = {h2h_res['w']}-{h2h_res['d']}-{h2h_res['l']}, chips/hand = {h2h_res['mean']:+.3f} +- {h2h_res['ci']:.3f}, capped = {h2h_res['cap']:+.3f}, notices={h2h_res['notices']}, forfeits={h2h_res['forfeits']}, tb={h2h_res['tracebacks']}")
    else:
        out("  short-match vs v5_bot: NO DATA")

    # Acceptance Criteria Check
    out("\n--- ACCEPTANCE CRITERIA CHECK ---")
    rule1_pass = w_tot_sm >= w_tot_v5
    out(f"  1. Total held-out matches won >= v5?   {w_tot_sm} vs {w_tot_v5} ({w_tot_sm - w_tot_v5:+d}) -> {'PASS' if rule1_pass else 'FAIL'}")

    rule2_pass = len(drops_gt_3) == 0
    drop_desc = ", ".join([f"{opp}: {w_v5}->{w_sm} ({dw:+d})" for opp, w_v5, w_sm, dw in drops_gt_3]) if drops_gt_3 else "None"
    out(f"  2. No opponent drops by > 3 wins?      {drop_desc} -> {'PASS' if rule2_pass else 'FAIL'}")

    h2h_not_neg = (h2h_res and (h2h_res['mean'] + h2h_res['ci'] >= 0.0)) if h2h_res else False
    out(f"  3. H2H not negative beyond CI?         {'PASS' if h2h_not_neg else 'FAIL'}")

    accepted = rule1_pass and rule2_pass and h2h_not_neg
    out(f"\nFINAL VERDICT: {'ACCEPTED' if accepted else 'REJECTED'}")

    report_path = os.path.join(VAL_BASE, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    out(f"\nSaved report to {report_path}")


if __name__ == "__main__":
    main()
