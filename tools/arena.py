#!/usr/bin/env python3
"""
Run many local matches in parallel and summarise the results.

    python3.11 tools/arena.py BOT_A OPP [OPP ...] [--matches 8] [--jobs 8] [--stage 1]
                              [--hands N] [--no-time-limits] [--log-root DIR]

Each match uses a different seed (the same seeds for every opponent, so
comparisons between bots see the same deals). For each opponent it reports A's
mean net chips per match with its standard error, chips per hand,
wins/draws/losses, forfeits and the worst time-bank usage. Set BOT_NO_LOCK=1 in
the environment to turn off the bots' match-lock fold-out and measure raw chip
rates.
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
PLAYED = re.compile(r"\| (\d+) of (\d+) hands played")


def run(args, opp, seed):
    if not args.legs:
        return run_engine(args, opp, seed, None)
    legs = [run_engine(args, opp, seed, leg) for leg in (1, 2)]
    return {"net": sum(r["net"] for r in legs), "time": max(r["time"] for r in legs),
            "notices": sum(r["notices"] for r in legs), "forfeit": any(r["forfeit"] for r in legs),
            "hands": sum(r["hands"] for r in legs), "out": "".join(r["out"] for r in legs)}


def run_engine(args, opp, seed, leg):
    log_dir = ""
    if args.log_root:
        name = f"{os.path.splitext(os.path.basename(opp))[0]}_{seed}"
        log_dir = os.path.join(args.log_root, name, f"leg{leg}") if leg else os.path.join(args.log_root, name)
    cmd = [args.python, ENGINE, args.bot_a, opp, "--python", args.python,
           "--stage", str(args.stage), "--seed", str(seed), "--log-dir", log_dir]
    if leg:
        cmd += ["--leg", str(leg)]
    if args.hands:
        cmd += ["--hands", str(args.hands)]
    if args.no_time_limits:
        cmd.append("--no-time-limits")
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = {m.group(1): m.groups()[1:] for m in NET.finditer(out)}
    a = rows.get("A", ("0", "0", "0"))
    played = PLAYED.search(out)
    return {"net": int(a[0]), "time": float(a[1]), "notices": int(a[2]),
            "forfeit": "forfeit" in out, "hands": int(played.group(1)) if played else 0, "out": out}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("bot_a")
    p.add_argument("opponents", nargs="+")
    p.add_argument("--matches", type=int, default=8)
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--stage", type=int, default=1)
    p.add_argument("--legs", action=argparse.BooleanOptionalAction, default=True,
                   help="play each match as two legs with fresh processes (Rulebook 7.1); --no-legs is the old single-run format")
    p.add_argument("--hands", type=int)
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--no-time-limits", action="store_true")
    p.add_argument("--log-root", help="keep each match's logs under this folder")
    p.add_argument("--python", default=VENV_PY if os.path.exists(VENV_PY) else sys.executable)
    args = p.parse_args()
    args.bot_a = os.path.abspath(args.bot_a)
    opps = [os.path.abspath(o) for o in args.opponents]

    jobs = [(o, s) for o in opps for s in range(args.seed, args.seed + args.matches)]
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda j: run(args, *j), jobs))

    print(f"{os.path.relpath(args.bot_a)}  ({args.matches} matches per opponent)")
    total_w = total_n = 0
    for opp in opps:
        rs = [r for (o, _), r in zip(jobs, results) if o == opp]
        for r in rs:
            if r["forfeit"]:
                print(r["out"])
        nets = [r["net"] for r in rs]
        se = stdev(nets) / len(nets) ** 0.5 if len(nets) > 1 else 0.0
        hands = sum(r["hands"] for r in rs) or 1
        wins, draws = sum(n > 0 for n in nets), sum(n == 0 for n in nets)
        total_w += wins + 0.5 * draws
        total_n += len(nets)
        print(f"  vs {os.path.basename(opp):<20} mean {mean(nets):+8.1f} ± {se:6.1f}  "
              f"({sum(nets) / hands:+6.2f}/hand)  W/D/L {wins}/{draws}/{len(nets) - wins - draws}  "
              f"forfeits {sum(r['forfeit'] for r in rs)}  max time {max(r['time'] for r in rs):5.1f} s  "
              f"notices {sum(r['notices'] for r in rs)}")
    print(f"  match points {total_w:g}/{total_n}")


if __name__ == "__main__":
    main()
