#!/usr/bin/env python3
"""
Break down where bot A wins and loses chips, from match.log files written by the engine.

    python3.11 tools/leaks.py LOG_ROOT [LOG_ROOT ...]

Each LOG_ROOT is searched recursively for match.log. Hands are grouped by the
street the hand ended on and how it ended (A folded, B folded, showdown won /
lost / split), and by A's seat. Prints hand counts and A's total net per group.
"""

import os
import re
import sys
from collections import defaultdict

LINE = re.compile(r"^#\d+\s+button (\w) \|.*\| (preflop:.*) \| (fold|showdown)[^|]*$")


def main():
    for root in sys.argv[1:]:
        groups = defaultdict(lambda: [0, 0])
        hands = total = 0
        for dirpath, _, files in os.walk(root, followlinks=True):
            if "match.log" not in files:
                continue
            for line in open(os.path.join(dirpath, "match.log"), encoding="utf-8"):
                m = LINE.match(line)
                if not m:
                    continue
                button, actions, result = m.group(1), m.group(2), m.group(3)
                net = int(re.search(r"\bA ([+-]\d+)", line.split("|")[-1]).group(1))
                streets = re.findall(r"(preflop|flop|turn|river):", actions)
                last = streets[-1] if streets else "preflop"
                if result == "fold":
                    folder = "A" if re.search(r"Af$", actions.strip()) else "B"
                    how = f"{folder} folds"
                else:
                    how = "showdown " + ("won" if net > 0 else "lost" if net < 0 else "split")
                seat = "A button" if button == "A" else "A big blind"
                for key in ((last, how), ("seat", seat)):
                    groups[key][0] += 1
                    groups[key][1] += net
                hands += 1
                total += net
        print(f"{root}: {hands} hands, A net {total:+d} ({total / max(hands, 1):+.2f}/hand)")
        for key in sorted(groups, key=lambda k: (k[0] == "seat", k)):
            n, s = groups[key]
            print(f"  {key[0]:<8} {key[1]:<16} {n:6d} hands  net {s:+8d}  ({s / n:+7.2f}/hand)")


if __name__ == "__main__":
    main()
