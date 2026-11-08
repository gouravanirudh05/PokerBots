"""Port of an MIT Pokerbots 2024 (Auction Hold'em) entry: abh-win's C++ bot,
github.com/abh-win/auction-poker-bot (src/main_bot.cpp, src/opponent_model.cpp).

Exploitative profiling: Beta-smoothed VPIP / PFR / 3-bet / aggression / fold-to-bet
stats classify the opponent as nit, TAG, LAG, calling station or maniac, which
shifts opening ranges, value and bluff thresholds and call margins. Equity is
Monte Carlo against the opponent's range: the top VPIP / PFR / 3-bet share of hands
by preflop strength, with a soft edge, narrowed by each postflop bet or raise
(less for aggressive opponents). Value bets size up on wet boards; bluffs follow
the opponent's fold-to-bet rate. Its third-card auction has no counterpart here.
With 3 cards it uses its best keep's equity and discards to keep the most equity
against the opponent's range.
"""
import numpy as np

from _common import BIG_BLIND, C, PortBot, equity, pre_pct, random, run


class Beta:
    def __init__(self, mean, strength):
        self.k = self.n = 0.0
        self.a, self.b = mean * strength, (1 - mean) * strength

    def add(self, hit):
        self.k += bool(hit)
        self.n += 1

    def mean(self):
        return (self.k + self.a) / (self.n + self.a + self.b)


class OppModel:
    def __init__(self):
        self.vpip, self.pfr = Beta(0.60, 20), Beta(0.40, 20)
        self.three_bet, self.agg = Beta(0.15, 10), Beta(0.40, 20)
        self.fold_to_bet, self.wtsd = Beta(0.40, 15), Beta(0.35, 10)
        self.hands = 0

    def observe(self, history, showdown):
        self.hands += 1
        vpip = pfr = acted_pre = faced = three = saw_flop = False
        last_raiser = None
        for i, a in enumerate(history):
            if a["street"] == "preflop":
                if a["actor"] == "opp":
                    acted_pre = True
                    if last_raiser == "me":
                        faced = True
                        three |= a["action"] == "raise"
                    vpip |= a["action"] in ("call", "raise")
                    pfr |= a["action"] == "raise"
                if a["action"] == "raise":
                    last_raiser = a["actor"]
                continue
            saw_flop = True
            if a["actor"] != "opp":
                continue
            self.agg.add(a["action"] == "raise")
            for j in range(i - 1, -1, -1):  # facing our bet: our last action this street raised
                b = history[j]
                if b["street"] != a["street"]:
                    break
                if b["actor"] == "me":
                    if b["action"] == "raise":
                        self.fold_to_bet.add(a["action"] == "fold")
                    break
        if acted_pre:
            self.vpip.add(vpip)
            self.pfr.add(pfr)
        if faced:
            self.three_bet.add(three)
        if saw_flop:
            self.wtsd.add(showdown)

    def archetype(self):
        if self.hands < 15:
            return "unknown"
        v, p, af = self.vpip.mean(), self.pfr.mean(), self.agg.mean()
        ratio = p / v if v > 0 else 0
        if v < 0.30:
            return "nit"
        if v > 0.70 and ratio > 0.60 and af > 0.35:
            return "maniac"
        if v > 0.55 and ratio < 0.35:
            return "station"
        if v > 0.60 and ratio > 0.45:
            return "lag"
        return "tag"

    def range_width(self, raised, reraised):
        w = self.three_bet.mean() * self.vpip.mean() if reraised else (self.pfr.mean() if raised else self.vpip.mean())
        return min(1.0, max(0.04, w))


def texture(board):
    suits = [0] * 4
    counts = [0] * 13
    ranks = 0
    for c in board:
        suits[c & 3] += 1
        counts[c >> 2] += 1
        ranks |= 1 << (c >> 2)
    max_suit, paired = max(suits), max(counts) >= 2
    ext = (ranks << 1) | (ranks >> 12 & 1)  # ace also low
    connected = max(bin((ext >> lo) & 0x1F).count("1") for lo in range(10))
    flushy = 1.0 if max_suit >= 3 else 0.5 if max_suit == 2 else 0.0
    straighty = 1.0 if connected >= 3 else 0.4 if connected == 2 else 0.0
    return min(1.0, max(0.0, 0.5 * flushy + 0.4 * straighty - (0.15 if paired else 0.0)))


class Bot(PortBot):
    def __init__(self):
        super().__init__()
        self.opp = OppModel()
        self.we_raised_pre = False
        self.last_history = []

    def new_hand(self, msg):
        self.we_raised_pre = False
        self.last_history = []

    def observe(self, msg):
        self.opp.observe(msg.get("history") or [], msg.get("result") == "showdown")

    def weight_fn(self, history):
        """Likelihood of each opponent hand (by preflop percentile) given its actions."""
        opp_raises_pre = opp_aggr_post = 0
        we_before = our_raise = False
        for a in history:
            if a["action"] != "raise":
                continue
            if a["street"] == "preflop":
                if a["actor"] == "opp":
                    opp_raises_pre += 1
                    we_before |= our_raise
                else:
                    our_raise = True
            elif a["actor"] == "opp":
                opp_aggr_post += 1
        reraised = opp_raises_pre >= 2 or we_before
        width = self.opp.range_width(opp_raises_pre > 0, reraised)
        af = self.opp.agg.mean()
        for _ in range(opp_aggr_post):
            width *= 0.70 + 0.3 * af
        width = min(1.0, max(0.05, width))

        def w(pct):  # Range::top(width, soft 0.08); its percentile is 0 for the best hand
            return np.maximum(np.clip((width - (1 - pct)) / 0.08 + 0.5, 0, 1), 0.02)
        return w

    def equity(self, req, n=1500):
        return equity(self.hole, self.board(req), self.dead(), n=n,
                      weight=self.weight_fn(req.get("history") or []), opp_disc=self.opp_discard)[0]

    def choose_discard(self, req):
        hole = [C[c] for c in req["hole_cards"]]
        return equity(hole, self.board(req)[:3], n=1500, weight=self.weight_fn(self.last_history))[1]

    def raise_frac(self, req, frac):
        """Bet `frac` of the pot after calling."""
        return self.raise_to(req, req["my_bet"] + req["to_call"] + frac * (req["pot"] + req["to_call"]))

    def act(self, req):
        self.last_history = req.get("history") or []
        return self.preflop(req) if req["street"] == "preflop" else self.postflop(req)

    def preflop(self, req):
        pct = 1 - pre_pct(self.hole)  # 0 = best
        arch = self.opp.archetype()
        legal = req["legal_actions"]
        can_raise = "raise" in legal
        if self.button and req["my_bet"] == 1 and req["opp_bet"] == BIG_BLIND:
            open_ = {"nit": 0.90, "station": 0.55, "maniac": 0.55, "lag": 0.70}.get(arch, 0.80)
            if pct <= open_ and can_raise:
                self.we_raised_pre = True
                return self.raise_to(req, (4 if arch == "station" else 3) * BIG_BLIND)
            if pct <= open_ + 0.12 and arch != "maniac":
                return self.call_or_check(req)
            return self.fold_or_check(req)
        if req["to_call"] == 0:  # big blind after a limp
            if pct <= (0.40 if arch == "station" else 0.30) and can_raise:
                self.we_raised_pre = True
                return self.raise_frac(req, 1.0)
            return {"type": "action", "action": "check"}
        e = self.equity(req, n=800)
        po = req["to_call"] / (req["pot"] + req["to_call"])
        margin = -0.02 if self.button else 0.02
        margin += {"maniac": -0.04, "nit": 0.04}.get(arch, 0.0)
        eff = min(req["my_stack"] + req["my_bet"], req["opp_stack"] + req["opp_bet"])
        if (e > 0.60 or pct <= 0.03) and can_raise:
            to = 3 * req["opp_bet"]
            if to * 3 > eff:
                to = req["max_raise"]
            self.we_raised_pre = True
            return self.raise_to(req, to)
        if e >= po + margin:
            return self.call_or_check(req)
        return self.fold_or_check(req)

    def postflop(self, req):
        arch = self.opp.archetype()
        e = self.equity(req)
        wet = texture(self.board(req))
        spr = min(req["my_stack"], req["opp_stack"]) / max(1, req["pot"])
        river = req["street"] == "river"
        ftb, af = self.opp.fold_to_bet.mean(), self.opp.agg.mean()
        can_raise = "raise" in req["legal_actions"]
        if req["to_call"] == 0:
            if not can_raise:
                return {"type": "action", "action": "check"}
            value_thr = (0.66 if river else 0.63) + {"station": -0.06, "nit": 0.04}.get(arch, 0.0)
            if e >= value_thr:
                if spr < 1.5 or (e > 0.85 and spr < 3.0):
                    return self.raise_to(req, req["max_raise"])
                size = 0.75 if river else 0.55 + 0.25 * wet
                if arch == "station":
                    size += 0.25
                return self.raise_frac(req, size)
            bluff_p = 0.0 if arch == "station" else min(0.55, max(0.0, (ftb - 0.30) * 1.2 + 0.10))
            if self.we_raised_pre and req["street"] == "flop" and wet < 0.4 and random.random() < min(0.85, bluff_p + 0.35):
                return self.raise_frac(req, 0.33)
            if not river and e >= 0.35 and random.random() < bluff_p:
                return self.raise_frac(req, 0.5 + 0.2 * wet)
            if river and e < 0.25 and random.random() < bluff_p * 0.6:
                return self.raise_frac(req, 0.7)
            return {"type": "action", "action": "check"}
        po = req["to_call"] / (req["pot"] + req["to_call"])
        margin = (0.02 if river else 0.0) + (0.40 - af) * 0.20
        margin += {"maniac": -0.05, "nit": 0.05}.get(arch, 0.0)
        if e >= (0.80 if river else 0.75) and can_raise:
            if spr < 2.0:
                return self.raise_to(req, req["max_raise"])
            return self.raise_frac(req, 0.8)
        if e >= po + margin:
            return self.call_or_check(req)
        if not river and can_raise and ftb > 0.6 and e > 0.3 and random.random() < 0.15:
            return self.raise_frac(req, 0.8)
        return self.fold_or_check(req)


if __name__ == "__main__":
    run(Bot())
