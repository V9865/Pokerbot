---
name: phase-5-submit
description: Phase 5 of the pokerbot build - the final audit and the submission build. Bug fixes only. Use when the user says to run phase 5, to finalise, or to prepare the final upload.
---
# Phase 5: final audit and submission (about 45 minutes; bug fixes only)

1. Follow the rules-audit skill in this fresh conversation. Fix every FAIL
   (safety only), then repeat the audit until ALL PASS.
2. `py -3.11 tools\bundle.py`
3. Run the full pre-upload checklist in bot-safety section 6 and print each
   item with PASS or FAIL and the evidence.
4. Final matches with the final dist\bot.py:
   - every zoo bot and exploiter, seeds 1-10, Stage 1
   - the previous snapshot, seeds 1-20 (should be about even if nothing changed)
   - gto_like and maniac, seeds 1-3, Stage 2
   Safety gate clean on all of them.
5. Choose the version to submit: the newest snapshot that passed every gate. If
   the newest one failed anything, submit the previous one. State which and why.
6. Copy it to snapshots\final_bot.py; update memory (Status: FINAL, the file's
   size and SHA-256 from `certutil -hashfile snapshots\final_bot.py SHA256`);
   commit "final"; `git tag submission-final`.

Tell the user the exact file to upload (rename to bot.py if the portal requires
that name), its size, and remind them to confirm on Unstop that the upload was
accepted as valid.
