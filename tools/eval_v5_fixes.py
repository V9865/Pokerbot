"""Evaluate v5 fix combinations A, B, C, D vs snapshots/v4_bot.py on Stage 1 fresh seeds 91000+."""
import argparse
import csv
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_ROOT = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
BASE_TAG = "val_v5_fixes"


VARIANTS = {
    "A": [("FIX_BUCKET", "True"),  ("PF_3BET_SCALE", "True")],
    "B": [("FIX_BUCKET", "True"),  ("PF_3BET_SCALE", "False")],
    "C": [("FIX_BUCKET", "False"), ("PF_3BET_SCALE", "True")],
    "D": [("FIX_BUCKET", "False"), ("PF_3BET_SCALE", "False")],
}


def bundle_variant(name, overrides):
    out_dir = os.path.join(RUNS_ROOT, "variants")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"v5_{name}.py")
    cmd = [sys.executable, os.path.join(ROOT, "tools", "bundle.py"), out_path]
    for k, v in overrides + [("RAISE_EV", "False"), ("USE_FREQ_FLOOR", "False")]:
        cmd += ["--set", f"{k}={v}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"Failed bundling {name}:\n{res.stderr}")
    return out_path


def run_batch(bot_path, opps_csv, seeds, jobs, tag, force=False):
    csv_path = os.path.join(RUNS_ROOT, tag, "results.csv")
    if os.path.isfile(csv_path) and not force:
        print(f"[SKIP] {tag}", flush=True)
        return csv_path
    t0 = time.time()
    print(f"[RUN ] {tag}: {os.path.basename(bot_path)} vs {opps_csv} ({seeds})", flush=True)
    cmd = [
        sys.executable, os.path.join(ROOT, "tools", "run_matches.py"),
        "--bot", bot_path, "--opps", opps_csv, "--seeds", seeds,
        "--stage", "1", "--jobs", str(jobs), "--tag", tag,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[DONE] {tag} in {time.time() - t0:.1f}s (exit={res.returncode})", flush=True)
    return csv_path


def load_stats(csv_path):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    out = {}
    for opp in dict.fromkeys(r["opp"] for r in rows):
        rs = [r for r in rows if r["opp"] == opp and r["net"] not in (None, "")]
        n = len(rs)
        probs = sum(int(r["notices_a"] or 0) + int(r["traceback"] or 0) + (1 if (r.get("forfeit") or "").strip() else 0)
                    for r in rows if r["opp"] == opp)
        per = [float(r["net"]) / float(r["hands"] or 400) for r in rs]
        cap_per = [float(r["cap"] or 0) / float(r["hands"] or 400) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        cap_mean = sum(cap_per) / n
        cap_sd = math.sqrt(sum((x - cap_mean) ** 2 for x in cap_per) / (n - 1)) if n > 1 else 0.0
        out[opp] = {
            "n": n,
            "w": sum(1 for r in rs if float(r["net"]) > 0),
            "d": sum(1 for r in rs if float(r["net"]) == 0),
            "l": sum(1 for r in rs if float(r["net"]) < 0),
            "mean": mean, "ci": 1.96 * sd / math.sqrt(n),
            "cap": cap_mean, "cap_ci": 1.96 * cap_sd / math.sqrt(n),
            "problems": probs,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    field_opps = ["friend", "gto_like", "liar", "rof_big", "exploiter2", "ai_typical_v2", "persona"]
    field_csv = ",".join(field_opps)
    v4_path = os.path.join(ROOT, "snapshots", "v4_bot.py")

    bots = {"v4": v4_path}
    for name, ov in VARIANTS.items():
        bots[name] = bundle_variant(name, ov)

    for name, bpath in bots.items():
        run_batch(bpath, field_csv, "91000-91019", args.jobs, f"{BASE_TAG}/field_{name}", args.force)
        if name != "v4":
            run_batch(bpath, "snapshots/v4_bot.py", "91000-91039", args.jobs, f"{BASE_TAG}/h2h_{name}", args.force)

    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("=" * 115)
    out("V5 FIX-SET SELECTION (Stage 1; field seeds 91000-91019 n=20; H2H vs v4 seeds 91000-91039 n=40)")
    out("=" * 115)
    header = f"{'opp':<14} | {'v4 (W-D-L cap+-CI)':<22} | {'A (T,T)':<22} | {'B (T,F)':<22} | {'C (F,T)':<22} | {'D (F,F)':<22}"
    out(header)
    out("-" * 126)

    stats = {name: load_stats(os.path.join(RUNS_ROOT, f"{BASE_TAG}/field_{name}", "results.csv")) for name in bots}
    h2h = {name: load_stats(os.path.join(RUNS_ROOT, f"{BASE_TAG}/h2h_{name}", "results.csv"))["v4_bot"] for name in VARIANTS}

    for opp in field_opps:
        cells = []
        for name in ("v4", "A", "B", "C", "D"):
            d = stats[name][opp]
            cells.append(f"{d['w']}-{d['d']}-{d['l']:<2} {d['cap']:+5.2f}+-{d['cap_ci']:4.2f}")
        out(f"{opp:<14} | " + " | ".join(f"{c:<22}" for c in cells))

    out("-" * 126)
    avg_caps = {}
    for name in ("v4", "A", "B", "C", "D"):
        avg_caps[name] = sum(stats[name][o]["cap"] for o in field_opps) / len(field_opps)
    out("Field avg cap  | " + " | ".join(f"{avg_caps[n]:+22.4f}" for n in ("v4", "A", "B", "C", "D")))

    out("\nRaw chips/hand +- 95% CI per opponent:")
    for opp in field_opps:
        cells = []
        for name in ("v4", "A", "B", "C", "D"):
            d = stats[name][opp]
            cells.append(f"{d['mean']:+6.2f}+-{d['ci']:4.2f} (p={d['problems']})")
        out(f"{opp:<14} | " + " | ".join(f"{c:<22}" for c in cells))

    out("\nHead-to-Head vs snapshots/v4_bot.py (Stage 1, seeds 91000-91039, n=40):")
    for name in ("A", "B", "C", "D"):
        d = h2h[name]
        flips = []
        for opp in field_opps:
            dv4, dv = stats["v4"][opp], stats[name][opp]
            if dv4["w"] > dv4["l"] and dv["l"] > dv["w"]:
                flips.append(f"{opp}: {dv4['w']}-{dv4['l']} -> {dv['w']}-{dv['l']}")
        neg_beyond_ci = (d["mean"] + d["ci"]) < 0.0
        out(f"  {name} {VARIANTS[name]}: W-D-L={d['w']}-{d['d']}-{d['l']}, raw={d['mean']:+.3f}+-{d['ci']:.3f}, cap={d['cap']:+.3f}+-{d['cap_ci']:.3f}, probs={d['problems']}, neg_beyond_CI={neg_beyond_ci}, flips={flips}")

    report_file = os.path.join(RUNS_ROOT, BASE_TAG, "report.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    out(f"\nSaved to {report_file}")


if __name__ == "__main__":
    main()

