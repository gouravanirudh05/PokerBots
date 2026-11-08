"""Port of MIT Pokerbots 2026 reference bot 2 ("good cards"),
github.com/mitpokerbots/reference-2-2026.

Reference 1 plus: with every hole card ten or higher, raises to 10x the minimum.
"""
from _common import run
from mit_ref1 import Bot as Ref1


class Bot(Ref1):
    strong = "TJQKA"


if __name__ == "__main__":
    run(Bot())
