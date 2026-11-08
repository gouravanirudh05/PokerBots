"""Sparring opponent: tag_bot's decisions, but every bet and raise is the minimum legal size."""
import tag_bot

tag_bot.raise_to = lambda req, frac: {"type": "action", "action": "raise", "amount": req["min_raise"]}

if __name__ == "__main__":
    tag_bot.main()
