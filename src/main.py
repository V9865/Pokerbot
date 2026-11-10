"""Entry point: the safe message loop. One flushed JSON line per request."""
import sys
import json
from safety import send, log, fallback_action, fallback_discard, sanitize_action, sanitize_discard
from strategy import Brain


def summary(brain, why):
    g = brain.gov
    log("SUMMARY %s hands=%d think_s=%.2f max_reply_ms=%.1f modes=%s errors=%d notices=%d fold_to_bet=%.2f aggr=%.2f" % (
        why, brain.hand_id, g.total_ms / 1000.0, g.max_reply_ms, g.mode_counts, brain.errors, brain.notices,
        brain.opp.fold_to_bet(), brain.opp.aggression()))


def main():
    brain = Brain()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue
        t = msg.get("type")
        if t == "action_request":
            try:
                reply = sanitize_action(brain.decide(msg), msg)
            except Exception as e:
                brain.errors += 1
                log("ERR action", repr(e))
                reply = fallback_action(msg)
            send(reply)
            brain.gov.done()
        elif t == "discard_request":
            try:
                reply = sanitize_discard(brain.discard(msg), msg)
            except Exception as e:
                brain.errors += 1
                log("ERR discard", repr(e))
                reply = fallback_discard(msg)
            send(reply)
            brain.gov.done()
        elif t == "match_end":
            break
        else:
            try:
                brain.observe(msg)
            except Exception as e:
                brain.errors += 1
                log("ERR observe", repr(e))
    summary(brain, "end")


if __name__ == "__main__":
    main()
