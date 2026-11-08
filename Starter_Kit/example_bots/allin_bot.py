"""Sparring opponent: shoves every hand preflop. A classic pokerbots baseline that punishes timid callers."""
import json
import sys


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "action_request":
            legal = msg["legal_actions"]
            if "raise" in legal:
                reply = {"type": "action", "action": "raise", "amount": msg["max_raise"]}
            else:
                reply = {"type": "action", "action": "call" if "call" in legal else "check"}
            print(json.dumps(reply), flush=True)
        elif t == "discard_request":
            cards = sorted(msg["hole_cards"], key=lambda c: "23456789TJQKA".index(c[0]))
            print(json.dumps({"type": "discard", "card": cards[0]}), flush=True)
        elif t == "match_end":
            break


if __name__ == "__main__":
    main()
