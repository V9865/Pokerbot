"""Checks strategy.read_history against real engine requests: the pot we
reconstruct from the action history must equal the pot the engine reports.

  py -3.11 tools\test_history.py
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
d = os.path.join(ROOT, "runs", "history_test")
os.makedirs(d, exist_ok=True)
rec = os.path.join(ROOT, "opponents", "recorder.py")
subprocess.run([sys.executable, os.path.join(ROOT, "starter", "engine.py"), rec, os.path.join(ROOT, "opponents", "maniac.py"),
                "--seed", "5", "--hands", "60", "--log-dir", d], capture_output=True)
import strategy                                              # noqa: E402


def replay_pot(history, seat):
    my, op = (1, 2) if seat == "button" else (2, 1)
    pot, street = 3, "preflop"
    for e in history:
        if e["street"] != street:
            street, my, op = e["street"], 0, 0
        amt = e.get("amount")
        if e["actor"] == "me":
            if e["action"] in ("raise", "call"):
                amt = op if amt is None else amt
                pot += amt - my
                my = amt
        elif e["action"] in ("raise", "call"):
            amt = my if amt is None else amt
            pot += amt - op
            op = amt
    return pot, my, op


n = bad = 0
for leg in (1, 2):
    p = os.path.join(d, "A_leg%d_stderr.txt" % leg)
    for line in open(p, encoding="utf-8", errors="replace"):
        if not line.startswith("REQ "):
            continue
        try:
            o = json.loads(line[4:])
        except ValueError:
            continue                                        # line cut off at the 64 KB stderr limit
        req, seat = o["req"], o["seat"]
        pot, my, op = replay_pot(req["history"], seat)
        same_street = not req["history"] or req["history"][-1]["street"] == req["street"]
        exp_my, exp_op = (my, op) if same_street else (0, 0)
        if req["street"] == "preflop" or same_street:
            ok = pot == req["pot"] and exp_my == req["my_bet"] and exp_op == req["opp_bet"]
        else:
            ok = pot == req["pot"]
        x, pf = strategy.read_history(req["history"], seat, strategy.OppModel())
        ok = ok and 0.0 < x <= 1.0
        n += 1
        if not ok:
            bad += 1
            if bad <= 3:
                print("MISMATCH", seat, "replayed", pot, my, op, "engine", req["pot"], req["my_bet"], req["opp_bet"], req["history"][-3:])
print("requests checked: %d, mismatches: %d" % (n, bad))
print("RESULT:", "OK" if n > 50 and not bad else "FAILED")
sys.exit(0 if n > 50 and not bad else 1)
