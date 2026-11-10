# Update 1: trained policy (apply once)

Instructions for the agent. The user says "Apply UPDATE_1.md".

1. Delete these old phase skills (replaced by this update):
   .agents\skills\phase-2-ranges, .agents\skills\phase-3-exploits,
   .agents\skills\phase-4-tune
2. Check that these files from the update are present (the user copied them):
   .agents\skills\phase-2-features\SKILL.md, phase-3-policy, phase-4-train,
   phase-5-submit (replaces the old one), training-method.
3. In AGENTS.md, replace the line listing phase skills with:
   "Phases are skills: phase-0-verify, phase-1-harden, phase-2-features,
   phase-3-policy, phase-4-train, phase-5-submit. Do one phase per
   conversation, in order, and stop at its checkpoint. The trained policy is
   described in the skill training-method."
   Also in "Hard rules" rule 2 keep the budget, and add rule 11:
   "11. Never upload a variant built with --set or --params. Only dist\bot.py
   built from src\ after a stage is accepted."
4. Append to memory\PROJECT_MEMORY.md (do not overwrite anything):
   - Status: v1 lost heavily to the user's friend's bot (11 Nov, no log kept).
   - Next step: phase-2-features Step 0 (friend's bot diagnosis).
   - Decisions, dated 2026-11-10, by the user:
     * hybrid plan: keep the safety shell and the math core; replace the
       if/else decision layer with a trained, EV-structured policy
       (training-method skill). No full rebuild (solver or deep RL rejected
       as too risky before the deadline).
     * the friend's bot is available and becomes a training and test opponent
       (weight 3 of about 25; overfitting guarded by held-out opponents).
     * laptop: 8+ cores, can train overnight.
     * final upload by 12-13 Nov; stages C and D of training are optional.
   - Create memory\TRAINING_LOG.md with a one-line header.
5. In .agents\skills\match-testing\SKILL.md, add friend, exploiter and
   exploiter2 to the zoo table, and a line: "Head-to-head against the
   previous snapshot and the result against friend are the two main measures
   of progress."
6. Commit: "update 1: trained policy plan". Then delete UPDATE_1.md and
   commit again.
Report what was changed.
