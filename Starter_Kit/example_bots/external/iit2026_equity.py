"""Port of an IIT Pokerbots 2026 (Jane Street) entry: kartikya2207's submitted bot,
github.com/kartikya2207/poker__bot_engine_kartikya (bot_final.py).

Equity-driven heuristic play: a 169-class preflop equity table with raise/call/fold
thresholds; postflop 60-sample Monte Carlo equity against a random hand; facing a
bet it raises all-in or folds (never calls, from its author's log analysis); not
facing a bet it value-bets 80% / 50% pot. Its game had 10/20 blinds and 5000-chip
stacks, so chip constants are scaled to 1/2 and 200. Its sneak-peek auction has no
counterpart here. With 3 cards it rates a hand by its best 2-card subset preflop
and its best keep on the flop, and discards to keep the most equity.
"""
from _common import BIG_BLIND, RANKS, C, PortBot, equity, run

SCALE = 20 / BIG_BLIND  # its big blind was 20

PF = {
    'AA': 0.852, 'KK': 0.827, 'QQ': 0.794, 'JJ': 0.772, 'TT': 0.744, '99': 0.717,
    '88': 0.698, '77': 0.668, '66': 0.643, '55': 0.616, '44': 0.568, '33': 0.547, '22': 0.498,
    'AKs': 0.684, 'AQs': 0.649, 'AJs': 0.647, 'ATs': 0.645, 'A9s': 0.646, 'A8s': 0.632,
    'A7s': 0.603, 'A6s': 0.600, 'A5s': 0.607, 'A4s': 0.583, 'A3s': 0.573, 'A2s': 0.567,
    'AKo': 0.648, 'AQo': 0.636, 'AJo': 0.643, 'ATo': 0.615, 'A9o': 0.602, 'A8o': 0.616,
    'A7o': 0.589, 'A6o': 0.559, 'A5o': 0.583, 'A4o': 0.578, 'A3o': 0.555, 'A2o': 0.538,
    'KQs': 0.622, 'KJs': 0.630, 'KTs': 0.625, 'K9s': 0.616, 'K8s': 0.598, 'K7s': 0.565,
    'K6s': 0.571, 'K5s': 0.561, 'K4s': 0.541, 'K3s': 0.544, 'K2s': 0.513,
    'KQo': 0.605, 'KJo': 0.604, 'KTo': 0.586, 'K9o': 0.565, 'K8o': 0.562, 'K7o': 0.557,
    'K6o': 0.526, 'K5o': 0.537, 'K4o': 0.521, 'K3o': 0.515, 'K2o': 0.516,
    'QJs': 0.608, 'QTs': 0.574, 'Q9s': 0.581, 'Q8s': 0.557, 'Q7s': 0.532, 'Q6s': 0.534,
    'Q5s': 0.522, 'Q4s': 0.506, 'Q3s': 0.509, 'Q2s': 0.503,
    'QJo': 0.573, 'QTo': 0.573, 'Q9o': 0.562, 'Q8o': 0.541, 'Q7o': 0.503, 'Q6o': 0.503,
    'Q5o': 0.493, 'Q4o': 0.498, 'Q3o': 0.492, 'Q2o': 0.479,
    'JTs': 0.573, 'J9s': 0.535, 'J8s': 0.557, 'J7s': 0.516, 'J6s': 0.521, 'J5s': 0.497,
    'J4s': 0.485, 'J3s': 0.490, 'J2s': 0.470,
    'JTo': 0.545, 'J9o': 0.524, 'J8o': 0.514, 'J7o': 0.496, 'J6o': 0.481, 'J5o': 0.452,
    'J4o': 0.464, 'J3o': 0.444, 'J2o': 0.439,
    'T9s': 0.522, 'T8s': 0.516, 'T7s': 0.493, 'T6s': 0.483, 'T5s': 0.460, 'T4s': 0.468,
    'T3s': 0.468, 'T2s': 0.438, 'T9o': 0.510, 'T8o': 0.487, 'T7o': 0.492, 'T6o': 0.443,
    'T5o': 0.443, 'T4o': 0.449, 'T3o': 0.428, 'T2o': 0.414,
    '98s': 0.509, '97s': 0.466, '96s': 0.477, '95s': 0.464, '94s': 0.425, '93s': 0.439, '92s': 0.407,
    '98o': 0.471, '97o': 0.460, '96o': 0.443, '95o': 0.422, '94o': 0.411, '93o': 0.402, '92o': 0.392,
    '87s': 0.470, '86s': 0.472, '85s': 0.450, '84s': 0.420, '83s': 0.415, '82s': 0.411,
    '87o': 0.437, '86o': 0.427, '85o': 0.410, '84o': 0.393, '83o': 0.371, '82o': 0.368,
    '76s': 0.468, '75s': 0.454, '74s': 0.409, '73s': 0.375, '72s': 0.376,
    '76o': 0.413, '75o': 0.396, '74o': 0.378, '73o': 0.384, '72o': 0.350,
    '65s': 0.440, '64s': 0.415, '63s': 0.412, '62s': 0.386,
    '65o': 0.398, '64o': 0.379, '63o': 0.358, '62o': 0.356,
    '54s': 0.407, '53s': 0.389, '52s': 0.392, '54o': 0.376, '53o': 0.360, '52o': 0.345,
    '43s': 0.390, '42s': 0.378, '43o': 0.364, '42o': 0.333, '32s': 0.360, '32o': 0.325,
}


def pair_equity(a, b):
    r1, r2, s1, s2 = a >> 2, b >> 2, a & 3, b & 3
    if r1 < r2:
        r1, r2, s1, s2 = r2, r1, s2, s1
    key = RANKS[r1] + RANKS[r2]
    if r1 != r2:
        key += "s" if s1 == s2 else "o"
    return PF.get(key, 0.45)


class Bot(PortBot):
    def new_hand(self, msg):
        h = self.hole
        self.pf_eq = max(pair_equity(h[i], h[j]) for i, j in ((0, 1), (0, 2), (1, 2)))
        self.eq_cache = {}

    def equity(self, req):
        street = req["street"]
        if street not in self.eq_cache:
            self.eq_cache[street] = equity(self.hole, self.board(req), self.dead(), n=60)[0]
        return self.eq_cache[street]

    def choose_discard(self, req):
        hole = [C[c] for c in req["hole_cards"]]
        return equity(hole, self.board(req)[:3], n=60)[1]

    def act(self, req):
        return self.preflop(req) if req["street"] == "preflop" else self.postflop(req)

    def preflop(self, req):
        eq, ctc = self.pf_eq, req["to_call"]
        pot = max(req["pot"], 40 / SCALE)
        legal = req["legal_actions"]
        facing_raise = ctc > 20 / SCALE

        def raise_to(mult):
            return self.raise_to(req, pot * mult)

        def shove():
            return self.raise_to(req, req["max_raise"]) if "raise" in legal else self.call_or_check(req)

        if facing_raise:
            po = ctc / (pot + ctc)
            raise_size = ctc / (20 / SCALE)
            if eq >= 0.68:
                return shove() if raise_size > 5 else raise_to(3.0)
            if eq >= 0.58:
                return raise_to(2.5) if raise_size < 3 else self.call_or_check(req)
            if eq >= max(0.44, po + 0.04):
                return self.call_or_check(req)
            return self.fold_or_check(req)
        if not self.button and ctc == 0:
            if eq >= 0.60:
                return raise_to(3.0)
            return {"type": "action", "action": "check"}
        if eq >= 0.62:
            return raise_to(2.5)
        if eq >= 0.44:
            return self.call_or_check(req)
        return self.fold_or_check(req)

    def postflop(self, req):
        eq = self.equity(req)
        pot = max(req["pot"], 40 / SCALE)
        ctc = req["to_call"]
        legal = req["legal_actions"]
        can_raise = "raise" in legal

        def shove():
            return self.raise_to(req, req["max_raise"]) if can_raise else self.call_or_check(req)

        if ctc > 0:  # raise or fold, never call
            po = ctc / (pot + ctc)
            if eq >= 0.65:
                return shove() if can_raise else self.fold_or_check(req)
            if eq >= 0.52 and po < 0.18 and ctc < 60 / SCALE:
                return shove() if can_raise else self.fold_or_check(req)
            return self.fold_or_check(req)
        if not can_raise:
            return {"type": "action", "action": "check"}
        if eq >= 0.65:
            return shove() if req["street"] == "river" else self.raise_to(req, pot * 0.80)
        if eq >= 0.55:
            return self.raise_to(req, pot * 0.50)
        return {"type": "action", "action": "check"}


if __name__ == "__main__":
    run(Bot())
