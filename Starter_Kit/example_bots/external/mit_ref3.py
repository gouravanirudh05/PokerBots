"""Port of MIT Pokerbots 2026 reference bot 3 ("monte carlo"),
github.com/mitpokerbots/reference-3-2026.

Reference 2's betting, with a 1000-sample Monte Carlo discard. MIT's version puts
the discard on the board; here discards leave play, so it keeps the pair with the
most equity against a random hand.
"""
from _common import C, equity, run
from mit_ref2 import Bot as Ref2


class Bot(Ref2):
    def choose_discard(self, req):
        hole = [C[c] for c in req["hole_cards"]]
        return equity(hole, self.board(req)[:3], n=1000)[1]


if __name__ == "__main__":
    run(Bot())
