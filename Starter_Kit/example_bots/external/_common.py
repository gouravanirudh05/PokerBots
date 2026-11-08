"""Shared plumbing for ports of public pokerbots to Discard Hold'em.

The bots in this folder re-implement the decision logic of bots published on GitHub
for other competitions, adapted to this game's rules and protocol. They are local
sparring partners only and must never be copied into the submission (Rulebook 10.1).
Where a source bot's game differs (2-card hands, an auction, a board discard), the
port keeps its decision rules and fills the gap the way that bot would most
naturally play: best-keep equity with 3 cards, and discarding the card whose
removal leaves the most equity.
"""
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot_v4 as ev  # noqa: E402  (frozen evaluator, preflop table, card names)

C = ev.CARD_INDEX
RANKS = ev.RANKS
STARTING_STACK, BIG_BLIND = 200, 2


def pre_pct(three):
    """Percentile (1 = best) of a 3-card hand among all 3-card hands."""
    return float(ev.PRE[0, three[0], three[1], three[2]])


def equity(hole, board, dead=(), n=600, weight=None, opp_disc=None):
    """Monte Carlo equity against a random opponent hand, optionally weighted.

    hole: 3 cards (preflop/flop: the best keep's equity is returned) or 2 cards.
    weight: maps the opponent's preflop percentile (1 = best, per sample) to a
    likelihood. With 3 cards the opponent keeps its heuristic best pair on the flop.
    Returns (equity, index of the card to discard; 0 when holding 2 cards).
    """
    known = set(hole) | set(board) | set(dead)
    n_opp = 3 if len(hole) == 3 else 2
    s = ev.deal(known, n, n_opp + 5 - len(board))
    opp, runout = s[:, :n_opp], s[:, n_opp:]
    full = np.concatenate([np.broadcast_to(np.array(board, dtype=np.intp), (n, len(board))), runout], axis=1)
    if n_opp == 3:
        pct = ev.PRE[0][opp[:, 0], opp[:, 1], opp[:, 2]]
        d, _ = ev.heuristic_keeps(opp, full[:, :3])
        opp = np.take_along_axis(opp, ev.KEEP_IDX[d], axis=1)
    elif opp_disc is not None:
        pct = ev.PRE[0][opp[:, 0], opp[:, 1], np.full(n, opp_disc)]
    else:
        pct = np.full(n, 0.5)
    w = np.ones(n) if weight is None else weight(pct)
    opp_val = ev.evaluate(np.concatenate([opp, full], axis=1))
    keeps = ev.KEEP_IDX if len(hole) == 3 else [np.array([0, 1])]
    eqs = [ev.wavg(ev.showdown(ev.evaluate(np.concatenate([np.broadcast_to(np.array(hole)[k], (n, 2)), full], 1)),
                               opp_val), w) for k in keeps]
    best = int(np.argmax(eqs))
    return eqs[best], best


class PortBot:
    """Protocol loop and state; subclasses implement act(req) and choose_discard(req)."""

    def __init__(self):
        self.hand_id = 0
        self.button = False
        self.hole = []
        self.my_discard = self.opp_discard = None

    # ---- helpers for subclasses

    @staticmethod
    def fold_or_check(req):
        return {"type": "action", "action": "check" if "check" in req["legal_actions"] else "fold"}

    @staticmethod
    def call_or_check(req):
        return {"type": "action", "action": "call" if "call" in req["legal_actions"] else "check"}

    @staticmethod
    def raise_to(req, amount):
        if "raise" not in req["legal_actions"]:
            return PortBot.call_or_check(req)
        amount = int(max(req["min_raise"], min(req["max_raise"], round(amount))))
        return {"type": "action", "action": "raise", "amount": amount}

    def board(self, req):
        return [C[c] for c in req.get("board", [])]

    def dead(self):
        return [c for c in (self.my_discard, self.opp_discard) if c is not None]

    # ---- hooks

    def new_hand(self, msg):
        pass

    def observe(self, msg):
        pass

    def act(self, req):
        raise NotImplementedError

    def choose_discard(self, req):
        """Index (into req["hole_cards"]) of the card to discard."""
        raise NotImplementedError

    # ---- protocol

    def handle(self, msg):
        t = msg.get("type")
        if t == "new_hand":
            self.hand_id = msg.get("hand_id", self.hand_id + 1)
            self.button = msg.get("seat") == "button"
            self.hole = [C[c] for c in msg.get("hole_cards", [])]
            self.my_discard = self.opp_discard = None
            self.new_hand(msg)
        elif t == "discard_result":
            self.my_discard = C.get(msg.get("my_discard"))
            self.opp_discard = C.get(msg.get("opp_discard"))
            self.hole = [C[c] for c in msg.get("hole_cards", [])]
        elif t == "hand_result":
            self.observe(msg)
        elif t == "action_request":
            try:
                return self.act(msg)
            except Exception as exc:
                print(f"action error: {exc!r}", file=sys.stderr)
                return self.fold_or_check(msg)
        elif t == "discard_request":
            cards = msg["hole_cards"]
            try:
                return {"type": "discard", "card": cards[self.choose_discard(msg)]}
            except Exception as exc:
                print(f"discard error: {exc!r}", file=sys.stderr)
                return {"type": "discard", "card": cards[0]}
        return None


def run(bot):
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("type") == "match_end":
            break
        reply = bot.handle(msg)
        if reply is not None:
            print(json.dumps(reply), flush=True)


__all__ = ["C", "RANKS", "STARTING_STACK", "BIG_BLIND", "pre_pct", "equity", "PortBot", "run", "random", "np", "ev"]
