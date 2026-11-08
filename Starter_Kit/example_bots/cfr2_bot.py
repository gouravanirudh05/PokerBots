"""Sparring opponent: blueprint v2 (a finer, independently trained abstraction: 1755 preflop
classes, 144/144/120 buckets, 2.7B MCCFR iterations), played on its own in CFR mode. It differs
from bot.py's v1 blueprint, so it checks for overfitting to our own strategy."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfr2_base as base  # noqa: E402


class Bot(base.Bot):
    def __init__(self):
        super().__init__()
        self.mode = "cfr"

    def _choose_mode(self):
        pass


if __name__ == "__main__":
    base.Bot = Bot
    base.main()
