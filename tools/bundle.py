"""Bundle src/ into ONE file: dist/bot.py (the file we upload).

Modules are concatenated in dependency order; lines importing project modules
are removed. Fails on forbidden names or duplicate top-level definitions.
Usage: py -3.11 tools\bundle.py [output_path] [--set NAME=VALUE ...]
--set builds a VARIANT with config values overridden, for A/B tests, e.g.
  py -3.11 tools\bundle.py runs\variants\bluff20.py --set BLUFF_FLOP=0.20
  py -3.11 tools\run_matches.py --bot runs\variants\bluff20.py --opps snapshots\v1_bot.py --seeds 1-40 --tag bluff20
Never upload a variant; change src\config.py and rebuild dist\bot.py instead.
"""
import ast, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ["config", "cards", "evaluator", "preflop_table", "safety", "equity", "ranges", "features", "strategy", "main"]
# add new modules to ORDER after everything they import (e.g. "ranges", "opponent" before "strategy")
FORBIDDEN = ["socket", "subprocess", "threading", "multiprocessing", "os.system", "urllib", "requests", "open("]


def main():
    argv = sys.argv[1:]
    sets = []
    while "--set" in argv:
        i = argv.index("--set")
        sets.append(argv[i + 1])
        del argv[i:i + 2]
    out = argv[0] if argv else os.path.join(ROOT, "dist", "bot.py")
    if sets and os.path.abspath(out) == os.path.join(ROOT, "dist", "bot.py"):
        sys.exit("--set builds test variants only; give an output path under runs\\variants")
    src = os.path.join(ROOT, "src")
    extra = [f[:-3] for f in os.listdir(src) if f.endswith(".py") and f[:-3] not in ORDER]
    if extra:
        sys.exit("modules missing from ORDER in tools/bundle.py: %s" % extra)
    pat = re.compile(r"^\s*(from\s+(%s)\s+import\b.*|import\s+(%s)\s*)$" % ("|".join(ORDER), "|".join(ORDER)))
    parts = ['"""Discard Hold\'em bot - bundled from src/ by tools/bundle.py. Do not edit."""\n']
    seen = {}
    for name in ORDER:
        text = open(os.path.join(src, name + ".py"), encoding="utf-8").read()
        for node in ast.parse(text).body:
            names = []
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for n in names:
                if n in seen and seen[n] != name and not n.startswith("_") and n not in ("np", "HAVE_NP"):
                    sys.exit("duplicate top-level name %r in %s and %s" % (n, seen[n], name))
                seen.setdefault(n, name)
        body = [l for l in text.splitlines() if not pat.match(l)]
        while body and body[-1].strip() in ("main()", 'if __name__ == "__main__":'):
            body.pop()
        parts.append("\n# " + "=" * 20 + " " + name + " " + "=" * 20 + "\n" + "\n".join(body) + "\n")
        if name == "config":
            for kv in sets:
                k, v = kv.split("=", 1)
                parts.append("assert %r in CFG, 'unknown config name %s'\nCFG[%r] = %s\n" % (k, k, k, v))
    parts.append('\n\nif __name__ == "__main__":\n    main()\n')
    code = "".join(parts)
    ast.parse(code)
    hits = [w for w in FORBIDDEN if w in code]
    if hits:
        sys.exit("forbidden names in bundle: %s" % hits)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("wrote %s (%d bytes, limit 5,000,000)" % (out, len(code.encode("utf-8"))))


if __name__ == "__main__":
    main()
