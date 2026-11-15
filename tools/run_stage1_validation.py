"""Validation suite for v6 vs v5 at REAL Stage 1 length (no --hands flag, 400 hands per match).
Fresh seeds 96000-96039 for held-out opponents, and seeds 96100-96199 for head-to-head v6 vs v5.

Usage:
  py -3.11 tools/run_stage1_validation.py [--jobs 10] [--force]
"""
import argparse
import csv
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_ROOT = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
VAL_BASE = os.path.join(RUNS_ROOT, "val_s1_real")


def run_batch(bot_path, opps_csv, seeds, jobs, tag, stage=1, force=False):
    out_dir = os.path.join(RUNS_ROOT, tag)
    csv_path = os.path.join(out_dir, "results.csv")
    if os.path.isfile(csv_path) and not force:
        print(f"[SKIP] {tag} already has results.csv", flush=True)
        return csv_path

    t0 = time.time()
    print(f"[RUN ] {tag}: bot={os.path.basename(bot_path)} opps={opps_csv} seeds={seeds} jobs={jobs} stage={stage}", flush=True)
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


def scan_timing(tag, bank=30.0):
    """Scan all A_leg1_stderr.txt and A_leg2_stderr.txt in RUNS_ROOT/<tag>."""
    base = os.path.join(RUNS_ROOT, tag)
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
    return f"{wdl:<8} {st['mean']:+6.2f}+-{st['ci']:4.2f} ({st['cap']:+5.2f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.makedirs(VAL_BASE, exist_ok=True)
    bots = {
        "v5": os.path.join(ROOT, "snapshots", "v5_bot.py"),
        "v6": os.path.join(ROOT, "dist", "bot.py"),
    }
    for k, p in bots.items():
        if not os.path.isfile(p):
            sys.exit(f"Missing bot {k}: {p}")

    fixed_opps = ["friend", "gto_like", "liar", "lag", "rof_big", "nit", "ai_typical", "exploiter2"]
    fixed_csv = ",".join(fixed_opps)

    t_start = time.time()

    # 1. Held-out fixed opponents (seeds 96000-96039, Real Stage 1 = 400 hands)
    for name, bpath in bots.items():
        run_batch(bpath, fixed_csv, "96000-96039", args.jobs, f"val_s1_real/fixed_{name}", stage=1, force=args.force)

    # 2. 40 Personas (seeds 96000-96039, Real Stage 1 = 400 hands)
    for name, bpath in bots.items():
        run_batch(bpath, "persona", "96000-96039", args.jobs, f"val_s1_real/persona_{name}", stage=1, force=args.force)

    # 3. Head-to-head v6 vs v5 (seeds 96100-96199, Real Stage 1 = 400 hands)
    run_batch(bots["v6"], "snapshots/v5_bot.py", "96100-96199", args.jobs, "val_s1_real/h2h_v6_vs_v5", stage=1, force=args.force)

    # 4. Serial timing for v6 (--jobs 1, Stage 1 bank = 30s)
    run_batch(bots["v6"], "friend,gto_like,maniac", "96000-96001", 1, "val_s1_real/timing_v6_serial", stage=1, force=args.force)

    total_dt = time.time() - t_start
    print(f"\nAll validation batches completed in {total_dt/60.0:.1f} min.", flush=True)

    # Report generation
    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("=" * 110)
    out("REAL STAGE 1 VALIDATION REPORT (400 hands/match; Fresh seeds 96000-96039 & 96100-96199)")
    out("=" * 110)

    all_held_opps = fixed_opps + ["persona"]
    summary_metrics = {b: {"cap_list": [], "wins": 0, "losses": 0, "total_matches": 0, "matchups": {}} for b in bots}

    out(f"\n--- HELD-OUT OPPONENTS (Stage 1 400 hands/match, 40 matches each, seeds 96000-96039) ---")
    out(f"{'Opponent':<13} | {'v5 Baseline (W-D-L chips+-CI cap)':<35} | {'v6 Candidate (W-D-L chips+-CI cap)':<35} | {'Win Diff (v6 - v5)'}")
    out("-" * 110)

    for opp in all_held_opps:
        cells = []
        d_map = {}
        for bname in ("v5", "v6"):
            tag = f"val_s1_real/{'persona' if opp == 'persona' else 'fixed'}_{bname}"
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
        w_v6 = d_map["v6"]["w"] if d_map.get("v6") else 0
        diff_w = w_v6 - w_v5
        out(f"{opp:<13} | {cells[0]:<35} | {cells[1]:<35} | {diff_w:+d} wins")

    # Overall summary
    out("\n--- OVERALL HELD-OUT TOTALS ---")
    w_tot_v5 = summary_metrics["v5"]["wins"]
    n_tot_v5 = summary_metrics["v5"]["total_matches"]
    w_tot_v6 = summary_metrics["v6"]["wins"]
    n_tot_v6 = summary_metrics["v6"]["total_matches"]

    avg_cap_v5 = sum(summary_metrics["v5"]["cap_list"]) / len(summary_metrics["v5"]["cap_list"]) if summary_metrics["v5"]["cap_list"] else 0.0
    avg_cap_v6 = sum(summary_metrics["v6"]["cap_list"]) / len(summary_metrics["v6"]["cap_list"]) if summary_metrics["v6"]["cap_list"] else 0.0

    out(f"  v5 Baseline : {w_tot_v5}/{n_tot_v5} wins ({w_tot_v5/n_tot_v5*100:.2f}%) | Avg Capped: {avg_cap_v5:+.4f} chips/hand")
    out(f"  v6 Candidate: {w_tot_v6}/{n_tot_v6} wins ({w_tot_v6/n_tot_v6*100:.2f}%) | Avg Capped: {avg_cap_v6:+.4f} chips/hand")
    out(f"  Total Win Delta (v6 - v5): {w_tot_v6 - w_tot_v5:+d} wins")

    # GTO-like check
    gto_v5_cap = summary_metrics["v5"]["matchups"]["gto_like"]["cap"]
    gto_v6_cap = summary_metrics["v6"]["matchups"]["gto_like"]["cap"]
    gto_cap_diff = gto_v6_cap - gto_v5_cap
    out(f"\n--- GTO_LIKE CAPPED CHIPS CHECK ---")
    out(f"  v5 gto_like cap: {gto_v5_cap:+.4f}")
    out(f"  v6 gto_like cap: {gto_v6_cap:+.4f}")
    out(f"  Delta (v6 - v5): {gto_cap_diff:+.4f} (Rule: not worse by more than 0.15, i.e. >= -0.1500)")

    # Head-to-Head
    out("\n--- HEAD-TO-HEAD v6 vs snapshots/v5_bot.py (Stage 1 400 hands, seeds 96100-96199, n=100) ---")
    st_map = load_csv_stats(os.path.join(RUNS_ROOT, "val_s1_real/h2h_v6_vs_v5", "results.csv"))
    h2h_res = st_map.get("v5_bot") or (list(st_map.values())[0] if st_map else None)
    if h2h_res:
        out(f"  v6 vs v5_bot: W-D-L = {h2h_res['w']}-{h2h_res['d']}-{h2h_res['l']}, chips/hand = {h2h_res['mean']:+.3f} +- {h2h_res['ci']:.3f}, capped = {h2h_res['cap']:+.3f}, notices={h2h_res['notices']}, forfeits={h2h_res['forfeits']}, tb={h2h_res['tracebacks']}")
    else:
        out("  v6 vs v5_bot: NO DATA")

    # Serial timing for v6
    out("\n--- SERIAL TIMING FOR v6 (Stage 1, bank 30s/leg, friend,gto_like,maniac seeds 96000-96001) ---")
    tm = scan_timing("val_s1_real/timing_v6_serial", bank=30.0)
    if tm:
        out(f"  Legs scanned   : {tm['legs']}")
        out(f"  Mean % bank    : {tm['mean_pct']:.2f}%")
        out(f"  Max % bank     : {tm['max_pct']:.2f}%")
        out(f"  Worst reply    : {tm['worst_reply_ms']:.1f} ms")
        out(f"  Errors/Notices : errors={tm['errors']}, notices={tm['notices']}")
    else:
        out("  Timing: NO DATA")

    # Acceptance Criteria Check
    out("\n--- ACCEPTANCE CRITERIA CHECK ---")
    rule1_pass = w_tot_v6 >= w_tot_v5
    out(f"  1. Field wins >= v5?                 {w_tot_v6} vs {w_tot_v5} ({w_tot_v6 - w_tot_v5:+d}) -> {'PASS' if rule1_pass else 'FAIL'}")

    rule2_pass = gto_cap_diff >= -0.1500
    out(f"  2. gto_like cap not worse by > 0.15? Delta: {gto_cap_diff:+.4f} (min -0.1500) -> {'PASS' if rule2_pass else 'FAIL'}")

    h2h_chips = h2h_res["mean"] if h2h_res else -999.0
    rule3_pass = h2h_chips >= 0.0
    out(f"  3. H2H chips/hand >= 0?              {h2h_chips:+.3f} -> {'PASS' if rule3_pass else 'FAIL'}")

    keep_v6 = rule1_pass and rule2_pass and rule3_pass
    out(f"\nFINAL DECISION: {'KEEP v6' if keep_v6 else 'RESTORE v5'}")

    report_path = os.path.join(VAL_BASE, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    out(f"\nSaved report to {report_path}")


if __name__ == "__main__":
    main()
