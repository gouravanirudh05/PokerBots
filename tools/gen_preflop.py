#!/usr/bin/env python3
"""
Generate the preflop table embedded in Starter_Kit/bot.py.

For every 3-card starting hand (computed once per suit-isomorphism class) this
estimates, by Monte Carlo, the all-in equity against a random hand and against
the top 50%, 25% and 12% of hands, with both players discarding after the flop
by the bot's heuristic keep rule. It also stores each hand's percentile by
equity against a random hand. The result is written between the PREFLOP DATA
markers in bot.py.

    python3.11 tools/gen_preflop.py [--samples 6000] [--workers 14]
"""

import argparse
import base64
import os
import re
import sys
from itertools import combinations, permutations
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BOT_PATH = os.path.join(HERE, "..", "Starter_Kit", "bot.py")
sys.path.insert(0, os.path.dirname(BOT_PATH))
import bot  # noqa: E402

COMBOS = np.array(list(combinations(range(52), 3)))
SUIT_PERMS = list(permutations(range(4)))


def canonical(hand):
    return min(tuple(sorted((c & ~3) | perm[c & 3] for c in hand)) for perm in SUIT_PERMS)


def equity(hand, opp_pool, n, rng):
    """All-in equity of `hand` against hands drawn uniformly from `opp_pool` (rows of COMBOS)."""
    ok = ~np.isin(opp_pool, hand).any(axis=1)
    pool = opp_pool[ok]
    opp3 = pool[rng.integers(0, len(pool), n)]
    keys = rng.random((n, 52))
    keys[:, list(hand)] = 2.0
    keys[np.arange(n)[:, None], opp3] = 2.0
    board = np.argsort(keys, axis=1)[:, :5]
    flop = board[:, :3]
    mine = np.broadcast_to(np.array(hand), (n, 3))
    my_disc, _ = bot.heuristic_keeps(mine, flop)
    opp_disc, _ = bot.heuristic_keeps(opp3, flop)
    my_keep = np.take_along_axis(mine, bot.KEEP_IDX[my_disc], axis=1)
    opp_keep = np.take_along_axis(opp3, bot.KEEP_IDX[opp_disc], axis=1)
    mv = bot.evaluate(np.concatenate([my_keep, board], axis=1))
    ov = bot.evaluate(np.concatenate([opp_keep, board], axis=1))
    return float(bot.showdown(mv, ov).mean())


def _init(seed):
    bot.RNG = np.random.default_rng(seed + os.getpid())


def _job(args):
    hand, pools, n = args
    rng = np.random.default_rng(abs(hash(hand)) % (2 ** 32) + os.getpid())
    return [equity(hand, pool, n, rng) for pool in pools]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=6000)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = p.parse_args()

    class_of = [canonical(tuple(int(c) for c in h)) for h in COMBOS]
    reps, rep_index = {}, np.zeros(len(COMBOS), dtype=np.int64)
    for i, key in enumerate(class_of):
        rep_index[i] = reps.setdefault(key, len(reps))
    rep_hands = [None] * len(reps)
    for i, key in enumerate(class_of):
        if rep_hands[reps[key]] is None:
            rep_hands[reps[key]] = tuple(int(c) for c in COMBOS[i])
    print(f"{len(COMBOS)} hands in {len(rep_hands)} classes", flush=True)

    with Pool(args.workers, initializer=_init, initargs=(1,)) as pool:
        e_rand = np.array(pool.map(_job, [(h, [COMBOS], args.samples) for h in rep_hands]))[:, 0]
        all_eq = e_rand[rep_index]
        pct = (np.argsort(np.argsort(all_eq, kind="stable"), kind="stable") + 0.5) / len(all_eq)
        print("pass 1 done", flush=True)
        pools = [COMBOS[pct >= 1 - w] for w in bot.PRE_WIDTHS[1:]]
        ranged = np.array(pool.map(_job, [(h, pools, args.samples) for h in rep_hands]))
        print("pass 2 done", flush=True)

    cols = np.vstack([pct, all_eq] + [ranged[:, j][rep_index] for j in range(ranged.shape[1])])
    data = np.clip(np.round(cols * 255), 0, 255).astype(np.uint8)
    encoded = base64.b64encode(data.tobytes()).decode()

    with open(BOT_PATH, encoding="utf-8") as f:
        src = f.read()
    src, count = re.subn(r'^PREFLOP_DATA = ".*"$', f'PREFLOP_DATA = "{encoded}"', src, flags=re.M)
    if count != 1:
        sys.exit("PREFLOP_DATA line not found in bot.py")
    with open(BOT_PATH, "w", encoding="utf-8") as f:
        f.write(src)

    order = np.argsort(-all_eq)
    names = lambda i: " ".join(bot.CARD_NAME[c] for c in COMBOS[i])
    print("best:", [(names(i), round(all_eq[i], 3)) for i in order[:5]])
    print("worst:", [(names(i), round(all_eq[i], 3)) for i in order[-5:]])
    print(f"wrote {len(encoded)} base64 chars to {BOT_PATH}")


if __name__ == "__main__":
    main()
