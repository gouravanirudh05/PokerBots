#!/usr/bin/env python3
"""
Run many local matches in parallel and summarise the results.

    python3.11 tools/arena.py BOT_A BOT_B [--matches 8] [--jobs 8] [--stage 1] [--hands N]

Each match uses a different seed. Reports A's mean net chips per match with its
standard error, wins/draws/losses, forfeits, and the worst time-bank usage.
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, stdev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "Starter_Kit", "engine.py")
VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
NET = re.compile(r"^\s+([AB])\s+.*net\s+([+-]\d+)\s+time used\s+([\d.]+) s.*notices (\d+)", re.M)


def run(args, seed):
    cmd = [args.python, ENGINE, args.bot_a, args.bot_b, "--python", args.python,
           "--stage", str(args.stage), "--seed", str(seed), "--log-dir", ""]
    if args.hands:
        cmd += ["--hands", str(args.hands)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = {m.group(1): m.groups()[1:] for m in NET.finditer(out)}
    a = rows.get("A", ("0", "0", "0"))
    return int(a[0]), float(a[1]), int(a[2]), "forfeit" in out, out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("bot_a")
    p.add_argument("bot_b")
    p.add_argument("--matches", type=int, default=8)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--stage", type=int, default=1)
    p.add_argument("--hands", type=int)
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--python", default=VENV_PY if os.path.exists(VENV_PY) else sys.executable)
    args = p.parse_args()
    args.bot_a, args.bot_b = os.path.abspath(args.bot_a), os.path.abspath(args.bot_b)

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda s: run(args, s), range(args.seed, args.seed + args.matches)))
    nets = [r[0] for r in results]
    for r in results:
        if r[3]:
            print(r[4])
    se = stdev(nets) / len(nets) ** 0.5 if len(nets) > 1 else 0.0
    wins = sum(n > 0 for n in nets)
    draws = sum(n == 0 for n in nets)
    print(f"{os.path.basename(os.path.dirname(args.bot_a))}/{os.path.basename(args.bot_a)} vs "
          f"{os.path.basename(args.bot_b)}: mean {mean(nets):+.1f} ± {se:.1f} per match | "
          f"W/D/L {wins}/{draws}/{len(nets) - wins - draws} | forfeits {sum(r[3] for r in results)} | "
          f"max time {max(r[1] for r in results):.1f} s | notices {sum(r[2] for r in results)}")
    print("nets:", nets)


if __name__ == "__main__":
    main()
