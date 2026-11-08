"""Sparring opponent: tag_bot's decisions, but every bet and raise is 2.5 times the pot."""
import tag_bot


def raise_to(req, frac):
    target = req["opp_bet"] + int(2.5 * (req["pot"] + req["to_call"]))
    return {"type": "action", "action": "raise", "amount": max(req["min_raise"], min(req["max_raise"], target))}


tag_bot.raise_to = raise_to

if __name__ == "__main__":
    tag_bot.main()
