#!/usr/bin/env python3
"""
Offline evaluation of exploit-to-CFR switch rules on real exploit-mode leg logs.

    python3.11 tools/switch_sim.py LOG_ROOT HANDS_PER_LEG opp=cfr_rate [opp=cfr_rate ...]

LOG_ROOT holds OPP_SEED/leg{1,2}/match.log from `arena.py --legs --log-root`, played in exploit
mode. For each leg the hand-by-hand nets are replayed to find where a rule would switch, and the
rest of the leg is credited at the measured CFR-mode rate against that opponent.
"""

import glob
import os
import re
import sys
from statistics import mean


def nets(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.search(r"\bA ([+-]\d+)", line.split("|")[-1])
        if line.startswith("#") and m:
            out.append(int(m.group(1)))
    return out


def switch_at(xs, first, every, rate):
    total = 0
    for h, x in enumerate(xs, 1):
        total += x
        if h >= first and (h - first) % every == 0 and h < len(xs) and total < rate * h:
            return h
    return None


def main():
    root, hands = sys.argv[1], int(sys.argv[2])
    opps = dict(a.split("=") for a in sys.argv[3:])
    data = {}
    for opp, rate in opps.items():
        legs = [nets(p) for p in glob.glob(os.path.join(root, f"{opp}_*", "leg*", "match.log"))]
        data[opp] = ([x for x in legs if len(x) == hands], float(rate))
    print({k: len(v[0]) for k, v in data.items()}, "legs")
    firsts = (80, 120, 160, 200, 280) if hands >= 500 else (80, 120, 160)
    rules = [("never", None)] + [((f, 40, r), (f, 40, r)) for f in firsts for r in (-2.0, -1.0, 0.0, 0.5, 1.0)]
    for name, rule in rules:
        cells = []
        for opp, (legs, rate) in data.items():
            totals, switched = [], 0
            for xs in legs:
                h = None if rule is None else switch_at(xs, *rule)
                switched += h is not None
                totals.append(sum(xs) if h is None else sum(xs[:h]) + rate * (len(xs) - h))
            cells.append(f"{opp[:8]} {mean(totals) / hands:+6.2f} ({switched / len(legs):4.0%})")
        print(f"{str(name):<16}" + "  ".join(cells))


if __name__ == "__main__":
    main()
