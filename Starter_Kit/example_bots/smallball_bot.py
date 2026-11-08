"""Sparring opponent: loose small-ball. Limps nearly everything, bets a quarter pot with any pair
or better, and calls up to half the pot with it."""
import random

import tag_bot


def quarter(req):
    target = req["opp_bet"] + int(0.25 * (req["pot"] + req["to_call"]))
    return {"type": "action", "action": "raise", "amount": max(req["min_raise"], min(req["max_raise"], target))}


def choose_action(req, hole):
    legal, to_call, pot = req["legal_actions"], req["to_call"], req["pot"]
    if req["street"] == "preflop":
        if to_call == 0:
            return {"type": "action", "action": "check"}
        keep = tag_bot.preflop_score(hole) >= 16 or to_call <= 1
        return {"type": "action", "action": "call" if keep and to_call <= 12 else "fold"}
    st = tag_bot.made_strength(hole, req["board"])
    if to_call == 0:
        if "raise" in legal and (st >= 1 or random.random() < 0.2):
            return quarter(req)
        return {"type": "action", "action": "check"}
    if "raise" in legal and st >= 3:
        return quarter(req)
    return {"type": "action", "action": "call" if st >= 1 and to_call <= 0.5 * pot else "fold"}


tag_bot.choose_action = choose_action

if __name__ == "__main__":
    tag_bot.main()
