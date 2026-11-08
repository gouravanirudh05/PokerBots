"""Sparring opponent: polarized overbets. Postflop it bets 3 times the pot with strong hands and
30% of its air, checks the rest, and folds weak hands to bets. Preflop plays like tag_bot."""
import random

import tag_bot

base = tag_bot.choose_action


def big(req):
    target = req["opp_bet"] + 3 * (req["pot"] + req["to_call"])
    return {"type": "action", "action": "raise", "amount": max(req["min_raise"], min(req["max_raise"], target))}


def choose_action(req, hole):
    if req["street"] == "preflop":
        return base(req, hole)
    legal, to_call = req["legal_actions"], req["to_call"]
    st = tag_bot.made_strength(hole, req["board"])
    if to_call == 0:
        if "raise" in legal and (st >= 3 or random.random() < 0.3):
            return big(req)
        return {"type": "action", "action": "check"}
    if "raise" in legal and st >= 3:
        return big(req)
    return {"type": "action", "action": "call" if st >= 2 else "fold"}


tag_bot.choose_action = choose_action

if __name__ == "__main__":
    tag_bot.main()
