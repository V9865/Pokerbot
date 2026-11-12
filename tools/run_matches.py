"""Run batches of matches in parallel and summarise them.

  py -3.11 tools\run_matches.py --bot dist\bot.py --opps all --seeds 1-20 --tag NAME
      [--stage 1|2] [--jobs N] [--hands N]

Our bot plays seat A. Exit code 1 if our bot produced any notice, forfeit or
traceback. Timing from parallel runs is inflated; use tools\timing_report.py.
"""
import argparse, csv, math, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZOO = [
    "station", "random_bot", "shover", "maniac", "nit", "minraiser",
    "ai_typical", "ai_typical_v2", "gto_like", "raise_or_fold",
    "rof_tight", "rof_loose", "rof_big", "rof_small", "liar", "friend",
    "persona", "exploiter", "exploiter2", "lag"
]


def parse_seeds(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def resolve(name):
    for p in (name, os.path.join(ROOT, "opponents", name + ".py"), os.path.join(ROOT, name)):
        if os.path.isfile(p):
            return os.path.abspath(p)
    sys.exit("opponent not found: " + name)


def play(job):
    bot, opp, seed, args, logdir = job
    cmd = [sys.executable, os.path.join(ROOT, "starter", "engine.py"), bot, opp,
           "--seed", str(seed), "--stage", str(args.stage), "--log-dir", logdir]
    if args.hands:
        cmd += ["--hands", str(args.hands)]
    env = os.environ.copy()
    env["MATCH_SEED"] = str(seed)
    out = subprocess.run(cmd, env=env, capture_output=True, text=True).stdout
    r = {"opp": os.path.splitext(os.path.basename(opp))[0], "seed": seed, "net": None, "hands": None,
         "time_a": 0.0, "notices_a": 0, "notices_b": 0, "forfeit": "", "traceback": 0, "cap": None}
    m = re.search(r"\|\s*(\d+) of (\d+) hands played", out)
    if m:
        r["hands"] = int(m.group(2))
    for who in "AB":
        m = re.search(r"^\s*%s\s+\S+\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+) s.*notices\s+(\d+)" % who, out, re.M)
        if m and who == "A":
            r["net"], r["time_a"], r["notices_a"] = int(m.group(1)), float(m.group(2)), int(m.group(3))
        elif m:
            r["notices_b"] = int(m.group(3))
    m = re.search(r"Capped delta: A ([+-]?\d+)", out)
    if m:
        r["cap"] = int(m.group(1))
    if "forfeit" in out.lower():
        r["forfeit"] = " ".join(l.strip() for l in out.splitlines() if "forfeit" in l.lower())[:200]
    for leg in (1, 2):
        p = os.path.join(logdir, "A_leg%d_stderr.txt" % leg)
        if os.path.isfile(p) and b"Traceback" in open(p, "rb").read():
            r["traceback"] += 1
    if r["net"] is None:
        r["forfeit"] = r["forfeit"] or "could not parse engine output: " + out[-200:].replace("\n", " ")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default=os.path.join(ROOT, "dist", "bot.py"))
    ap.add_argument("--opps", default="all")
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--hands", type=int)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()
    bot = os.path.abspath(args.bot)
    opps = []
    for o in args.opps.split(","):
        opps += ZOO if o == "all" else [o]
    seeds = parse_seeds(args.seeds)
    default_runs = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
    runs_dir = os.environ.get("POKERBOT_RUNS_DIR", default_runs)
    base = os.path.join(runs_dir, args.tag)
    jobs = []
    for o in opps:
        path = resolve(o)
        for s in seeds:
            d = os.path.join(base, "%s_%d" % (os.path.splitext(os.path.basename(path))[0], s))
            os.makedirs(d, exist_ok=True)
            jobs.append((bot, path, s, args, d))
    with ThreadPoolExecutor(args.jobs) as ex:
        rows = list(ex.map(play, jobs))
    with open(os.path.join(base, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("%-16s %5s %9s %10s %8s %8s %7s %s" % ("opponent", "n", "W-D-L", "chips/hand", "95% CI", "capped", "time s", "problems"))
    bad = 0
    for o in dict.fromkeys(r["opp"] for r in rows):
        rs = [r for r in rows if r["opp"] == o and r["net"] is not None]
        n = len(rs)
        prob = sum(r["notices_a"] for r in rows if r["opp"] == o) + sum(1 for r in rows if r["opp"] == o and (r["forfeit"] or r["traceback"]))
        bad += prob
        if not n:
            print("%-16s no parsed results" % o)
            continue
        per = [r["net"] / float(r["hands"] or 400) for r in rs]
        mean = sum(per) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in per) / (n - 1)) if n > 1 else 0.0
        w_, d_, l_ = sum(r["net"] > 0 for r in rs), sum(r["net"] == 0 for r in rs), sum(r["net"] < 0 for r in rs)
        cap = sum((r["cap"] or 0) for r in rs) / float(sum((r["hands"] or 400) for r in rs))
        print("%-16s %5d %9s %+10.2f %8s %+8.2f %7.1f %s" % (o, n, "%d-%d-%d" % (w_, d_, l_), mean,
              "+-%.2f" % (1.96 * sd / math.sqrt(n)), cap, max(r["time_a"] for r in rs), prob or ""))
    for r in rows:
        if r["forfeit"] or r["traceback"] or r["notices_a"]:
            print("PROBLEM", r["opp"], "seed", r["seed"], "notices", r["notices_a"], "tracebacks", r["traceback"], r["forfeit"])
    print("results: " + os.path.join(base, "results.csv"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
