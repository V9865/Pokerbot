# Discard Hold'em pokerbot

A working bot for the Pokerbots competition plus everything Antigravity needs to
improve it. Full instructions: Pokerbot_Antigravity_Build_Kit.docx.

Quick start (Windows, from this folder):

    py -3.11 -m pip install numpy scipy
    py -3.11 tools\bundle.py
    py -3.11 tools\fuzz_protocol.py
    py -3.11 tools\run_matches.py --opps all --seeds 1-3 --tag check

The file to upload is dist\bot.py.

In Antigravity: open this folder, start a conversation and type
`/phase-0-verify` (or "Run the phase-0-verify skill.").

- AGENTS.md: always-on rules for the agent
- .agents\skills\: reference skills and the six phase skills
- memory\: project memory the agent reads first and keeps up to date
- src\: bot source; tools\: build and test tools; opponents\: test opponents
- starter\: the organisers' starter kit (engine.py); replace it if they publish an update
