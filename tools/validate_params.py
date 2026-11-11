"""Validation tool for trained parameters against held-out opponents.

Usage:
  py -3.11 tools/validate_params.py runs/train/stage_a/best.json [--seeds 5000-5039] [--jobs 8]
"""
import argparse
import json
import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def run_validation():
    parser = argparse.ArgumentParser(description="Validate trained parameters")
    parser.add_argument("params_file", help="Path to best.json params file")
    parser.add_argument("--seeds", default="5000-5039", help="Seed range for held-out validation")
    parser.add_argument("--jobs", type=int, default=8, help="Number of worker jobs")
    args = parser.parse_args()

    params_path = os.path.abspath(args.params_file)
    if not os.path.isfile(params_path):
        sys.exit(f"Params file not found: {params_path}")

    # Build validation variant bot
    val_bot_dir = os.path.join(ROOT, "runs", "variants")
    os.makedirs(val_bot_dir, exist_ok=True)
    val_bot_path = os.path.join(val_bot_dir, "cand_val_bot.py")

    print(f"Bundling validation variant with {params_path}...")
    bundle_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "bundle.py"),
        val_bot_path,
        "--params", params_path
    ]
    res = subprocess.run(bundle_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"Failed to bundle validation variant:\n{res.stderr}")

    # Held out opponents
    cfg_path = os.path.join(ROOT, "tools", "train_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        train_cfg = json.load(f)

    held_out_opps = train_cfg.get("held_out_opponents", ["friend", "liar", "ai_typical", "exploiter2"])
    
    print("\nRunning Validation against Held-out Opponents...")
    print(f"  Opponents: {held_out_opps} + 30 Personas (5000-5029) + Head-to-Head vs v1_1")
    print(f"  Seeds: {args.seeds}")
    
    # 1. Run against held-out fixed opponents (friend, liar, ai_typical, exploiter2)
    opps_str = ",".join(held_out_opps + ["snapshots/v1_1_bot.py"])
    run_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_matches.py"),
        "--bot", val_bot_path,
        "--opps", opps_str,
        "--seeds", args.seeds,
        "--stage", "2",
        "--jobs", str(args.jobs),
        "--tag", "val_held_out"
    ]
    subprocess.run(run_cmd)

    # 2. Run against 30 fixed personas (seeds 5000-5029)
    run_persona_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_matches.py"),
        "--bot", val_bot_path,
        "--opps", "persona",
        "--seeds", "5000-5029",
        "--stage", "2",
        "--jobs", str(args.jobs),
        "--tag", "val_personas"
    ]
    subprocess.run(run_persona_cmd)


if __name__ == "__main__":
    run_validation()

