"""Sparring opponent: the CFR strategy embedded in bot_v4, played on its own.

This is the method of MIT 2017's winner rebuilt for this game: a near-equilibrium
strategy from Monte Carlo CFR on a card and bet abstraction (see the CFR section
of bot.py and tools/cfr_train.py). No exploit mode and no match lock: it doesn't
adapt, so losing chips to it means a real leak. When a hand leaves its abstract
tree, bot_v4's EV engine decides, as in bot.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_v4 as base  # noqa: E402


class Bot(base.Bot):
    def __init__(self):
        super().__init__()
        self.mode = "cfr"

    def _choose_mode(self):
        pass

    def _lead_is_safe(self):
        return False


if __name__ == "__main__":
    base.Bot = Bot
    base.main()
