---
name: phase-1-harden
description: Phase 1 of the pokerbot build - learn the existing code, add decision unit tests, run Stage 2 length matches and an independent audit, so later phases cannot silently break the bot. Use when the user says to run phase 1 or to harden the bot.
---
# Phase 1: harden (about 1 hour, no strategy changes)

Read first: bot-safety, match-testing, and all of src\ (about 900 lines, excluding the generated table).

1. Write a 15-line code map into memory\PROJECT_MEMORY.md under Facts: what each
   module and each Brain method does, and where Phase 2 and 3 will plug in.
2. tools\test_strategy.py: unit tests that drive strategy.Brain directly with
   hand-written messages (new_hand, action_request, discard_request,
   discard_result). Each test asserts on the sanitized reply. Cover at least:
   - never folds when check is legal; never folds the button for 1 chip
   - a pair of aces + any card: raises preflop, and calls an all-in
   - 7-2-2 type hands fold to a large preflop raise
   - river: holding the nuts facing a bet -> raise or call, never fold
   - river: holding nothing facing a pot-size bet -> fold
   - river: checked to with a strong hand -> bet; amount within the legal range
   - raise not in legal_actions (opponent all-in) -> only call or fold
   - min_raise == max_raise (short all-in) -> a raise uses exactly that amount
   - discard: K-7-7 on 7-4-2 keeps the sevens; A-7s-6s on Ks-9s-2c keeps the
     flush draw or the choice is within 0.01 equity; discard while all-in works
   - a request with no prior new_hand -> a legal fallback reply, no crash
   - PANIC mode (time_left_ms = 500) returns legal replies in under 5 ms
   Run it under both numpy and no-numpy.
3. Stage 2 length: `py -3.11 tools\run_matches.py --opps maniac,gto_like,ai_typical_v2 --seeds 1-3 --stage 2 --tag phase1_s2`
   Safety gate must be clean.
4. `py -3.11 tools\fuzz_protocol.py dist\bot.py 5000`
5. Follow the rules-audit skill yourself and fix every FAIL (safety fixes only).
6. Rebuild; confirm the bot's decisions did not change: head-to-head against
   snapshots\v1_bot.py over 10 seeds should be close to zero.
7. Update memory; commit "phase 1: hardened".

Stop and report: the tests added and their results, the audit list, the Stage 2
table and timing. If src\ changed, copy dist\bot.py to snapshots\v1b_bot.py and
tell the user it can be uploaded.
