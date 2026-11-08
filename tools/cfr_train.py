#!/usr/bin/env python3
"""
Train the CFR strategy embedded in Starter_Kit/bot.py.

    python3.11 tools/cfr_train.py deals [--deals 2000000] [--jobs 10]   # card features of a deal pool
    python3.11 tools/cfr_train.py train [--iters 100000000] [--jobs 15]  # MCCFR, resumable; repeat to train more
    python3.11 tools/cfr_train.py pack                                  # embed the strategy in bot.py

The abstraction (betting tree, features, bucket counts) is the CFR section of bot.py.
Work files go to tools/cfr/work/. `deals` resets training; `train` resumes it.
"""

import argparse
import base64
import io
import os
import re
import subprocess
import sys
import zlib
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# --bot PATH trains a candidate abstraction in a copy of bot.py (also the file `pack` embeds into)
BOT_PATH = os.path.join(ROOT, "Starter_Kit", "bot.py")
if "--bot" in sys.argv:
    BOT_PATH = os.path.abspath(sys.argv[sys.argv.index("--bot") + 1])
sys.path.insert(0, os.path.dirname(BOT_PATH))
cb = __import__(os.path.splitext(os.path.basename(BOT_PATH))[0])

CFR_DIR = os.path.join(ROOT, "tools", "cfr")
WORK = os.path.join(CFR_DIR, "work")
if "--work" in sys.argv:
    WORK = os.path.abspath(sys.argv[sys.argv.index("--work") + 1])
SAMPLES = 160
if "--samples" in sys.argv:
    SAMPLES = int(sys.argv[sys.argv.index("--samples") + 1])
CHUNK = max(250, 320_000 // SAMPLES)  # deals per worker task (memory grows with SAMPLES)


def features(seed):
    """Features of CHUNK random deals. Slot 0 is the button; the pool is symmetric anyway."""
    rng = np.random.default_rng(seed)
    cards = np.argpartition(rng.random((CHUNK, 52)), 11, axis=1)[:, :11]
    rows = np.arange(CHUNK)[:, None]
    flop, board = cards[:, 6:9], cards[:, 6:11]
    out = {"pre": [], "flop_eq": [], "flop_hs": [], "turn_eq": [], "turn_hs": [], "river": []}
    kept, discards = [], []
    for slot in (0, 1):
        three = cards[:, 3 * slot:3 * slot + 3]
        out["pre"].append(cb.cfr_pre_bucket(three))
        eq, hs, disc = cb.cfr_flop_features(three, flop, SAMPLES, rng)
        out["flop_eq"].append(eq)
        out["flop_hs"].append(hs)
        kept.append(three[rows, cb.KEEP_IDX[disc]])
        discards.append(three[np.arange(CHUNK), disc])
    dead = np.stack(discards, axis=1)
    values = []
    for slot in (0, 1):
        eq, hs = cb.cfr_turn_features(kept[slot], board[:, :4], dead, SAMPLES, rng)
        out["turn_eq"].append(eq)
        out["turn_hs"].append(hs)
        out["river"].append(cb.cfr_river_strength(kept[slot], board, dead, SAMPLES, rng))
        values.append(cb.evaluate(np.concatenate([kept[slot], board], axis=1)))
    out = {k: np.stack(v, axis=1) for k, v in out.items()}  # (CHUNK, 2)
    out["result"] = np.sign(values[0] - values[1]).astype(np.int8)
    return out


def quantile_edges(x, n):
    return np.quantile(x, np.arange(1, n) / n)


def grid_edges(eq, hs, shape):
    eq_edges = quantile_edges(eq, shape[0])
    bins = np.searchsorted(eq_edges, eq, side="right")
    hs_edges = np.stack([quantile_edges(hs[bins == i], shape[1]) for i in range(shape[0])])
    return eq_edges, hs_edges


def cmd_deals(args):
    os.makedirs(WORK, exist_ok=True)
    n_chunks = args.deals // CHUNK
    with Pool(args.jobs) as pool:
        parts = []
        for i, part in enumerate(pool.imap_unordered(features, range(args.seed, args.seed + n_chunks))):
            parts.append(part)
            if (i + 1) % 50 == 0:
                print(f"{(i + 1) * CHUNK} deals", flush=True)
    f = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}

    edges = {}
    edges["flop_eq"], edges["flop_hs"] = grid_edges(f["flop_eq"].ravel(), f["flop_hs"].ravel(), cb.CFR_GRID[1])
    edges["turn_eq"], edges["turn_hs"] = grid_edges(f["turn_eq"].ravel(), f["turn_hs"].ravel(), cb.CFR_GRID[2])
    edges["river"] = quantile_edges(f["river"].ravel(), cb.CFR_BUCKETS[3])
    np.savez(os.path.join(WORK, "edges.npz"), **edges)

    n = len(f["result"])
    b = np.zeros((n, 2, 4), dtype=np.uint16)
    for slot in (0, 1):
        b[:, slot, 0] = f["pre"][:, slot]
        b[:, slot, 1] = cb.cfr_grid_bucket(f["flop_eq"][:, slot], f["flop_hs"][:, slot], edges["flop_eq"], edges["flop_hs"])
        b[:, slot, 2] = cb.cfr_grid_bucket(f["turn_eq"][:, slot], f["turn_hs"][:, slot], edges["turn_eq"], edges["turn_hs"])
        b[:, slot, 3] = np.searchsorted(edges["river"], f["river"][:, slot], side="right")
    for s in range(4):
        assert b[:, :, s].max() < cb.CFR_BUCKETS[s]
    with open(os.path.join(WORK, "deals.bin"), "wb") as fh:
        fh.write(np.int64(n).tobytes())
        fh.write(b.tobytes())
        fh.write(f["result"].tobytes())

    nodes, children = cb.CfrTree().arrays()
    tree = cb.CfrTree()
    with open(os.path.join(WORK, "tree.bin"), "wb") as fh:
        fh.write(np.array([len(nodes), len(children)], dtype=np.int32).tobytes())
        fh.write(np.int64(tree.size).tobytes())
        fh.write(nodes.tobytes())
        fh.write(children.tobytes())
    state = os.path.join(WORK, "state.bin")
    if os.path.exists(state):
        os.remove(state)  # new buckets: start training over
    print(f"{n} deals, {len(nodes)} tree nodes, {tree.size} strategy entries; "
          f"bucket counts per street: {[len(np.unique(b[:, :, s])) for s in range(4)]}")


def cmd_train(args):
    exe = os.path.join(CFR_DIR, "mccfr")
    src = exe + ".c"
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        subprocess.run(["gcc", "-O3", "-march=native", "-Wall", "-o", exe, src, "-lpthread"], check=True)
    subprocess.run([exe, os.path.join(WORK, "tree.bin"), os.path.join(WORK, "deals.bin"),
                    os.path.join(WORK, "state.bin"), str(args.iters), str(args.jobs), str(args.seed)], check=True)


def cmd_pack(args):
    """Quantize the average strategy to steps of 1/CFR_LEVELS and embed it, with the bucket
    edges, in bot.py's CFR_DATA line."""
    size = cb.CfrTree().size
    strategy = np.fromfile(os.path.join(WORK, "state.bin.strategy"), dtype=np.float32)
    assert strategy.size == size, "strategy does not match bot.py's abstraction"
    buf = io.BytesIO()
    np.savez(buf, strategy=np.round(strategy * cb.CFR_LEVELS).astype(np.uint8),
             **dict(np.load(os.path.join(WORK, "edges.npz"))))
    encoded = base64.b64encode(zlib.compress(buf.getvalue(), 9)).decode()
    with open(BOT_PATH, encoding="utf-8") as f:
        src = f.read()
    src, count = re.subn(r'^CFR_DATA = ".*"$', lambda _: f'CFR_DATA = "{encoded}"', src, flags=re.M)
    if count != 1:
        sys.exit("CFR_DATA line not found in bot.py")
    with open(BOT_PATH, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"embedded {len(encoded) / 1e6:.2f} MB of strategy; bot.py is now {os.path.getsize(BOT_PATH) / 1e6:.2f} MB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["deals", "train", "pack"])
    p.add_argument("--deals", type=int, default=2_000_000)
    p.add_argument("--iters", type=int, default=100_000_000)
    p.add_argument("--jobs", type=int, default=15)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--bot", help="bot.py copy holding the abstraction (default Starter_Kit/bot.py)")
    p.add_argument("--work", help="work folder (default tools/cfr/work)")
    p.add_argument("--samples", type=int, help="Monte Carlo samples per card feature (default 160)")
    args = p.parse_args()
    {"deals": cmd_deals, "train": cmd_train, "pack": cmd_pack}[args.command](args)


if __name__ == "__main__":
    main()
