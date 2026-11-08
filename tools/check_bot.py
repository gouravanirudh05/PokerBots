#!/usr/bin/env python3
"""
Safety checks for bot.py that a normal match can't reach: a nearly empty time bank, the
and messages with unknown or missing fields.

    python3.11 tools/check_bot.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Starter_Kit"))
import bot as B  # noqa: E402


def request(left_ms, street="preflop", **extra):
    req = {"type": "action_request", "hand_id": 1, "street": street, "board": [], "pot": 3, "my_bet": 1,
           "opp_bet": 2, "to_call": 1, "my_stack": 199, "opp_stack": 198, "legal_actions": ["fold", "call", "raise"],
           "min_raise": 4, "max_raise": 200, "raises_left": 3, "history": [], "time_left_ms": left_ms}
    req.update(extra)
    return req


def start(total=200, bank=30000, hand_id=1, seat="button"):
    bot = B.Bot()
    bot.handle({"type": "init", "total_hands": total, "time_bank_ms": bank})
    bot.handle({"type": "new_hand", "hand_id": hand_id, "seat": seat, "hole_cards": ["As", "Kd", "7c"]})
    return bot


def check(name, ok):
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    return ok


def main():
    results = []

    # Nearly out of time: instant passive replies, and no heavy work afterwards.
    bot = start()
    t = time.perf_counter()
    reply = bot.handle(request(1200))
    results.append(check("low bank: folds or checks instantly", reply["action"] == "fold" and time.perf_counter() - t < 0.01))
    t = time.perf_counter()
    reply = bot.handle({"type": "discard_request", "hole_cards": ["As", "Kd", "7c"], "board": ["Ah", "7d", "2s"],
                        "pot": 12, "my_stack": 194, "opp_stack": 194, "time_left_ms": 1200})
    results.append(check("low bank: discards instantly", reply["type"] == "discard" and time.perf_counter() - t < 0.01))
    t = time.perf_counter()
    bot.handle({"type": "hand_result", "hand_id": 1, "result": "showdown", "net": 6, "board": ["Ah", "7d", "2s", "3c", "4h"],
                "my_hole_cards": ["As", "Kd"], "opp_hole_cards": ["Qs", "Qd"], "opp_discard": "2c", "history": []})
    results.append(check("low bank: hand results skip the model", time.perf_counter() - t < 0.01))

    # Forward compatibility.
    bot = start()
    results.append(check("unknown message ignored", bot.handle({"type": "something_new", "x": 1}) is None))
    reply = bot.handle(request(60000, new_field="y"))
    results.append(check("unknown field ignored", reply["type"] == "action"))
    reply = bot.handle({"type": "action_request", "legal_actions": ["check"]})
    results.append(check("broken request still answered", reply["action"] == "check"))

    reply = bot.handle({"type": "action_request"})
    results.append(check("request without legal actions still answered", reply["type"] == "action"))
    reply = bot.handle({"type": "discard_request"})
    results.append(check("discard request without cards still answered", reply["type"] == "discard"))
    saved, B.CFR_DATA = B.CFR_DATA, "not valid base64 data"
    player = B.CfrPlayer()
    B.CFR_DATA = saved
    results.append(check("a broken strategy blob disables CFR instead of crashing", player.ready is False))

    print("all passed" if all(results) else "FAILURES")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
