# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Competition entry for Pokerbots: a Python 3.11 bot that plays **Discard Hold'em** (heads-up no-limit Hold'em with 3 hole cards and a simultaneous, face-up discard of one hole card after flop betting). Submission deadline: 15 Nov 2026, 23:59 IST. The deliverable is a single `bot.py` (or a `.zip` with `bot.py` at top level, ≤ 5 MB).

The authoritative specs are the text files in the repo root (note: `.gitignore` excludes `*.txt` and `*.pdf`, so they are local-only):
- `Problem_Statement.txt`: game rules with worked examples (prevails on game rules)
- `Protocol.txt` / `Protocol Specification.pdf`: stdin/stdout JSON message formats and legality
- `Rulebook.txt` / `rules.pdf`: tournament structure, limits, scoring, conduct (prevails on everything else)

## Commands

The machine has no system Python 3.11; a uv venv at `.venv/` (Python 3.11 + numpy + scipy, gitignored) matches the competition. Recreate with `uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python numpy scipy`.

The engine starts bots with cwd = the bot's directory, so `--python` must be an **absolute, non-symlink-resolved** path (`realpath` on the venv python drops the venv and numpy goes missing).

```bash
PY=$PWD/.venv/bin/python   # run from the repo root
cd Starter_Kit
$PY engine.py bot.py example_bots/tag_bot.py --python $PY                 # Stage 1: 400 hands, 60 s bank
$PY engine.py bot.py example_bots/tag_bot.py --python $PY --stage 2       # 1000 hands, 150 s bank, 450 s wall clock
$PY engine.py A.py B.py --python $PY --hands 20 --seed 42 --verbose       # short reproducible match
$PY ../tools/arena.py bot.py example_bots/tag_bot.py --matches 12 --jobs 6   # parallel matches, mean ± SE, W/D/L, max time
BOT_NO_LOCK=1 $PY ../tools/arena.py ...   # disable the match-lock fold-out to measure raw chip win rates
$PY ../tools/gen_preflop.py               # regenerate the embedded preflop table (~30 s on 16 cores)
```

Logs go to `logs/` (`--log-dir ''` disables): `match.log` has one line per hand (actions abbreviated `x` check, `c6` call to 6, `r20` raise to 20, `f` fold); `A_stderr.txt` / `B_stderr.txt` capture each bot's stderr (first 64 KB). There is no test suite; a clean run means zero `notices` and no forfeit. Running many arena jobs at once inflates "time used" through CPU contention, so judge timing on uncontended runs (worst case so far: Stage 2 self-play, ~33 s of 150 s).

## Architecture

- `Starter_Kit/engine.py`: local match runner that mirrors the official engine. Spawns each bot as a subprocess, runs duplicate deals (hands 2k+1 and 2k+2 share cards, seats swapped, seeded by `f"{seed}:{deal}"`), enforces min-raise / 4-raise cap / all-in rules, the simultaneous discard, time banks, and corrections. Time spent before 5 s after launch is not charged.
- `Starter_Kit/bot.py`: **the submission** (single self-contained file). Pieces:
  - Evaluator: card = `4*rank + suit` (rank 0 = deuce). Non-flush values come from a sorted table of rank multisets (key = Σ 5^rank, looked up with `np.searchsorted`); flushes from an 8192-entry suit-mask table. Built at import (~0.6 s, uncharged start-up). Values are `category << 20 | kicker nibbles`. Verified against `engine.best_hand`.
  - `keep_score` / `heuristic_keeps`: flop strength of a kept pair (made hand + flush/straight-draw bonus). Used to model the opponent's discard, not ours.
  - `PREFLOP_DATA`: base64 table between the `BEGIN/END PREFLOP DATA` markers, written by `tools/gen_preflop.py`, never edited by hand. 5 columns per 3-card hand: percentile, equity vs random / top 50% / 25% / 12%. Regenerate after changing `keep_score` or the evaluator.
  - `flop_equities` / `later_equity`: Monte Carlo against sampled opponent hands, weighted by `range_weight(percentile, alpha)`. Alphas come from `OppModel` (preflop width from per-situation raise rates; per-street aggression scaled by `tightness`). The opponent's exposed discard down-weights hands whose heuristic keep is inconsistent with it. Our discard = argmax equity over the 3 keeps.
  - Sample counts adapt to the time bank (`n_samples`, 30% of the remaining bank spread over remaining hands).
  - `_lead_is_safe`: folds out the rest of the match once the win is guaranteed and either the capped tie-break score is already maxed or playing on risks >1% chance of losing.
  - All request handling is wrapped so exceptions fall back to check/fold or the default discard, and never crash.
- `Starter_Kit/example_bots/`: sparring opponents: `random_bot`, `check_call_bot` (original starter), `tag_bot` (rule-based tight-aggressive, imports the engine's evaluator), `maniac_bot` (raises/shoves constantly).
- `tools/arena.py`: parallel match runner and summariser. `tools/gen_preflop.py`: preflop table generator (imports `bot.py`).

## Hard constraints for bot code

- **stdout is protocol-only.** Every reply is exactly one JSON line, flushed (`print(..., flush=True)`). Any stray print is a malformed message, corrected to check/fold. Debug output goes to `sys.stderr`.
- Only stdlib, numpy and scipy. No file I/O, sockets or subprocesses at competition time (read-only FS, no network); any precomputed tables must be embedded in `bot.py`/the zip.
- Must never crash: a crash, EOF, a reply over 5 s, an exhausted time bank (60 s / 400 hands, 150 s / ~1000 hands) or the wall-clock kill (180 s / 450 s) forfeits the whole match. Budget compute using `time_left_ms` from each request. Resources: 1 vCPU, 1 GB RAM.
- Ignore unknown message types and fields (forward compatibility).
- Raise `amount` is a **"to" total for the current street**, not an increment, and must satisfy `min_raise ≤ amount ≤ max_raise`. `min_raise = opp_bet + max(last_raise_size, 2)`; the big blind counts as the first of the 4 bets/raises preflop.
- A discard request is sent even when one or both players are all-in (no betting follows). Fold before flop betting ends → no discard.
- Illegal discards default to the lowest-ranked hole card (ties: s, h, d, c); illegal actions default to check, else fold.
- Bot is restarted fresh per match; no state carries between matches. Duplicate deals are not identified to the bot.
- Rulebook 10.1: no code copied from other teams or public bot repositories; published algorithms (CFR, Monte Carlo, etc.) are fine, as is reusing `engine.py` code.
