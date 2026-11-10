---
name: rules-audit
description: Independent audit of the Discard Hold'em bot against the competition rules, the protocol and the safety checklist. Use in a fresh conversation after each phase and before every upload; it reports findings and does not change strategy.
---
# Rules audit

Act as a reviewer who did not write this bot. Find anything that could cause a
forfeit, a notice, a disqualification or a rule breach. Report; do not refactor.
Start a NEW conversation for this so earlier work does not bias the review.

Read first: the skills discard-holdem-rules and bot-safety. Then read every file
in src\ and the bundled dist\bot.py.

Report PASS or FAIL with file and line for each:
1. Only protocol JSON reaches stdout; sys.stdout is redirected; every reply is
   flushed; exactly one reply per request; no reply to other messages.
2. Every action reply passes through sanitize_action: legal action only; raise
   amount an int within [min_raise, max_raise]; never fold when check is legal.
3. Every discard reply names one of the 3 hole cards in the request.
4. Every decision path is inside try/except with a fallback reply.
5. Unknown types and fields, blank lines and invalid JSON are ignored.
6. The process exits on match_end and on end of input.
7. Time: the governor uses time_left_ms; no unbounded loops; observe() is
   cheap; start-up under 2 s.
8. Imports: stdlib, numpy, scipy only. No file access, sockets, subprocesses,
   threads, multiprocessing or network code in src\ or dist\bot.py.
9. Nothing persists or passes information between legs; nothing tries to
   detect duplicate deals.
10. Raise amounts are "to" amounts (street totals), never increments.
11. The discard is answered when all-in, and with either 2 or 3 cards in hand
    the code never indexes past what it holds.
12. Python 3.11 compatible; numpy calls exist in numpy 1.24+.
13. The bot runs without numpy (bot-safety section 4).
14. dist\bot.py equals a fresh bundle of src\ (bundle to runs\audit_bot.py and
    compare).
Then run the pre-upload checklist in bot-safety section 6 and report each item.
End with the FAIL items in priority order, or "ALL PASS".
