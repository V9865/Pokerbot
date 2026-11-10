"""Protocol fuzz test: feeds a bot random but valid requests plus junk and checks
that every reply is one legal JSON line, in time, and that the bot exits cleanly.

  py -3.11 tools\fuzz_protocol.py [bot_path] [hands] [max_reply_ms] [--no-numpy]
--no-numpy tests the degraded mode: it fuzzes a copy of the bot (written under
runs\) in which numpy cannot be imported.
"""
import json, os, queue, random, subprocess, sys, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_NUMPY = "--no-numpy" in sys.argv
_args = [a for a in sys.argv[1:] if a != "--no-numpy"]
bot = os.path.abspath(_args[0] if _args else os.path.join(ROOT, "dist", "bot.py"))
HANDS = int(_args[1]) if len(_args) > 1 else 1500
MAX_MS = float(_args[2]) if len(_args) > 2 else 250.0
if NO_NUMPY:
    os.makedirs(os.path.join(ROOT, "runs"), exist_ok=True)
    copy = os.path.join(ROOT, "runs", "nonumpy_bot.py")
    with open(copy, "w", encoding="utf-8") as f:
        f.write("import sys; sys.modules['numpy'] = None\n" + open(bot, encoding="utf-8").read())
    bot = copy
    print("no-numpy mode: fuzzing", copy)
DECK = [r + s for r in "23456789TJQKA" for s in "shdc"]
JUNK = ["", "   ", "not json", "[1, 2, 3]", '{"type": "mystery", "x": 1}', '{"no_type": true}', "{bad json",
        '{"type": "notice", "code": "illegal_action", "applied": "check"}', '"just a string"', "42"]
random.seed(2026)
p = subprocess.Popen([sys.executable, bot], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, cwd=os.path.dirname(os.path.abspath(bot)))
q = queue.Queue()
threading.Thread(target=lambda: [q.put(l) for l in p.stdout] and None, daemon=True).start()
err = []
threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True).start()
fails = {}
worst = 0.0
n_req = 0


def fail(kind, detail):
    fails.setdefault(kind, []).append(detail)


def tell(msg):
    try:
        p.stdin.write(((msg if isinstance(msg, str) else json.dumps(msg)) + "\n").encode())
        p.stdin.flush()
    except OSError:
        time.sleep(0.3)
        print("FAIL bot process died. Last stderr:\n" + (err[0] if err else b"").decode("utf-8", "replace")[-1500:])
        print("RESULT: FAILED")
        sys.exit(1)


def ask(req, first=False):
    global worst, n_req
    n_req += 1
    req["future_field"] = {"ignore": "me"}
    t = time.perf_counter()
    tell(req)
    try:
        line = q.get(timeout=10)
    except queue.Empty:
        fail("no reply", req["type"])
        return None
    ms = (time.perf_counter() - t) * 1000
    if not first:
        worst = max(worst, ms)
        if ms > MAX_MS:
            fail("slow", "%.0f ms on %s %s" % (ms, req["type"], req.get("street")))
    try:
        r = json.loads(line)
    except ValueError:
        fail("not json", line[:80])
        return None
    if req["type"] == "action_request":
        a = r.get("action")
        if r.get("type") != "action" or a not in req["legal_actions"]:
            fail("illegal action", "%s not in %s" % (r, req["legal_actions"]))
        elif a == "raise" and not (isinstance(r.get("amount"), int) and req["min_raise"] <= r["amount"] <= req["max_raise"]):
            fail("illegal amount", "%s range %s-%s" % (r, req["min_raise"], req["max_raise"]))
        elif a == "fold" and "check" in req["legal_actions"]:
            fail("fold when check legal", str(r))
    else:
        if r.get("type") != "discard" or r.get("card") not in req["hole_cards"]:
            fail("illegal discard", "%s not in %s" % (r, req["hole_cards"]))
    return r


def action_req(hid, street, board, hist, left):
    pot = random.randint(3, 400)
    committed = random.randint(0, 198)
    my_stack = 200 - committed
    facing = random.random() < 0.55
    opp_bet = random.randint(2, max(2, my_stack)) if facing else 0
    my_bet = random.randint(0, max(0, opp_bet - 1)) if facing else 0
    to_call = opp_bet - my_bet
    legal = ["fold", "call"] if to_call > 0 else ["check"]
    req = {"type": "action_request", "hand_id": hid, "street": street, "board": board, "pot": pot,
           "my_bet": my_bet, "opp_bet": opp_bet, "to_call": to_call, "my_stack": my_stack,
           "opp_stack": random.randint(0, 200), "legal_actions": legal,
           "raises_left": random.randint(0, 4), "history": list(hist), "time_left_ms": left}
    if random.random() < 0.7:
        hi = my_bet + my_stack
        lo = min(hi, opp_bet + random.choice([2, 2, 4, 10, 40]))
        if hi >= 1:
            req["legal_actions"] = legal + ["raise"]
            req["min_raise"], req["max_raise"] = lo, hi
    return req


tell({"type": "init", "protocol_version": "1.0", "total_hands": HANDS, "starting_stack": 200,
      "small_blind": 1, "big_blind": 2, "time_bank_ms": 30000, "per_response_ms": 5000})
first = True
for hid in range(1, HANDS + 1):
    left = random.choice([30000, 30000, 30000, 9000, 4000, 1500, 300])     # exercises every time mode
    cards = random.sample(DECK, 11)
    hole, opp, board = cards[:3], cards[3:6], cards[6:]
    seat = random.choice(["button", "big_blind"])
    if random.random() < 0.03:
        tell(random.choice(JUNK))
    if random.random() > 0.01:                       # sometimes the new_hand message is "lost"
        tell({"type": "new_hand", "hand_id": hid, "seat": seat, "hole_cards": hole, "stack": 200, "opp_stack": 200})
    hist = []
    for street, nb in (("preflop", 0), ("flop", 3), ("turn", 4), ("river", 5)):
        if street == "turn":
            if random.random() < 0.9:
                r = ask({"type": "discard_request", "hand_id": hid, "hole_cards": hole, "board": board[:3],
                         "pot": random.randint(4, 400), "my_stack": random.randint(0, 198),
                         "opp_stack": random.randint(0, 198), "time_left_ms": left})
                mine = r.get("card") if r and r.get("card") in hole else hole[0]
            else:
                mine = hole[0]
            hole = [c for c in hole if c != mine]
            tell({"type": "discard_result", "hand_id": hid, "my_discard": mine, "opp_discard": opp[0], "hole_cards": hole})
        for _ in range(random.choice([0, 1, 1, 2, 3])):
            if random.random() < 0.02:
                tell(random.choice(JUNK))
            who = random.choice(["me", "opp"])
            act = random.choice(["check", "call", "raise", "raise"])
            e = {"street": street, "actor": who, "action": act}
            if act != "check":
                e["amount"] = random.randint(2, 200)
            r = ask(action_req(hid, street, board[:nb], hist, left), first)
            first = False
            hist.append(e)
        if random.random() < 0.15:
            break
    tell({"type": "hand_result", "hand_id": hid, "result": random.choice(["fold", "showdown"]),
          "net": random.randint(-200, 200), "board": board, "my_hole_cards": hole,
          "opp_hole_cards": random.choice([None, opp[1:]]), "opp_discard": random.choice([None, opp[0]]), "history": hist})
tell({"type": "match_end", "reason": "complete"})
try:
    p.wait(timeout=3)
    exited = True
except subprocess.TimeoutExpired:
    exited = False
    p.kill()
    fail("no exit after match_end", "")
time.sleep(0.2)
if not q.empty():
    fail("extra output", "bot wrote lines when no request was outstanding")
stderr = (err[0] if err else b"").decode("utf-8", "replace")
if "Traceback" in stderr:
    fail("traceback on stderr", stderr[-300:])
n_err = stderr.count("ERR ")
# EOF exit
p2 = subprocess.Popen([sys.executable, bot], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
p2.stdin.close()
try:
    p2.wait(timeout=5)
except subprocess.TimeoutExpired:
    p2.kill()
    fail("no exit on EOF", "")
print("requests: %d, worst reply: %.1f ms, caught errors logged by the bot: %d" % (n_req, worst, n_err))
if n_err:
    print("first error lines:", [l for l in stderr.splitlines() if l.startswith("ERR ")][:5])
for k, v in fails.items():
    print("FAIL %-22s x%d  e.g. %s" % (k, len(v), v[0]))
print("RESULT:", "OK" if not fails else "FAILED")
sys.exit(1 if fails else 0)
