---
name: phase-5-submit
description: Phase 5 of the pokerbot build (update 1) - the final audit and the submission build, choosing between the trained versions and v1 by head-to-head and friend's-bot results. Bug fixes only. Use when the user says to run phase 5, to finalise, or to prepare the final upload.
---
# Phase 5: final audit and submission (about 1 hour; bug fixes only)

1. Follow the rules-audit skill in this fresh conversation. Fix every FAIL
   (safety only), then repeat the audit until ALL PASS.
2. `py -3.11 tools\bundle.py` and confirm POLICY and PARAMS in dist\bot.py are
   the accepted ones (no --set or --params variant is ever uploaded).
3. Run the pre-upload checklist in bot-safety section 6, printing PASS or FAIL
   with evidence for each item.
4. Choose the version. Candidates: the newest accepted snapshot and v1.
   Play both on fresh seeds 9000-9039 against: each other, friend, gto_like,
   ai_typical_v2, exploiter2 and ai_typical (held-out), and 10 seeds against
   the rest of the zoo. Pick the newest only if it beats v1 head-to-head AND
   does at least as well against friend and both held-out opponents; else
   submit v1 (or the best earlier snapshot). State which and why.
5. Stage 2 check on the chosen file: timing_report --stage 2 and 3 Stage 2
   matches against friend, gto_like and exploiter. Safety gate clean.
6. Copy the chosen file to snapshots\final_bot.py; record in memory its size
   and SHA-256 (`certutil -hashfile snapshots\final_bot.py SHA256`), Status:
   FINAL; commit "final"; `git tag submission-final`.

Tell the user the exact file to upload (named bot.py), its size, and to
confirm on Unstop that the upload shows as valid.
