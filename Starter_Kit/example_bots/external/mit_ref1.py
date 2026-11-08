"""Port of MIT Pokerbots 2026 reference bot 1 ("toss smallest"),
github.com/mitpokerbots/reference-1-2026. Same variant family as ours.

Discards its lowest-ranked card. Min-raises half the time when it can, otherwise
checks; facing a bet it folds a quarter of the time and calls the rest.
"""
from _common import PortBot, RANKS, random, run


class Bot(PortBot):
    strong = None  # reference 2/3: raise 10x min with all-broadway hands

    def choose_discard(self, req):
        ranks = [RANKS.index(c[0]) for c in req["hole_cards"]]
        return ranks.index(min(ranks))

    def act(self, req):
        legal = req["legal_actions"]
        if "raise" in legal:
            if self.strong and all(c[0] in self.strong for c in self.card_names()):
                return self.raise_to(req, min(req["min_raise"] * 10, req["max_raise"]))
            if random.random() < 0.5:
                return self.raise_to(req, req["min_raise"])
        if "check" in legal:
            return {"type": "action", "action": "check"}
        if random.random() < 0.25:
            return {"type": "action", "action": "fold"}
        return {"type": "action", "action": "call"}

    def card_names(self):
        return [RANKS[c >> 2] + "shdc"[c & 3] for c in self.hole]


if __name__ == "__main__":
    run(Bot())
