# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Competition entry for Pokerbots: a Python 3.11 bot that plays **Discard Hold'em** (heads-up no-limit Hold'em with 3 hole cards and a simultaneous, face-up discard of one hole card after flop betting). Submission deadline: 15 Nov 2026, 23:59 IST. The deliverable is a single `bot.py` (or a `.zip` with `bot.py` at top level, ≤ 5 MB).

The authoritative specs are the text files in the repo root (note: `.gitignore` excludes `*.txt` and `*.pdf`, so they are local-only):
- `Problem_Statement_Updated.txt` / `problemStatement_Updated.pdf`: game rules with worked examples (prevails on game rules)
- `Protocol_Updated.txt` / `protocol_specification.pdf`: stdin/stdout JSON message formats and legality
- `Rulebook_Updated.txt` / `RuleBook_Updated.pdf`: tournament structure, limits, scoring, conduct (prevails on everything else)

The non-`Updated` `Rulebook.txt`, `Protocol.txt` and `Problem_Statement.txt` and `rules.pdf` are the superseded first release. The update (7 Nov 2026) introduced legs: a match is two legs of 200 hands (Stage 1) or 500 hands (Stage 2), each played by a freshly started process, with leg 2 swapping cards and seats on the same deals. The bot can't know the match score, which is why there is no end-of-match logic. The bundled `engine.py` predates this; `--leg 1|2` implements the updated format, and `arena.py` plays two legs per match by default (`--no-legs` is the old single-run format).

## Commands

The machine has no system Python 3.11; a uv venv at `.venv/` (Python 3.11 + numpy + scipy, gitignored) matches the competition. Recreate with `uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python numpy scipy`.

The engine starts bots with cwd = the bot's directory, so `--python` must be an **absolute, non-symlink-resolved** path (`realpath` on the venv python drops the venv and numpy goes missing).

```bash
PY=$PWD/.venv/bin/python   # run from the repo root
cd Starter_Kit
$PY engine.py bot.py example_bots/tag_bot.py --python $PY --leg 1           # one Stage 1 leg: 200 hands, 30 s bank
$PY engine.py bot.py example_bots/tag_bot.py --python $PY --leg 2 --stage 2 # one Stage 2 leg: 500 hands, 75 s bank, 225 s wall clock
$PY engine.py A.py B.py --python $PY --leg 1 --hands 20 --seed 42 --verbose # short reproducible leg
# parallel matches against one or more opponents: mean ± SE, chips/hand, W/D/L, max time
$PY ../tools/arena.py bot.py example_bots/bot_v3.py example_bots/tag_bot.py --matches 16 --jobs 14 --no-time-limits
BOT_MODE=cfr $PY ../tools/arena.py ...    # force bot.py's mode: cfr (embedded strategy) or exploit (EV engine)
BOT_NO_LOCK=1 ...                         # only for frozen bots up to v4, which still have the old match lock
$PY ../tools/arena.py ... --log-root DIR  # keep logs, then: $PY ../tools/leaks.py DIR  (chips by street / outcome / seat)
$PY ../tools/river_lines.py DIR           # chips by river betting line, from the same logs
$PY ../tools/switch_sim.py DIR 500 cfr_bot=-0.02 bot_v3=0.60 ...  # replay switch rules on exploit-mode logs (opponent=CFR-mode rate)
$PY ../tools/check_bot.py                 # safety regression: low bank, broken messages, broken strategy blob
$PY ../tools/gen_preflop.py               # regenerate the embedded preflop table (~30 s on 16 cores)
# CFR strategy: deal pool (~5 min), MCCFR (resumable, checkpoints every 2 min), embed into bot.py
$PY ../tools/cfr_train.py deals --jobs 10 && $PY ../tools/cfr_train.py train --iters 600000000 && $PY ../tools/cfr_train.py pack
```

Run long jobs detached (`setsid nohup ... > tools/cfr/train.log 2>&1 &`): a background shell dies with the session, and a reboot also wipes the scratchpad, so keep anything worth having under `tools/cfr/work/` (gitignored). `train` resumes from `tools/cfr/work/state.bin`. `deals` wipes that state. `pack` also works on a mid-run checkpoint. `pack` rewrites bot.py's `CFR_DATA` line (quantized to 1/15 steps, zlib, base64: about 1 MB).

Logs go to `logs/` (`--log-dir ''` disables): `match.log` has one line per hand (actions abbreviated `x` check, `c6` call to 6, `r20` raise to 20, `f` fold); `A_stderr.txt` / `B_stderr.txt` capture each bot's stderr (first 64 KB; the bot logs opponent-model stats every 100 hands). There is no test suite; a clean run means zero `notices` and no forfeit.

### Evaluating changes

- The yardstick is head-to-head against both `example_bots/cfr_bot.py` and `bot_v3.py` (they punish opposite mistakes), the public ports, and the pool. **Never judge a change on blueprint-style opponents alone**: the river solver measured +0.17 against `cfr_bot` and mirrors, then lost −1.88 to v3 and −0.87 to the IIT port on the same seeds, and was removed. Run an A/A control on the same seeds before believing a gain. The weak pool bots are beaten by 2–58 chips/hand and can't tell close versions apart; `tag_bot` and `mc_bot` are the most informative of them. Many plausible tweaks that look good in theory lose to the CFR bot or to v3, so test both. Use `BOT_NO_LOCK=1` for chip rates, but check match points with the lock on.
- Against a 64-match run's ±0.15/hand noise, decide with 128+ matches on fresh seeds.
- Noise: a 400-hand match swings about ±500 chips even with duplicate deals. Use 64+ matches (~6 min at 14 jobs) for a head-to-head verdict, and compare candidates **on the same `--seed`** so they see the same deals.
- Use `--no-time-limits` for parallel A/B runs (otherwise CPU contention can forfeit). In that mode the bots see an infinite bank and always use their max sample count, so **its "max time" figures are meaningless**. Judge timing with real clocks on 1–4 uncontended matches. Worst case for v5 with both bots pinned to one core (`taskset`): 15.0 s of the 30 s bank at Stage 1 and 40.9 s of the 75 s bank at Stage 2, both vs `check_call_bot`. Start-up to first reply is about 1.4 s; peak memory 86 MB.
- After a version is clearly better, freeze it as `example_bots/bot_vN.py` (each frozen copy is self-contained, preflop table included).
- A finer abstraction didn't help: blueprint v2 (1755 lossless preflop classes, 144/144/120 buckets, 3M deals, 2.7B iterations, `tools/cfr/work2/`) drew with v1 head-to-head (−0.05 ± 0.17) and did no better against `cfr_bot` or v3, at twice the file size. It was rejected.
- Deal pools from before 4 Nov use uint8 buckets (9 bytes per deal). The current `mccfr` reads uint16 (17 bytes) and won't notice the difference, so convert old pools first; `tools/cfr/work1b/` is the converted v1 pool, and `tools/cfr/work/` is the original.
- Known model weakness (measured against the CFR bot): range weights from `m_weight` are too concentrated on strong hands, so the predicted fold rate to our turn/river bets is far below the actual rate (e.g. 21% predicted vs 56% actual), and equity vs callers is overestimated. Flattening the weights (an exponent on the likelihoods) or taking callers as the top of the weighted range both tested worse.

## Architecture

- `Starter_Kit/engine.py`: local match runner that mirrors the official engine. Spawns each bot as a subprocess, runs duplicate deals (hands 2k+1 and 2k+2 share cards, seats swapped, seeded by `f"{seed}:{deal}"`), enforces min-raise / 4-raise cap / all-in rules, the simultaneous discard, time banks, and corrections. Time spent before 5 s after launch is not charged.
- `Starter_Kit/bot.py`: **the submission** (single self-contained file, about 1.2 MB). It has two modes: the exploitative EV engine (most of the pieces below) and an embedded CFR strategy. It starts in exploit mode, which plays the blueprint on preflop and flop (`BLUEPRINT_STREETS`) and the EV engine on turn and river, until, after 60 hands, a win rate of 3 chips/hand shows the opponent is weak and the EV engine takes every street (`PRE_EXPLOIT_*`). Extending the blueprint to the turn tested worse. From hand 200, checked every 40 hands, a loss rate over 2 chips/hand switches to full CFR for the rest of the leg (`_choose_mode`, `SWITCH_*`): this is insurance only, since exploit mode matched or beat CFR mode against every opponent tested. Pieces:
  - Evaluator: card = `4*rank + suit` (rank 0 = deuce). Non-flush values come from a sorted table of rank multisets (key = Σ 5^rank, looked up with `np.searchsorted`); flushes from an 8192-entry suit-mask table. Built at import (~0.4 s, uncharged start-up). Values are `category << 20 | kicker nibbles`. Verified against `engine.best_hand`.
  - `keep_score` / `heuristic_keeps`: flop strength of a kept pair (made hand + flush/straight-draw bonus). Used to model the opponent's discard and flop strength, not our own discard.
  - `PREFLOP_DATA`: base64 table between the `BEGIN/END PREFLOP DATA` markers, written by `tools/gen_preflop.py`, never edited by hand. 5 columns per 3-card hand: percentile, equity vs random / top 50% / 25% / 12%. Regenerate after changing `keep_score` or the evaluator.
  - `flop_sim` / `later_sim`: Monte Carlo over sampled opponent hands. Each returns per-sample results `res`, likelihood weights `w`, and the opponent's strength percentile among the samples (keep score on the flop, made-hand value later). Weights multiply `m_weight(percentile, m)` for every opponent action, where `m` is the mean showdown percentile of hands behind that kind of action (`action_kind`: pre_raise, bet_small, bet_big, raise, call, check ...), learned in `OppModel._calibrate` from priors. The exposed opponent discard is weighted by how often its discards matched `heuristic_keeps` at showdown. Our discard = argmax equity over the 3 keeps.
  - `Bot.postflop`: picks the max-EV option among check/call/fold and `BET_SIZES` (capped per street by `MAX_SIZE`, so no early overshoves). The opponent folds samples below a strength threshold given by `OppModel.fold_prob(kind, size, street)`. Kind is bet/raise/reraise by raise depth on the street, learned per street and size bucket. When we're called, equity realization is computed from our equity against the callers, not the whole range. That makes it fold less once its range has been narrowed by earlier calls. `realize()` discounts equity on flop and turn, more for weak hands. `_check_ev` looks one opponent bet ahead when we act first.
  - The adaptive preflop (`Bot.preflop`, used against clearly weak opponents and off the blueprint's tree) is threshold-based on the table, loosened or tightened by the opponent's fold-to-raise rate. Facing raises, it uses equity against the range width implied by the opponent's raise frequency and showdowns.
  - Sample counts adapt to the time bank (`n_samples`, 25% of the remaining bank spread over remaining hands, 150–5000 samples).
  - CFR section (`CfrTree`, `cfr_*_features`, `CfrPlayer`, `CFR_DATA`): the abstraction the strategy was trained on. Pot-fraction bets (1/3, 2/3, pot, all-in); imperfect-recall buckets per street (preflop percentile; flop/turn equity x current strength; river strength, all vs a random hand); max-equity discard. Opponent sizes map to the tree with randomized pseudo-harmonic translation. When a hand leaves the tree, `CfrPlayer.action` returns None and the EV engine decides. Any change to this abstraction needs `cfr_train.py deals` + `train` + `pack`.
  - All request handling is wrapped so exceptions fall back to check/fold or the default discard, and never crash.
- `Starter_Kit/example_bots/`: frozen baselines `bot_v1.py` (threshold-based), `bot_v2.py` (first EV bot), `bot_v3.py` (EV bot with the per-street fold model), `bot_v4.py` (first hybrid) and `bot_v5.py` (= current bot.py), plus sparring opponents: `minraise_bot`, `overbet_bot`, `minbet_bot`, `polar_bot`, `smallball_bot` (odd bet sizes, to check the blueprint's size translation; v5 went 80–0 against them), `random_bot`, `check_call_bot` (original starter), `tag_bot` (rule-based tight-aggressive), `mc_bot` (classic equity-vs-pot-odds bot, imports `bot_v1` for its evaluator), `bluff_bot` (loose barreler), `allin_bot` (shoves every hand), `maniac_bot`, `cfr_bot` (below).
- `example_bots/cfr_bot.py`: sparring opponent that plays `bot_v4`'s embedded CFR strategy only (no exploit mode, no match lock). It's the method of MIT 2017's winner rebuilt for this game; that bot itself plays a different variant and can't run here. It doesn't adapt, so losing chips to it means a real leak in the exploit engine.
- `Starter_Kit/example_bots/external/`: ports of public bots, adapted to this game's rules and protocol (shared plumbing in `_common.py`, built on `bot_v4`): `mit_ref1/2/3` (MIT Pokerbots 2026 official reference bots; MIT 2026 used a related 3-card discard variant), `iit2026_equity` (an IIT Pokerbots 2026 equity bot that raises or folds when facing bets), `mit2024_profiler` (an MIT 2024 entry with VPIP/PFR archetype profiling and range-weighted Monte Carlo equity). They are local sparring partners only: never copy their code into the submission (Rulebook 10.1). v5 beats them by +34, +33, +26, +3.9 and +9.5 chips/hand at Stage 2 and has won every match. Exploit mode beats the last two far more than CFR mode does (+3.9 vs +1.6, +9.5 vs +2.3), so a false switch to CFR is costly.
- `tools/arena.py`: parallel match runner and summariser. `tools/leaks.py`: chip breakdown from kept logs. `tools/gen_preflop.py`: preflop table generator (imports `bot.py`).

## Hard constraints for bot code

- **stdout is protocol-only.** Every reply is exactly one JSON line, flushed (`print(..., flush=True)`). Any stray print is a malformed message, corrected to check/fold. Debug output goes to `sys.stderr`.
- Only stdlib, numpy and scipy. Read-only FS, no network, no sockets or subprocesses. Rule 5.4 now lets a bot read files inside its own submission (a zip holding `bot.py`), though everything is still embedded in `bot.py` for now. Avoid optional stdlib modules such as `lzma` that a minimal Python build may lack: an import crash forfeits every match.
- Must never crash: a crash, EOF, a reply over 5 s, an exhausted time bank (30 s per 200-hand leg, 75 s per 500-hand leg) or the wall-clock kill (90 s / 225 s per leg) in either leg forfeits the whole match at Δ = −C. Budget compute using `time_left_ms` from each request; `_check_time` is the last-resort guard (`tools/check_bot.py` tests it). Time before 5 s after launch is uncharged in every leg. Resources: 1 vCPU, 1 GB RAM.
- Ignore unknown message types and fields (forward compatibility).
- Raise `amount` is a **"to" total for the current street**, not an increment, and must satisfy `min_raise ≤ amount ≤ max_raise`. `min_raise = opp_bet + max(last_raise_size, 2)`; the big blind counts as the first of the 4 bets/raises preflop.
- A discard request is sent even when one or both players are all-in (no betting follows). Fold before flop betting ends → no discard.
- Illegal discards default to the lowest-ranked hole card (ties: s, h, d, c); illegal actions default to check, else fold.
- Bot is restarted fresh per leg; state lives only within a leg. Rule 10.3 prohibits any attempt to identify the two hands of a duplicate deal or to carry information between legs.
- Rulebook 10.1: no code copied from other teams or public bot repositories; published algorithms (CFR, Monte Carlo, etc.) are fine, as is reusing `engine.py` code.
