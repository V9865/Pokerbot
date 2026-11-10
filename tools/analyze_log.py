"""Find where our bot (seat A) wins and loses chips, from match.log files.

  py -3.11 tools\analyze_log.py runs\TAG [opponent_name] [--worst 20]
Groups every hand by how it ended and prints totals, then the worst hands.
"""
import glob, os, re, sys
args = [a for a in sys.argv[1:] if not a.startswith("--")]
worst_n = int(sys.argv[sys.argv.index("--worst") + 1]) if "--worst" in sys.argv else 20
base = args[0] if args else "runs"
opp = args[1] if len(args) > 1 else ""
LINE = re.compile(r"^(L\d) #(\d+)\s+button (\w) \| (.*) \| board (.*?)(?: \| discards (.*?))? \| (.*) \| (fold|showdown)(?: \((.*?)\))? (\w) ([+-]?\d+), (\w) ([+-]?\d+)$")
groups, hands = {}, []
files = sorted(glob.glob(os.path.join(base, "%s*" % opp, "match.log")))
for path in files:
    for line in open(path, encoding="utf-8"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        net = int(m.group(11)) if m.group(10) == "A" else int(m.group(13))
        acts = m.group(7).split()
        street = [a for a in acts if a.endswith(":")][-1][:-1]
        last = acts[-1]
        pos = "button" if m.group(3) == "A" else "big blind"
        if m.group(8) == "fold":
            how = "we folded" if last.startswith("A") else "they folded"
        else:
            cats = m.group(9) or ""
            how = "showdown"
            a_bets = sum(1 for a in acts if a.startswith("Ar"))
            b_bets = sum(1 for a in acts if a.startswith("Br"))
            how += " (we bet more)" if a_bets > b_bets else " (they bet more)" if b_bets > a_bets else " (even)"
        size = "small pot" if abs(net) <= 10 else "medium pot" if abs(net) <= 50 else "big pot"
        key = "%-26s %-9s %-10s %s" % (how, street, pos, size)
        g = groups.setdefault(key, [0, 0])
        g[0] += 1
        g[1] += net
        hands.append((net, os.path.basename(os.path.dirname(path)), line.strip()))
total = sum(h[0] for h in hands)
print("files: %d, hands: %d, our net: %+d (%.2f chips/hand)" % (len(files), len(hands), total, total / max(1, len(hands))))
print("\n%-60s %7s %9s %8s" % ("how the hand ended / last street / our seat / size", "hands", "net", "per hand"))
for key, (n, net) in sorted(groups.items(), key=lambda kv: kv[1][1]):
    print("%-60s %7d %+9d %+8.1f" % (key, n, net, net / n))
print("\nworst %d hands:" % worst_n)
for net, where, line in sorted(hands)[:worst_n]:
    print("%+5d %s | %s" % (net, where, line))
