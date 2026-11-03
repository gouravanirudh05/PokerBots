"""Sparring opponent: rule-based tight-aggressive play using the engine's hand evaluator."""
import json
import os
import random
import sys
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import RANK_VALUE, best_hand  # noqa: E402


def preflop_score(cards):
    vals = sorted((RANK_VALUE[c[0]] for c in cards), reverse=True)
    score = vals[0] + 0.6 * vals[1] + 0.3 * vals[2]
    if len(set(vals)) < 3:
        score += 10 + max(v for v in vals if vals.count(v) > 1) * 0.5
    if len({c[1] for c in cards}) < 3:
        score += 2
    return score


def best_keep(hole, board):
    return max(combinations(hole, 2), key=lambda k: best_hand(k, board[:3]))


def made_strength(hole, board):
    """0 nothing, 1 weak pair, 2 good pair, 3 two pair+, 4 straight+."""
    keep = best_keep(hole, board) if len(hole) == 3 else hole
    cat = best_hand(keep, board)[0]
    board_cat = best_hand([], board)[0] if len(board) >= 5 else 0
    if cat >= 4:
        return 4
    if cat >= 2 and cat > board_cat:
        return 3
    if cat == 1:
        pair = best_hand(keep, board)[1]
        top = max(RANK_VALUE[c[0]] for c in board)
        return 2 if pair >= top else 1
    return 0


def raise_to(req, frac):
    target = req["opp_bet"] + int(frac * (req["pot"] + req["to_call"]))
    return {"type": "action", "action": "raise",
            "amount": max(req["min_raise"], min(req["max_raise"], target))}


def choose_action(req, hole):
    legal = req["legal_actions"]
    to_call = req["to_call"]
    if req["street"] == "preflop":
        s = preflop_score(hole)
        if "raise" in legal and s >= 30 and req["opp_bet"] <= 20:
            return raise_to(req, 1.0)
        if to_call == 0:
            return {"type": "action", "action": "check"}
        if s >= 26 or (s >= 21 and to_call <= 4):
            return {"type": "action", "action": "call"}
        return {"type": "action", "action": "fold"}
    st = made_strength(hole, req["board"])
    if to_call == 0:
        if "raise" in legal and (st >= 2 or random.random() < 0.15):
            return raise_to(req, 0.66)
        return {"type": "action", "action": "check"}
    if "raise" in legal and st >= 3:
        return raise_to(req, 0.8)
    if st >= 2 or (st == 1 and to_call <= 0.4 * req["pot"]):
        return {"type": "action", "action": "call"}
    return {"type": "action", "action": "fold"}


def main():
    hole = []
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "new_hand":
            hole = msg["hole_cards"]
        elif t == "discard_result":
            hole = msg["hole_cards"]
        elif t == "action_request":
            print(json.dumps(choose_action(msg, hole)), flush=True)
        elif t == "discard_request":
            keep = best_keep(msg["hole_cards"], msg["board"])
            card = next(c for c in msg["hole_cards"] if c not in keep)
            print(json.dumps({"type": "discard", "card": card}), flush=True)
        elif t == "match_end":
            break


if __name__ == "__main__":
    main()
