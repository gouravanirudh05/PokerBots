"""Sparring opponent: hyper-aggressive. Raises big or shoves often, rarely folds."""
import json
import random
import sys


def choose_action(req):
    legal = req["legal_actions"]
    roll = random.random()
    if "raise" in legal and roll < 0.55:
        if roll < 0.12:
            amount = req["max_raise"]
        else:
            amount = req["opp_bet"] + int(random.uniform(0.7, 1.5) * (req["pot"] + req["to_call"]))
        amount = max(req["min_raise"], min(req["max_raise"], amount))
        return {"type": "action", "action": "raise", "amount": amount}
    if "check" in legal:
        return {"type": "action", "action": "check"}
    if roll < 0.9:
        return {"type": "action", "action": "call"}
    return {"type": "action", "action": "fold"}


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "action_request":
            print(json.dumps(choose_action(msg)), flush=True)
        elif t == "discard_request":
            cards = sorted(msg["hole_cards"], key=lambda c: "23456789TJQKA".index(c[0]))
            print(json.dumps({"type": "discard", "card": cards[0]}), flush=True)
        elif t == "match_end":
            break


if __name__ == "__main__":
    main()
