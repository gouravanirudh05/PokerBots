"""Sparring opponent: loose-aggressive barreler. Raises most hands preflop, bets whenever
checked to, and only gives up to raises without a made hand. Tests our bluff-catching."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import best_hand  # noqa: E402


def raise_to(req, frac):
    target = req["opp_bet"] + int(frac * (req["pot"] + req["to_call"]))
    return {"type": "action", "action": "raise", "amount": max(req["min_raise"], min(req["max_raise"], target))}


def act(name):
    return {"type": "action", "action": name}


def choose_action(req, hole):
    legal, to_call = req["legal_actions"], req["to_call"]
    if req["street"] == "preflop":
        if "raise" in legal and req["opp_bet"] <= 6 and random.random() < 0.8:
            return raise_to(req, 1.0)
        return act("check") if to_call == 0 else act("call" if to_call <= 30 else "fold")
    cards = hole if len(hole) == 2 else hole[:2]
    cat = best_hand(cards, req["board"])[0]
    if to_call == 0:
        return raise_to(req, random.choice((0.66, 1.0))) if "raise" in legal and random.random() < 0.85 else act("check")
    if "raise" in legal and cat >= 2 and random.random() < 0.5:
        return raise_to(req, 1.0)
    if cat >= 1 or to_call <= 0.35 * req["pot"]:
        return act("call")
    return act("fold")


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
            board = msg["board"]
            h = msg["hole_cards"]
            drop = max(h, key=lambda c: best_hand([x for x in h if x != c], board))
            print(json.dumps({"type": "discard", "card": drop}), flush=True)
        elif t == "match_end":
            break


if __name__ == "__main__":
    main()
