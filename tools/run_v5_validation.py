"""Full Stage A v5 validation suite comparing v5_A_untrained, T5_best, and T5_mean
against snapshots/v4_bot.py on completely fresh seeds (92000-92039), including
Stage 1 & Stage 2 held-out sets, 40-seed head-to-head vs v4, safety bots,
and serial zero-contention timing checks.

Usage:
  py -3.11 tools/run_v5_validation.py [--jobs 10] [--force]
"""
import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from policy_params import STAGE_A_NAMES, PARAMS, BOUNDS

RUNS_ROOT = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
VAL_BASE = os.path.join(RUNS_ROOT, "val_stage_a_v5")


def run_batch(bot_path, opps_csv, seeds, stage, jobs, tag, force=False):
    out_dir = os.path.join(RUNS_ROOT, tag)
    csv_path = os.path.join(out_dir, "results.csv")
    if os.path.isfile(csv_path) and not force:
        print(f"[SKIP] {tag} already has results.csv", flush=True)
        return csv_path

    t0 = time.time()
    print(f"[RUN ] {tag}: bot={os.path.basename(bot_path)} opps={opps_csv} seeds={seeds} stage={stage} jobs={jobs}", flush=True)
    cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_matches.py"),
        "--bot", bot_path,
        "--opps", opps_csv,
        "--seeds", seeds,
        "--stage", str(stage),
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
        per = [float(r["net"]) / float(r["hands"] or 400) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        ci = 1.96 * sd / math.sqrt(n)
        w_cnt = sum(1 for r in rs if float(r["net"]) > 0)
        d_cnt = sum(1 for r in rs if float(r["net"]) == 0)
        l_cnt = sum(1 for r in rs if float(r["net"]) < 0)
        cap = sum(float(r["cap"] or 0) for r in rs) / float(sum(int(r["hands"] or 400) for r in rs))
        out[opp] = {
            "n": n, "w": w_cnt, "d": d_cnt, "l": l_cnt,
            "mean": mean, "ci": ci, "cap": cap,
            "notices": probs_notices, "forfeits": probs_forfeit, "tracebacks": probs_tb,
            "per_list": per, "rows": rs,
        }
    return out


def scan_timing(tag, stage):
    """Scan all A_leg1_stderr.txt and A_leg2_stderr.txt in C:/pokerbot_runs/<tag>."""
    base = os.path.join(RUNS_ROOT, tag)
    bank = 30.0 if stage == 1 else 75.0
    thinks = []
    replies = []
    errors = 0
    notices = 0
    missing = 0
    for root, _, files in os.walk(base):
        for leg in (1, 2):
            fn = f"A_leg{leg}_stderr.txt"
            if fn in files:
                p = os.path.join(root, fn)
                try:
                    txt = open(p, encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                m = re.search(r"SUMMARY \S+ hands=(\d+) think_s=([\d.]+) max_reply_ms=([\d.]+) modes=(\[[^\]]*\]) errors=(\d+) notices=(\d+)", txt)
                if m:
                    thinks.append(float(m.group(2)) / bank * 100.0)
                    replies.append(float(m.group(3)))
                    errors += int(m.group(5))
                    notices += int(m.group(6))
                else:
                    missing += 1
    if not thinks:
        return None
    return {
        "legs": len(thinks),
        "mean_pct": sum(thinks) / len(thinks),
        "max_pct": max(thinks),
        "worst_reply_ms": max(replies),
        "errors": errors,
        "notices": notices,
        "missing": missing,
    }


def fmt_cell(st):
    if not st or st["n"] == 0:
        return "NO DATA"
    wdl = f"{st['w']}-{st['d']}-{st['l']}"
    return f"{wdl:<7} {st['mean']:+6.2f}+-{st['ci']:4.2f} ({st['cap']:+5.2f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.makedirs(VAL_BASE, exist_ok=True)
    bots = {
        "v4": os.path.join(ROOT, "snapshots", "v4_bot.py"),
        "v5_A_untrained": os.path.join(RUNS_ROOT, "variants", "v5_A_untrained.py"),
        "T5_best": os.path.join(RUNS_ROOT, "variants", "T5_best.py"),
        "T5_mean": os.path.join(RUNS_ROOT, "variants", "T5_mean.py"),
    }
    for k, p in bots.items():
        if not os.path.isfile(p):
            sys.exit(f"Missing bot {k}: {p}")

    fixed_opps = ["friend", "liar", "ai_typical", "exploiter2"]
    if os.path.isfile(os.path.join(ROOT, "opponents", "friend2.py")):
        fixed_opps.insert(1, "friend2")
    if os.path.isfile(os.path.join(ROOT, "opponents", "friend_b.py")):
        fixed_opps.insert(1, "friend_b")

    fixed_csv = ",".join(fixed_opps)
    safety_csv = "station,random_bot,shover,maniac,minraiser"

    t_start = time.time()

    # 1. Held-out fixed opponents (Stage 1 & Stage 2, seeds 92000-92019)
    for st in (1, 2):
        for name, bpath in bots.items():
            run_batch(bpath, fixed_csv, "92000-92019", st, args.jobs, f"val_stage_a_v5/s{st}_fixed_{name}", args.force)

    # 2. 30 Held-out personas (Stage 1 & Stage 2, seeds 92000-92029)
    for st in (1, 2):
        for name, bpath in bots.items():
            run_batch(bpath, "persona", "92000-92029", st, args.jobs, f"val_stage_a_v5/s{st}_persona_{name}", args.force)

    # 3. Head-to-head vs v4 (Stage 2, seeds 92000-92039)
    for name in ("v5_A_untrained", "T5_best", "T5_mean"):
        run_batch(bots[name], "snapshots/v4_bot.py", "92000-92039", 2, args.jobs, f"val_stage_a_v5/h2h_{name}", args.force)

    # 4. Safety bots (Stage 2, seeds 92000-92004 = 5 fresh seeds)
    for name, bpath in bots.items():
        run_batch(bpath, safety_csv, "92000-92004", 2, args.jobs, f"val_stage_a_v5/s2_safety_{name}", args.force)

    # 5. Serial zero-contention timing checks (Stage 1 & Stage 2, --jobs 1)
    for st in (1, 2):
        for name in bots.keys():
            run_batch(bots[name], "friend,gto_like,maniac", "92000-92001", st, 1, f"val_stage_a_v5/s{st}_timing_{name}", args.force)

    total_dt = time.time() - t_start
    print(f"\nAll validation batches completed in {total_dt/60.0:.1f} min.", flush=True)

    # ------------------------------------------------------------ Report generation
    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("=" * 125)
    out("STAGE A v5 VALIDATION REPORT (Fresh seeds 92000-92039; exact paired seeds across v4, v5_A_untrained, T5_best, T5_mean)")
    out("=" * 125)

    # Collect stats per stage & opponent
    all_held_opps = ["persona"] + fixed_opps
    summary_metrics = {b: {"cap_list": [], "wins": 0, "losses": 0, "total_matches": 0, "matchups": {}} for b in bots}

    for st in (1, 2):
        hands_n = 400 if st == 1 else 1000
        out(f"\n--- HELD-OUT SET: STAGE {st} ({hands_n} hands/match; personas 92000-92029, fixed 92000-92019) ---")
        out(f"{'opponent':<13} | {'v4 (W-D-L chips+-CI cap)':<27} | {'v5_A_untrained':<27} | {'T5_best':<27} | {'T5_mean':<27}")
        out("-" * 125)
        for opp in all_held_opps:
            cells = []
            for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
                tag = f"val_stage_a_v5/s{st}_{'persona' if opp == 'persona' else 'fixed'}_{bname}"
                st_map = load_csv_stats(os.path.join(RUNS_ROOT, tag, "results.csv"))
                d = st_map.get(opp)
                cells.append(fmt_cell(d))
                if d and d["n"] > 0:
                    summary_metrics[bname]["cap_list"].append(d["cap"])
                    summary_metrics[bname]["wins"] += d["w"]
                    summary_metrics[bname]["losses"] += d["l"]
                    summary_metrics[bname]["total_matches"] += d["n"]
                    summary_metrics[bname]["matchups"][f"S{st}_{opp}"] = d
            out(f"{opp:<13} | {cells[0]:<27} | {cells[1]:<27} | {cells[2]:<27} | {cells[3]:<27}")

    # Field average capped chips across held-out sets
    out("\n--- FIELD AVERAGE CAPPED CHIPS (Held-out: Stage 1 + Stage 2) ---")
    for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
        caps = summary_metrics[bname]["cap_list"]
        avg_c = sum(caps) / len(caps) if caps else 0.0
        w_tot = summary_metrics[bname]["wins"]
        l_tot = summary_metrics[bname]["losses"]
        n_tot = summary_metrics[bname]["total_matches"]
        w_pct = (w_tot / n_tot * 100.0) if n_tot else 0.0
        out(f"  {bname:<15}: avg_capped = {avg_c:+.4f} chips/hand | total W-L = {w_tot}-{l_tot} ({w_pct:.2f}% wins over {n_tot} matches)")

    # H2H vs v4
    out("\n--- HEAD-TO-HEAD vs snapshots/v4_bot.py (Stage 2, seeds 92000-92039, n=40) ---")
    h2h_results = {}
    for bname in ("v5_A_untrained", "T5_best", "T5_mean"):
        st_map = load_csv_stats(os.path.join(RUNS_ROOT, f"val_stage_a_v5/h2h_{bname}", "results.csv"))
        d = st_map.get("v4_bot")
        h2h_results[bname] = d
        if d:
            out(f"  {bname:<15} vs v4: W-D-L = {d['w']}-{d['d']}-{d['l']}, chips/hand = {d['mean']:+.3f} +- {d['ci']:.3f}, capped = {d['cap']:+.3f}, notices={d['notices']}, forfeits={d['forfeits']}, tb={d['tracebacks']}")
        else:
            out(f"  {bname:<15} vs v4: NO DATA")

    # Safety
    out("\n--- SAFETY BOTS (Stage 2, seeds 92000-92004, n=5) ---")
    out(f"{'opponent':<13} | {'v4':<27} | {'v5_A_untrained':<27} | {'T5_best':<27} | {'T5_mean':<27}")
    out("-" * 125)
    safety_totals = {b: {"notices": 0, "forfeits": 0, "tracebacks": 0} for b in bots}
    for opp in safety_csv.split(","):
        cells = []
        for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
            st_map = load_csv_stats(os.path.join(RUNS_ROOT, f"val_stage_a_v5/s2_safety_{bname}", "results.csv"))
            d = st_map.get(opp)
            cells.append(fmt_cell(d))
            if d:
                safety_totals[bname]["notices"] += d["notices"]
                safety_totals[bname]["forfeits"] += d["forfeits"]
                safety_totals[bname]["tracebacks"] += d["tracebacks"]
        out(f"{opp:<13} | {cells[0]:<27} | {cells[1]:<27} | {cells[2]:<27} | {cells[3]:<27}")

    # Global error/notice/traceback count across ALL validation batches
    out("\n--- GLOBAL PROBLEM COUNT (all held-out + H2H + safety matches) ---")
    for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
        tot_n = safety_totals[bname]["notices"]
        tot_f = safety_totals[bname]["forfeits"]
        tot_tb = safety_totals[bname]["tracebacks"]
        for mkey, d in summary_metrics[bname]["matchups"].items():
            tot_n += d["notices"]
            tot_f += d["forfeits"]
            tot_tb += d["tracebacks"]
        if bname in h2h_results and h2h_results[bname]:
            hd = h2h_results[bname]
            tot_n += hd["notices"]
            tot_f += hd["forfeits"]
            tot_tb += hd["tracebacks"]
        out(f"  {bname:<15}: notices={tot_n}, forfeits={tot_f}, tracebacks={tot_tb}")

    # Timing
    out("\n--- TIMING (Serial --jobs 1: friend,gto_like,maniac, seeds 92000-92001 = 12 legs per stage) ---")
    timing_data = {b: {} for b in bots}
    for st in (1, 2):
        bank = 30.0 if st == 1 else 75.0
        out(f"  Stage {st} (bank {bank:.0f}s/leg):")
        for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
            tm = scan_timing(f"val_stage_a_v5/s{st}_timing_{bname}", st)
            timing_data[bname][f"S{st}"] = tm
            if tm:
                out(f"    {bname:<15}: legs={tm['legs']}, mean={tm['mean_pct']:.2f}% bank, max={tm['max_pct']:.2f}% bank, worst_reply={tm['worst_reply_ms']:.1f} ms, errors={tm['errors']}, notices={tm['notices']}")

    # Parallel worst reply audit across ALL validation batches
    out("\n--- PARALLEL MAX REPLY AUDIT (worst single reply ms across ALL validation legs) ---")
    for bname in ("v4", "v5_A_untrained", "T5_best", "T5_mean"):
        worst_ms = 0.0
        max_pct_s1 = 0.0
        max_pct_s2 = 0.0
        tags = [
            (f"val_stage_a_v5/s1_fixed_{bname}", 1), (f"val_stage_a_v5/s1_persona_{bname}", 1),
            (f"val_stage_a_v5/s2_fixed_{bname}", 2), (f"val_stage_a_v5/s2_persona_{bname}", 2),
            (f"val_stage_a_v5/s2_safety_{bname}", 2),
        ]
        if bname != "v4":
            tags.append((f"val_stage_a_v5/h2h_{bname}", 2))
        for tag, st in tags:
            tm = scan_timing(tag, st)
            if tm:
                worst_ms = max(worst_ms, tm["worst_reply_ms"])
                if st == 1:
                    max_pct_s1 = max(max_pct_s1, tm["max_pct"])
                else:
                    max_pct_s2 = max(max_pct_s2, tm["max_pct"])
        gate_pass = (max_pct_s1 < 40.0 and max_pct_s2 < 40.0 and worst_ms < 1000.0)
        out(f"  {bname:<15}: S1 max={max_pct_s1:.1f}% bank, S2 max={max_pct_s2:.1f}% bank, worst_reply={worst_ms:.1f} ms -> Gate: {'PASS' if gate_pass else 'FAIL'}")

    # Parameter values comparison vs T_mean
    out("\n--- PARAMETER VALUES vs T_mean (STARTING VALUES) ---")
    STAGE_A_V5 = os.path.join(RUNS_ROOT, "train", "stage_a_v5")
    with open(os.path.join(STAGE_A_V5, "mean.json")) as f:
        t5_mean_p = json.load(f)
    with open(os.path.join(STAGE_A_V5, "best.json")) as f:
        t5_best_p = json.load(f)

    out(f"  {'PARAM':<20} {'T_mean (start)':<15} {'T5_mean':<15} {'T5_best':<15} {'Bounds':<20} {'Bound Status'}")
    out("  " + "-" * 95)
    for name in sorted(PARAMS.keys()):
        v_start = PARAMS[name]
        v_mean = t5_mean_p.get(name, v_start)
        v_best = t5_best_p.get(name, v_start)
        b = BOUNDS.get(name)
        b_str = f"[{b[0]:.2f}, {b[1]:.2f}]" if b else "None"
        hit_flags = []
        if b:
            if abs(v_mean - b[0]) < 1e-4: hit_flags.append("mean@LOWER")
            if abs(v_mean - b[1]) < 1e-4: hit_flags.append("mean@UPPER")
            if abs(v_best - b[0]) < 1e-4: hit_flags.append("best@LOWER")
            if abs(v_best - b[1]) < 1e-4: hit_flags.append("best@UPPER")
        status = " ".join(hit_flags)
        trained = "*" if name in STAGE_A_NAMES else " "
        if name in STAGE_A_NAMES or abs(v_mean - v_start) > 1e-4 or abs(v_best - v_start) > 1e-4 or status:
            out(f"  {trained}{name:<19} {v_start:<15.4f} {v_mean:<15.4f} {v_best:<15.4f} {b_str:<20} {status}")

    # Section 8 Acceptance Rule Summary
    out("\n--- ACCEPTANCE RULE CHECK (training-method Section 8, baseline = v4) ---")
    v4_avg_cap = sum(summary_metrics["v4"]["cap_list"]) / len(summary_metrics["v4"]["cap_list"])
    v4_win_share = summary_metrics["v4"]["wins"] / summary_metrics["v4"]["total_matches"]
    out(f"  v4 baseline: avg_capped_across_all_heldout = {v4_avg_cap:+.4f}, win_share = {v4_win_share*100:.2f}% ({summary_metrics['v4']['wins']}/{summary_metrics['v4']['total_matches']})")

    for bname in ("v5_A_untrained", "T5_best", "T5_mean"):
        avg_cap = sum(summary_metrics[bname]["cap_list"]) / len(summary_metrics[bname]["cap_list"])
        win_share = summary_metrics[bname]["wins"] / summary_metrics[bname]["total_matches"]
        flips = []
        for k, d in summary_metrics[bname]["matchups"].items():
            d0 = summary_metrics["v4"]["matchups"][k]
            if d0["w"] > d0["l"] and d["l"] > d["w"]:
                flips.append(f"{k}: {d0['w']}-{d0['l']} -> {d['w']}-{d['l']}")
        h2h = h2h_results.get(bname)
        h2h_str = f"{h2h['w']}-{h2h['d']}-{h2h['l']} ({h2h['mean']:+.3f} +- {h2h['ci']:.3f}, cap {h2h['cap']:+.3f})" if h2h else "N/A"
        h2h_not_neg = (h2h and (h2h['mean'] + h2h['ci'] >= 0.0)) if h2h else False
        out(f"\n  Candidate: {bname}")
        out(f"    1. Avg capped chips improves vs v4?  {avg_cap:+.4f} vs {v4_avg_cap:+.4f} (diff: {avg_cap - v4_avg_cap:+.4f}) -> {'PASS' if avg_cap > v4_avg_cap else ('TIE' if abs(avg_cap - v4_avg_cap) < 0.005 else 'FAIL')}")
        out(f"    2. Held-out win share >= v4?        {win_share*100:.2f}% ({summary_metrics[bname]['wins']}/{summary_metrics[bname]['total_matches']}) vs {v4_win_share*100:.2f}% -> {'PASS' if win_share >= v4_win_share else 'FAIL'}")
        out(f"    3. No win -> clear loss flips?      {flips if flips else 'None (PASS)'}")
        out(f"    4. H2H vs v4 not negative beyond CI? {h2h_str} -> {'PASS' if h2h_not_neg else 'FAIL'}")

    report_path = os.path.join(VAL_BASE, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    out(f"\nSaved full report to {report_path}")


if __name__ == "__main__":
    main()

