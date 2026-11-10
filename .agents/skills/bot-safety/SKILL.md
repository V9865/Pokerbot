---
name: bot-safety
description: How the Discard Hold'em bot avoids forfeits and penalties - the safe message loop, reply sanitising, fallbacks, the time governor, the no-numpy degraded mode, bundling src into one dist\bot.py, and the pre-upload checklist. Use when touching main.py, safety.py, timing, tools\bundle.py, or when preparing an upload.
---
# Bot safety

A forfeit is a match loss at -400 (Stage 1) or -1000 (Stage 2). Safety beats strategy.

## 1. The loop (src\main.py, already implemented - keep these properties)
- safety.py sets OUT = sys.stdout and then sys.stdout = sys.stderr, so a stray
  print can never reach the engine. Replies go out only through send(), which
  writes one JSON line and flushes.
- For action_request and discard_request: build the reply inside try/except,
  pass it through sanitize_action / sanitize_discard, send it, then gov.done().
  On any exception send fallback_action / fallback_discard.
- Every other message goes to brain.observe() inside try/except; no reply.
- Blank lines, invalid JSON and non-object JSON are skipped.
- match_end or end of input ends the loop; the process then exits.
- Exactly ONE line per request. Never reply to anything else.
- Derive the situation from the request (history, board, pot, bets) each time.
  Stored state is only for what the request lacks: our hole cards, both
  discards, the opponent model, caches.

## 2. Sanitising and fallbacks (src\safety.py)
- sanitize_action: action must be in legal_actions; "fold" becomes "check"
  when check is legal; raise amount becomes an int clamped to
  [min_raise, max_raise]; anything else -> fallback_action.
- fallback_action: check if legal; else call if to_call <= 2; else fold.
- sanitize_discard: the card must be one of req["hole_cards"]; else
  fallback_discard (cheap rule, then the first card).
- New decision code must return plain dicts and may raise freely; the loop
  catches it. Never add a code path that writes to OUT directly.

## 3. Time
- Governor.start() picks a mode from time_left_ms / hands remaining:
  > 100 ms FULL; 50-100 HALF; 25-50 QUARTER; < 25 ms or under 2 s left PANIC.
  FULL uses MC_FLOP samples and every river card on the turn; HALF and QUARTER
  halve and quarter them; PANIC uses the table, the cheap rule and a tiny
  scalar simulation.
- Budget: under 40% of the bank per leg and no reply over 250 ms on this
  machine. v1 uses about 7% and 23 ms. The tournament machine may be slower.
- observe() must stay cheap. The next request is usually already waiting, so
  work done on non-request messages is charged in practice. If a phase adds
  heavy work at showdown (for example discard-rule learning), bound it.
- Any new loop over samples or hands must be vectorised with numpy or check
  time.perf_counter() against DECISION_CAP_MS.
- Start-up (imports, tables) must stay under 2 s. Measure after adding tables.
- Read total_hands and the time bank from init. Never hard-code 200 or 30000.

## 4. Degraded mode without numpy
evaluator.py sets HAVE_NP. If numpy fails to import, the bot still plays:
table preflop, cheap discard, scalar_equity postflop. Any new numpy-only code
must sit behind `if HAVE_NP` with a scalar or heuristic fallback. Test it:
  py -3.11 tools\fuzz_protocol.py dist\bot.py 1500 250 --no-numpy
(this fuzzes a copy of the bot in which numpy cannot be imported).

## 5. Bundling (tools\bundle.py)
- Concatenates src modules in ORDER into dist\bot.py, removes project imports,
  fails on duplicate top-level names and on forbidden names (socket,
  subprocess, threading, multiprocessing, os.system, urllib, requests, open().
- New module: add it to ORDER after everything it imports.
- In src, import project modules only as `from <module> import <names>` on a
  single line at the top of the file (the bundler deletes those lines).
- dist\bot.py is never edited by hand.

## 6. Pre-upload checklist (print PASS or FAIL with evidence for each)
1. `py -3.11 tools\bundle.py` succeeds; dist\bot.py under 5 MB.
2. `py -3.11 tools\test_evaluator.py` -> RESULT: OK.
3. `py -3.11 tools\test_history.py` -> RESULT: OK.
4. `py -3.11 tools\fuzz_protocol.py dist\bot.py 3000` -> RESULT: OK, worst
   reply under 250 ms. The "caught errors" count comes from deliberately
   inconsistent fuzz input and is acceptable; a FAIL line is not.
5. `py -3.11 tools\fuzz_protocol.py dist\bot.py 1500 250 --no-numpy` -> RESULT: OK.
6. `py -3.11 tools\timing_report.py --stage 1` and `--stage 2` -> RESULT: OK.
7. `py -3.11 tools\run_matches.py --opps all --seeds 1-10 --tag preupload`
   -> exit code 0 (no notices, forfeits or tracebacks from our bot).
8. Regression: does not lose to the previous snapshot over 40 seeds
   (see match-testing).
9. dist\bot.py contains no file access, network, subprocess or thread code
   (the bundler checks) and imports only stdlib and numpy/scipy.
10. Copied to snapshots\vN_bot.py; memory updated; committed.
