#!/usr/bin/env python3
"""
Chips by the river betting line of bot A, from match.log files.

    python3.11 tools/river_lines.py LOG_ROOT [LOG_ROOT ...]

Hands that reached the river are grouped by their river actions in order (x check, c call,
f fold, r raise with s/m/l/o = small, medium, large, over-pot size), with the outcome.
"""
import os
import re
import sys
from collections import defaultdict

TOKEN = re.compile(r"^([AB])([xcfr])(\d*)$")


def street_tokens(line, street):
    m = re.search(rf"\b{street}: ([^|]*?)(?= (?:flop|turn|river):| \|)", line)
    return m.group(1).split() if m else []


def street_total(tokens):
    return max([int(t[2:]) for t in tokens if len(t) > 2] + [0])


def main():
    rows = defaultdict(lambda: [0, 0, 0])
    for root in sys.argv[1:]:
        for dirpath, _, files in os.walk(root, followlinks=True):
            if "match.log" not in files:
                continue
            for line in open(os.path.join(dirpath, "match.log"), encoding="utf-8"):
                if not line.startswith("#") or " river: " not in line:
                    continue
                m = re.search(r"\bA ([+-]\d+)", line.split("|")[-1])
                if not m:
                    continue
                net = int(m.group(1))
                pot = 2 * sum(max(street_total(street_tokens(line, s)), 2 if s == "preflop" else 0)
                              for s in ("preflop", "flop", "turn"))
                seq = []
                for tok in street_tokens(line, "river"):
                    who, act, amount = TOKEN.match(tok).groups()
                    if act == "r":
                        frac = int(amount) / pot
                        act += "s" if frac < 0.45 else "m" if frac < 0.85 else "l" if frac < 1.3 else "o"
                    seq.append(who + act)
                r = rows[(" ".join(seq), "showdown" if "showdown" in line else "fold")]
                r[0] += 1
                r[1] += net
                r[2] += net > 0
    total = sum(r[1] for r in rows.values())
    print(f"river hands {sum(r[0] for r in rows.values())}, net {total:+d}")
    for (k, end), (n, net, won) in sorted(rows.items(), key=lambda kv: kv[1][1]):
        print(f"  {k:<22}{end:<9}{n:7d} hands  net {net:+8d}  ({net / n:+7.2f}/hand)  A ahead {won / n:4.0%}")


if __name__ == "__main__":
    main()
