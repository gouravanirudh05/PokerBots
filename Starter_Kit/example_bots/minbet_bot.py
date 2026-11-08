"""Sparring opponent: min-bets every street with any hand to probe for cheap folds, calls small
bets, and continues against real bets only with a good made hand."""
import tag_bot


def choose_action(req, hole):
    legal, to_call, pot = req["legal_actions"], req["to_call"], req["pot"]
    cheap = to_call <= max(2, 0.2 * pot)
    if "raise" in legal and (to_call == 0 or (req["street"] == "preflop" and to_call <= 1)):
        return {"type": "action", "action": "raise", "amount": req["min_raise"]}
    if to_call == 0:
        return {"type": "action", "action": "check"}
    if req["street"] == "preflop":
        strong = tag_bot.preflop_score(hole) >= 24
    else:
        strong = tag_bot.made_strength(hole, req["board"]) >= 2
    return {"type": "action", "action": "call" if cheap or strong else "fold"}


tag_bot.choose_action = choose_action

if __name__ == "__main__":
    tag_bot.main()
