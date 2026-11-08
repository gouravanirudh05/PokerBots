"""Sparring opponent: the classic Monte Carlo equity bot.

Equity against a uniformly random opponent hand, compared with pot odds. No
opponent modelling. This is what a competent but simple student bot looks like.
"""
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_v1 as ev  # noqa: E402  (evaluator, preflop table and heuristic keeps)

N = 600


def equity(hole, board, dead):
    hole = [ev.CARD_INDEX[c] for c in hole]
    board = [ev.CARD_INDEX[c] for c in board]
    dead = {ev.CARD_INDEX[c] for c in dead if c}
    n_opp = 3 if len(hole) == 3 else 2
    s = ev.deal(set(hole) | set(board) | dead, N, n_opp + 5 - len(board))
    opp, full = s[:, :n_opp], np.concatenate([np.broadcast_to(board, (N, len(board))), s[:, n_opp:]], 1)
    flop = full[:, :3]
    if n_opp == 3:
        d, _ = ev.heuristic_keeps(opp, flop)
        opp = np.take_along_axis(opp, ev.KEEP_IDX[d], axis=1)
    ov = ev.evaluate(np.concatenate([opp, full], 1))
    best = 0.0
    for keep in (ev.KEEP_IDX if len(hole) == 3 else [np.array([0, 1])]):
        mine = np.broadcast_to(np.array(hole)[keep], (N, 2))
        best = max(best, float(ev.showdown(ev.evaluate(np.concatenate([mine, full], 1)), ov).mean()))
    return best


def raise_to(req, frac):
    target = req["opp_bet"] + int(frac * (req["pot"] + req["to_call"]))
    return {"type": "action", "action": "raise", "amount": max(req["min_raise"], min(req["max_raise"], target))}


def act(name, **kw):
    return dict({"type": "action", "action": name}, **kw)


def choose_action(req, hole, dead):
    legal, to_call, pot = req["legal_actions"], req["to_call"], req["pot"]
    if req["street"] == "preflop":
        e = ev.pre_lookup([ev.CARD_INDEX[c] for c in hole])[1]
    else:
        e = equity(hole, req["board"], dead)
    if "raise" in legal and e > 0.72 and random.random() < 0.8:
        return raise_to(req, 0.75)
    if to_call == 0:
        if "raise" in legal and e > 0.6:
            return raise_to(req, 0.5)
        return act("check")
    if e > to_call / (pot + to_call) + 0.05:
        return act("call")
    return act("fold")


def main():
    hole, dead = [], []
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "new_hand":
            hole, dead = msg["hole_cards"], []
        elif t == "discard_result":
            hole, dead = msg["hole_cards"], [msg["my_discard"], msg["opp_discard"]]
        elif t == "action_request":
            print(json.dumps(choose_action(msg, hole, dead)), flush=True)
        elif t == "discard_request":
            h = [ev.CARD_INDEX[c] for c in msg["hole_cards"]]
            f = [ev.CARD_INDEX[c] for c in msg["board"]]
            d, _ = ev.heuristic_keeps(np.array([h]), np.array([f]))
            print(json.dumps({"type": "discard", "card": msg["hole_cards"][int(d[0])]}), flush=True)
        elif t == "match_end":
            break


if __name__ == "__main__":
    main()
