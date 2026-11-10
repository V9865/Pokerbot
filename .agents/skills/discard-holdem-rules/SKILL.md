---
name: discard-holdem-rules
description: Complete rules, scoring, limits and stdin/stdout protocol of Discard Hold'em (Pokerbots 2026). Use when writing or checking game logic, legal actions, raise amounts, message handling, discards, timing limits or the local engine.
---
# Discard Hold'em: rules and protocol

Sources: Problem Statement, Protocol Specification, Rulebook (docs\, scanned PDFs).
starter\engine.py implements the same rules. On game rules the Problem Statement
wins; on everything else the Rulebook wins. If engine.py and this file disagree,
report it.

## The hand
- Heads-up no-limit Hold'em with 3 hole cards each. Blinds 1 and 2.
- Stacks reset to 200 for both players EVERY hand. Nothing carries over.
- Seats alternate every hand. The button posts the small blind (1) and acts first
  preflop. The big blind acts first on flop, turn and river.
- Order: blinds -> 3 hole cards each -> preflop betting -> flop (3 cards) ->
  flop betting -> DISCARD -> turn -> betting -> river -> betting -> showdown.
- The board (5 cards) is fixed before any action. Discards never change it.
- Discard: if nobody folded by the end of flop betting, both players get a
  discard_request at the same time and each throws away 1 of their 3 cards.
  Neither sees the other's choice first. Then discard_result reveals both, and
  both cards are out of play. This also happens when one or both are all-in.
- Showdown: best 5 of (2 kept hole cards + 5 board), using 0, 1 or 2 hole cards.
  Ranks high to low: straight flush, quads, full house, flush, straight, trips,
  two pair, pair, high card. Ace is low only in A-2-3-4-5. No wrap-around.
  Kickers break ties; suits never do. Equal hands split: net 0 for both.
- A fold ends the hand at once: the folder loses what they committed; no more
  cards; no discard if the fold comes before flop betting ends.

## Betting
- Amounts are TO amounts: total committed on the current street after the action.
  Committed 2, raise to 10 -> adds 8.
- fold: only when to_call > 0. check: only when to_call == 0.
  call: only when to_call > 0. raise: opening bet or raise; integer amount with
  min_raise <= amount <= max_raise. An opening bet is sent as "raise".
- min_raise = opp_bet + max(s, 2), s = size of the last bet or raise on this
  street. No bet yet on a street: minimum opening bet is 2. Preflop the big blind
  counts as the first raise with s = 2, so the first preflop raise is to >= 4.
  Example: button raises 2 -> 6 (s = 4); big blind's minimum re-raise is to 10.
- max_raise = the all-in amount (most a player can have committed on the street;
  always equal for both players). If it is below the normal minimum,
  min_raise == max_raise and only the all-in is allowed.
- Cap: at most 4 bets or raises per street; preflop the big blind is the first,
  so at most 3 voluntary raises follow. At the cap only call or fold remain.
- raise can also be missing while raises_left > 0: when the opponent is all-in.
  ALWAYS choose from legal_actions.
- A round ends when both have acted and bets are equal, or on a fold. Preflop, if
  the button just calls, the big blind still has the option to check or raise.
- All-in and called: no more betting; remaining cards are dealt; the discard still
  happens; showdown. No action_request for streets without betting.

## Scoring and tournament
- Per hand: the winner wins the chips the loser committed.
- Match = 2 legs between the same bots. A leg plays every deal once: 200 deals
  (Stage 1) or 500 (Stage 2). Leg 2 replays the same deals with hole cards and
  seats swapped. Each leg is a FRESH bot process (init ... match_end).
- The bot with more total net chips over both legs wins. Win 1, draw 0.5, loss 0.
- Tie-break: sum over matches of clip(net, -C, C) / total hands.
  C = 400 in Stage 1, 1000 in Stage 2 (provisional).
- Forfeit (crash, time bank exhausted, a reply over 5 s, wall-clock kill, closed
  stdout): loss with net -C, opponent +C. If in leg 1, leg 2 is not played.
- Stage 1: Swiss, 6 rounds (7-8 if over 1000 teams), 400 hands per match.
  Top 32 -> Stage 2: full round robin, 1000 hands per match. Stage 2 alone
  decides prizes.

## Limits (provisional values may change; read them from init)
| Limit | Value |
| --- | --- |
| Language | Python 3.11; stdlib, numpy, scipy only |
| Submission | bot.py, or zip with bot.py at top level; <= 5 MB |
| Time bank | 30 s per leg (Stage 1), 75 s per leg (Stage 2); cumulative |
| Charged | from the moment a request is sent until the full reply line arrives |
| Per reply | 5 s |
| Start-up | the first 5 s after launch are not charged |
| Wall-clock kill | 90 s per leg (Stage 1), 225 s (Stage 2) |
| Resources | 1 vCPU, 1 GB RAM, no network, read-only filesystem |
| stderr | captured, first 64 KB per leg, never parsed |
Work done while handling non-request messages is effectively charged too: the
next request is usually already waiting and its clock is running.

## Protocol
- UTF-8, one JSON object per line, each with a "type" field.
- Engine -> bot on stdin. Bot -> engine on stdout, flushed after every line.
- A line written while a request is outstanding IS the reply (a debug print
  becomes a malformed reply and the real reply is ignored). Lines written when no
  request is outstanding are ignored.
- Ignore unknown message types and unknown fields.
- Cards: rank from 23456789TJQKA + suit from s h d c, e.g. "As", "Td", "2c".
- Streets: "preflop", "flop", "turn", "river". Actors: "me", "opp".

Engine -> bot:
- init: protocol_version "1.0", total_hands (per leg), starting_stack 200,
  small_blind 1, big_blind 2, time_bank_ms, per_response_ms
- new_hand: hand_id (1-indexed within the leg), seat "button"|"big_blind",
  hole_cards [3], stack, opp_stack
- action_request (REPLY): hand_id, street, board, pot (total, including bets on
  this street), my_bet, opp_bet, to_call, my_stack, opp_stack, legal_actions,
  min_raise and max_raise (only if raise is legal), raises_left, history,
  time_left_ms. history = all voluntary actions this hand, oldest first, blinds
  not listed: {"street":"flop","actor":"opp","action":"raise","amount":6};
  amount present for call and raise only.
- discard_request (REPLY): hand_id, hole_cards [3], board [3], pot, my_stack,
  opp_stack, time_left_ms
- discard_result: hand_id, my_discard, opp_discard, hole_cards [2 remaining]
- hand_result: hand_id, result "fold"|"showdown", net, board, my_hole_cards
  (3 if the hand ended before the discard), opp_hole_cards (2 cards at showdown,
  else null), opp_discard (or null), history
- notice: code "malformed"|"illegal_action"|"illegal_discard", applied
- match_end: reason "complete"|"opp_forfeit"|"forfeit". Exit after it.

Bot -> engine:
  {"type":"action","action":"fold"}
  {"type":"action","action":"check"}
  {"type":"action","action":"call"}
  {"type":"action","action":"raise","amount":40}
  {"type":"discard","card":"Kd"}

Corrections: an illegal or unparsable action becomes check if legal, else fold.
An illegal discard becomes the lowest-ranked hole card (ties by suit order
s, h, d, c). Each correction sends a notice. No reply at all is a timeout.

## Worked examples
Full hand (Problem Statement 8.1). A (button) Qh Jh 4c; B 9s 9d Kc.
Board Th 9h 2c / 3s / 5h.
- Preflop: A raises to 6, B calls. Pot 12.
- Flop: B checks; A bets 8 (sent as raise, amount 8); B raises to 24 (minimum
  was 8 + max(8, 2) = 16); A calls. Pot 60.
- Discard: A throws 4c (keeps flush and straight draws), B throws Kc (keeps
  three nines). A receives:
  {"type":"discard_result","hand_id":7,"my_discard":"4c","opp_discard":"Kc","hole_cards":["Qh","Jh"]}
- Turn 3s: B bets 40, A calls. Pot 140. River 5h: B checks, A bets 70, B calls.
- A's queen-high flush beats three nines. Net +140 for A.

Raising war (8.2): B posts 2; A raises to 6 (s=4, next min 10); B re-raises to 18
(s=12, next min 30); A raises to 50. Cap reached: B's legal_actions are
["fold","call"]. If B calls, pot 100, each has 150 behind.

All-in preflop (8.3): A shoves to 200 (max_raise), B calls. Flop dealt, no
betting, both still get discard_request, turn and river dealt, showdown.

## Local engine
py -3.11 starter\engine.py BOT_A BOT_B [--stage 1|2] [--hands N] [--seed S]
    [--log-dir DIR] [--verbose] [--no-time-limits] [--python PATH]
Same --seed = same deals. Summary printed at the end, for example:
  Seed 1 | 400 of 400 hands played (2 legs of 200)
    A  bot.py                      net    +477   time used   0.00 s (bank 30 s per leg)   notices 0
    B  example_bots/random_bot.py  net    -477   time used   0.00 s (bank 30 s per leg)   notices 0
  Result: A wins
  Capped delta: A +400, B -400 (C = 400)
Logs in DIR: match.log (one line per hand, prefixed L1/L2; actions x = check,
cN = call to N, rN = raise to N, f = fold) and A_leg1_stderr.txt etc.
tools\analyze_log.py already parses match.log.
Never judge timing with --no-time-limits.

## Conduct
- Our own code only; published algorithms are fine; no code from public bot
  repositories or other teams.
- No detecting duplicate deals, no information between legs, no interference
  with the engine, the sandbox or the other bot. Prize winners' code is reviewed.

## Two things the local engine taught us
- The clock for a request starts no earlier than 5 s after launch. A fast leg
  can finish inside those 5 s, and then the engine prints "time used 0.00 s".
  That is not our real thinking time. Use the bot's own SUMMARY line on stderr
  (think_s, max_reply_ms) via tools\timing_report.py.
- At showdown hand_result gives the opponent's 2 kept cards AND their discard,
  so all 3 of their original cards are known. After a fold nothing is shown.
