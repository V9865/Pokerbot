"""Timing check: plays matches ONE AT A TIME (no parallel load) and reports our
bot's own thinking time per leg, read from its stderr SUMMARY line.

  py -3.11 tools\timing_report.py [--stage 1|2] [--opps maniac,gto_like] [--seeds 1-2]
Fails if any leg uses more than 40% of the time bank or any reply exceeds 250 ms.
"""
import argparse, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--bot", default=os.path.join(ROOT, "dist", "bot.py"))
ap.add_argument("--stage", type=int, default=1)
ap.add_argument("--opps", default="maniac,gto_like")
ap.add_argument("--seeds", default="1-2")
args = ap.parse_args()
a, b = (args.seeds.split("-") + [args.seeds])[:2]
bank = 30.0 if args.stage == 1 else 75.0
bad = 0
print("%-12s %5s %4s %9s %8s %12s  %s" % ("opponent", "seed", "leg", "think s", "% bank", "max reply ms", "modes F/H/Q/P"))
for opp in args.opps.split(","):
    for seed in range(int(a), int(b) + 1):
        d = os.path.join(ROOT, "runs", "timing", "%s_s%d_%d" % (opp, args.stage, seed))
        os.makedirs(d, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "starter", "engine.py"), os.path.abspath(args.bot),
                        os.path.join(ROOT, "opponents", opp + ".py"), "--seed", str(seed), "--stage", str(args.stage),
                        "--log-dir", d], capture_output=True, text=True)
        for leg in (1, 2):
            p = os.path.join(d, "A_leg%d_stderr.txt" % leg)
            text = open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
            m = re.search(r"SUMMARY \S+ hands=(\d+) think_s=([\d.]+) max_reply_ms=([\d.]+) modes=(\[[^\]]*\]) errors=(\d+)", text)
            if not m:
                print("%-12s %5d %4d  no SUMMARY line found" % (opp, seed, leg))
                bad += 1
                continue
            think, mx = float(m.group(2)), float(m.group(3))
            flag = ""
            if think > 0.40 * bank or mx > 250 or int(m.group(5)):
                flag, bad = "  <-- PROBLEM", bad + 1
            print("%-12s %5d %4d %9.2f %7.1f%% %12.1f  %s%s" % (opp, seed, leg, think, 100 * think / bank, mx, m.group(4), flag))
print("RESULT:", "OK" if not bad else "%d PROBLEMS" % bad)
sys.exit(1 if bad else 0)
