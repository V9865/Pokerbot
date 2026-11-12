"""CMA-ES Policy Trainer for Discard Hold'em.

Usage:
  py -3.11 tools/train.py --stage A [--gens 15] [--pop 12] [--jobs 8] [--hands 400] [--dry-run] [--resume]

Objectives and rules:
  - F = weighted mean of score over opponents
  - score = 0.6 * tanh(n / 0.25) + 0.4 * clip(n, -1, 1), where n = net / hands
  - Any notice, forfeit or traceback: score = -10.0
  - Common random numbers: all candidates in generation g play the exact same seeds
  - Checkpoints saved per generation to runs/train/<stage>/gen_NNN.json
  - One line appended per generation to memory/TRAINING_LOG.md
"""
import argparse
import csv
import datetime
import glob
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

# Ensure src is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from policy_params import STAGE_A_NAMES, PARAMS, BOUNDS, pack_stage_a, unpack_stage_a

try:
    import cma
    HAVE_CMA = True
except ImportError:
    HAVE_CMA = False


def score_match(net, hands, bad=False):
    """Calculates the match score: 0.6 * tanh(n/0.25) + 0.4 * clip(n, -1, 1)."""
    if bad or net is None:
        return -10.0
    h = max(1, hands or 400)
    n = float(net) / h
    return 0.6 * math.tanh(n / 0.25) + 0.4 * max(-1.0, min(1.0, n))


def resolve_opp(opp_name):
    """Resolves an opponent file path."""
    for p in (opp_name, os.path.join(ROOT, "opponents", opp_name + ".py"), os.path.join(ROOT, opp_name)):
        if os.path.isfile(p):
            return os.path.abspath(p)
    sys.exit(f"Opponent not found: {opp_name}")


def play_match(job):
    """Plays one match using starter/engine.py."""
    bot, opp, seed, stage, hands, logdir = job
    cmd = [
        sys.executable,
        os.path.join(ROOT, "starter", "engine.py"),
        bot,
        opp,
        "--seed", str(seed),
        "--stage", str(stage),
        "--log-dir", logdir
    ]
    if hands:
        cmd += ["--hands", str(hands)]
    env = os.environ.copy()
    env["MATCH_SEED"] = str(seed)
    
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    out = res.stdout
    
    r = {
        "opp": os.path.splitext(os.path.basename(opp))[0],
        "seed": seed,
        "net": None,
        "hands": None,
        "time_a": 0.0,
        "notices_a": 0,
        "forfeit": False,
        "traceback": False,
        "cap": None
    }
    m = re.search(r"\|\s*(\d+) of (\d+) hands played", out)
    if m:
        r["hands"] = int(m.group(2))
    for who in "AB":
        m = re.search(r"^\s*%s\s+\S+\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+) s.*notices\s+(\d+)" % who, out, re.M)
        if m and who == "A":
            r["net"], r["time_a"], r["notices_a"] = int(m.group(1)), float(m.group(2)), int(m.group(3))
    
    m_cap = re.search(r"Capped delta: A ([+-]?\d+)", out)
    if m_cap:
        r["cap"] = int(m_cap.group(1))
        
    if "Traceback (most recent call last)" in out or "Traceback (most recent call last)" in res.stderr:
        r["traceback"] = True
    if "forfeited" in out.lower() or "disqualified" in out.lower():
        r["forfeit"] = True
    return r


def evaluate_candidate(cand_bot, opp_list, seeds, stage, hands, jobs_count, cand_dir):
    """Evaluates candidate bot across all opponents on the specified seeds."""
    job_list = []
    for opp_name, opp_path in opp_list:
        for s in seeds:
            d = os.path.join(cand_dir, f"{opp_name}_{s}")
            os.makedirs(d, exist_ok=True)
            job_list.append((cand_bot, opp_path, s, stage, hands, d))
            
    with ThreadPoolExecutor(max_workers=jobs_count) as ex:
        results = list(ex.map(play_match, job_list))
        
    # Group results by opponent
    opp_scores = {}
    for r in results:
        opp_name = r["opp"]
        bad = r["forfeit"] or r["traceback"] or (r["notices_a"] > 0) or (r["net"] is None)
        sc = score_match(r["net"], r["hands"], bad)
        opp_scores.setdefault(opp_name, []).append(sc)
        
    return opp_scores, results


def run_training():
    parser = argparse.ArgumentParser(description="CMA-ES Policy Trainer")
    parser.add_argument("--stage", choices=["A", "B", "C", "D"], default="A", help="Training stage")
    parser.add_argument("--gens", type=int, default=15, help="Number of generations")
    parser.add_argument("--pop", type=int, default=12, help="Population size")
    parser.add_argument("--jobs", type=int, default=8, help="Parallel worker threads")
    parser.add_argument("--hands", type=int, default=None, help="Hands per match (override)")
    parser.add_argument("--dry-run", action="store_true", help="Quick dry run (pop 4, hands 40)")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--matches-per-opp", type=int, default=None, help="Matches per opponent per gen")
    parser.add_argument("--sigma0", type=float, default=0.15, help="Initial CMA-ES step size sigma0")
    parser.add_argument("--tag", default=None, help="Subdirectory tag under runs/train/ (default: stage_<stage>)")
    args = parser.parse_args()

    if not HAVE_CMA:
        sys.exit("cma package not installed. Run: py -3.11 -m pip install cma")

    # Load configuration
    cfg_path = os.path.join(ROOT, "tools", "train_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        train_cfg = json.load(f)

    raw_opps = train_cfg["training_opponents"]
    tot_weight = sum(raw_opps.values())
    opp_weights = {os.path.splitext(os.path.basename(k))[0]: v / tot_weight for k, v in raw_opps.items()}
    resolved_opps = [(os.path.splitext(os.path.basename(k))[0], resolve_opp(k)) for k in raw_opps.keys()]
    assert abs(sum(opp_weights.values()) - 1.0) < 1e-9, f"Weight sum error: {opp_weights}"
    assert max(opp_weights.values()) <= 0.15 + 1e-9, f"Opponent weight > 15%: {opp_weights}"

    if args.dry_run:
        args.gens = 1
        args.pop = 4
        args.hands = 40
        matches_per_opp = 1
    else:
        matches_per_opp = args.matches_per_opp if args.matches_per_opp is not None else 2

    stage_name = args.stage
    default_runs = r"C:\pokerbot_runs" if os.name == "nt" else os.path.join(ROOT, "runs")
    runs_dir = os.environ.get("POKERBOT_RUNS_DIR", default_runs)
    run_tag = args.tag or f"stage_{stage_name.lower()}"
    out_dir = os.path.join(runs_dir, "train", run_tag)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print(f"CMA-ES Policy Training - Stage {stage_name}")
    print(f"  Population: {args.pop}, Target Generations: {args.gens}, Jobs: {args.jobs}, Sigma0: {args.sigma0}")
    print(f"  Opponents: {len(resolved_opps)} (Total weight: {tot_weight})")
    print(f"  Matches per opponent: {matches_per_opp}")
    print(f"  Output directory: {out_dir}")
    print("=" * 60)

    # Initial vector in unit cube
    x0 = pack_stage_a(PARAMS)
    sigma0 = float(args.sigma0)
    es = cma.CMAEvolutionStrategy(x0, sigma0, {
        "bounds": [0.0, 1.0],
        "popsize": args.pop,
        "seed": 42
    })

    start_gen = 1
    if args.resume:
        latest_pkl = os.path.join(out_dir, "cma_latest.pkl")
        checkpoints = sorted(glob.glob(os.path.join(out_dir, "gen_*.json")))
        loaded_pkl = False
        if os.path.isfile(latest_pkl):
            try:
                with open(latest_pkl, "rb") as pf:
                    es = pickle.load(pf)
                loaded_pkl = True
                print(f"Loaded CMA-ES state from {latest_pkl} (sigma={es.sigma:.4f})")
            except Exception as e:
                print(f"Could not load {latest_pkl} ({e}), initializing fresh CMA with checkpoint mean")
        if checkpoints:
            latest_ck = checkpoints[-1]
            with open(latest_ck, "r", encoding="utf-8") as f:
                ck_data = json.load(f)
            start_gen = ck_data["gen"] + 1
            print(f"Resuming from generation {start_gen} (latest checkpoint {latest_ck})")
            if not loaded_pkl and ("mean_params" in ck_data or "best_params" in ck_data):
                x_resume = pack_stage_a(ck_data.get("mean_params") or ck_data["best_params"])
                sigma_resume = ck_data.get("sigma", 0.15)
                es = cma.CMAEvolutionStrategy(x_resume, sigma_resume, {
                    "bounds": [0.0, 1.0],
                    "popsize": args.pop,
                    "seed": 42 + start_gen
                })

    log_file = os.path.join(ROOT, "memory", "TRAINING_LOG.md")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    total_matches_run = 0

    target_gens = args.gens if not args.resume else max(args.gens, start_gen + args.gens - 1)
    if start_gen > target_gens:
        print(f"Target generations ({target_gens}) already reached (start_gen={start_gen}). Nothing to do.")
        return

    for gen in range(start_gen, target_gens + 1):
        gen_start_time = time.time()
        # Keep training seeds strictly < 5000 (below held-out >= 5000 and << 50000)
        seeds = [100 + ((gen - 1) * max(20, matches_per_opp) + k) % 4800 for k in range(matches_per_opp)]
        
        # Decide match stage length: early short matches (100 hands) in first third, then Stage 1 length (400 hands)
        if args.hands is not None:
            match_hands = args.hands
            match_stage = 1 if match_hands <= 400 else 2
        elif gen <= max(1, target_gens // 3):
            match_hands = 100
            match_stage = 1
        else:
            match_hands = 400
            match_stage = 1

        solutions = es.ask()
        fitnesses = []
        gen_candidates_info = []

        print(f"\n--- Generation {gen:03d} of {target_gens:03d} (Seeds: {seeds}, Stage: {match_stage}, Hands: {match_hands}) ---")

        for idx, cand_vec in enumerate(solutions):
            cand_id = f"gen_{gen:03d}_cand_{idx:02d}"
            cand_dir = os.path.join(out_dir, cand_id)
            os.makedirs(cand_dir, exist_ok=True)

            # Unpack parameters
            cand_params = unpack_stage_a(cand_vec)
            params_file = os.path.join(cand_dir, "params.json")
            with open(params_file, "w", encoding="utf-8") as pf:
                json.dump(cand_params, pf, indent=2)

            # Bundle candidate variant
            cand_bot_path = os.path.join(cand_dir, "bot.py")
            bundle_cmd = [
                sys.executable,
                os.path.join(ROOT, "tools", "bundle.py"),
                cand_bot_path,
                "--params", params_file
            ]
            bundle_res = subprocess.run(bundle_cmd, capture_output=True, text=True)
            if bundle_res.returncode != 0:
                print(f"Error bundling candidate {cand_id}: {bundle_res.stderr}")
                fitnesses.append(10.0) # CMA minimizes, so higher is worse
                continue

            # Evaluate candidate
            opp_scores, raw_matches = evaluate_candidate(
                cand_bot_path,
                resolved_opps,
                seeds,
                match_stage,
                match_hands,
                args.jobs,
                cand_dir
            )
            total_matches_run += len(raw_matches)

            # Calculate weighted F
            weighted_F = 0.0
            used_w = 0.0
            for opp_name, scores in opp_scores.items():
                w = opp_weights.get(opp_name, 0.0)
                if w <= 0.0:
                    raise RuntimeError(f"Unweighted opponent {opp_name!r} in opp_scores!")
                used_w += w
                mean_sc = sum(scores) / len(scores) if scores else -10.0
                weighted_F += w * mean_sc
            assert abs(used_w - 1.0) < 1e-6, f"Used weights {used_w} != 1.0 (missing opponent?)"

            fitnesses.append(-weighted_F) # CMA minimizes -F
            gen_candidates_info.append({
                "idx": idx,
                "F": weighted_F,
                "params": cand_params
            })
            print(f"  Cand {idx:02d}: F = {weighted_F:+.4f}")

        # Update CMA-ES
        es.tell(solutions, fitnesses)

        gen_elapsed = time.time() - gen_start_time
        best_cand = max(gen_candidates_info, key=lambda c: c["F"])
        mean_F = -float(np.mean(fitnesses))
        best_F = best_cand["F"]

        print(f"Gen {gen:03d} finished in {gen_elapsed:.1f} s | Best F: {best_F:+.4f} | Mean F: {mean_F:+.4f}")

        # Save checkpoint (including CMA-ES mean in JSON so it is Python/NumPy-version independent)
        mean_params = unpack_stage_a(es.mean)
        checkpoint_data = {
            "stage": stage_name,
            "gen": gen,
            "best_F": best_F,
            "mean_F": mean_F,
            "elapsed_s": gen_elapsed,
            "best_params": best_cand["params"],
            "mean_params": mean_params,
            "sigma": es.sigma
        }
        ck_path = os.path.join(out_dir, f"gen_{gen:03d}.json")
        with open(ck_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        # Save CMA-ES optimizer state for exact resume
        try:
            with open(os.path.join(out_dir, f"cma_gen_{gen:03d}.pkl"), "wb") as pf:
                pickle.dump(es, pf)
            with open(os.path.join(out_dir, "cma_latest.pkl"), "wb") as pf:
                pickle.dump(es, pf)
        except Exception as e:
            print(f"Warning: could not pickle CMA-ES state: {e}")

        # Write current best and CMA-ES mean
        with open(os.path.join(out_dir, "best.json"), "w", encoding="utf-8") as f:
            json.dump(best_cand["params"], f, indent=2)
        with open(os.path.join(out_dir, "mean.json"), "w", encoding="utf-8") as f:
            json.dump(mean_params, f, indent=2)

        # Log line to TRAINING_LOG.md
        now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = (
            f"| {now_iso} | Stage {stage_name} | Gen {gen:03d} | "
            f"Best F: {best_F:+.4f} | Mean F: {mean_F:+.4f} | "
            f"Sigma: {es.sigma:.4f} | Matches: {total_matches_run} | Time: {gen_elapsed:.1f}s |\n"
        )
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)

    print("\nTraining complete! Best parameters saved to:", os.path.join(out_dir, "best.json"))


if __name__ == "__main__":
    run_training()

