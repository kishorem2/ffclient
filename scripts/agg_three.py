import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONSENSUS = DATA / "consensus.json"

FP_WEIGHT = 2.0   # FantasyPros ECR = 111 experts; weighted double vs a single analyst
SRC_WEIGHT = {"Winks": 1.0, "Norris": 1.0, "FantasyPros": FP_WEIGHT}

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

def norm_tokens(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"['\u2019.]", "", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return [t for t in s.split() if t]

def mkey(name, pos, team):
    """first-initial + surname + generational suffix + pos + team.

    The suffix is part of the identity, NOT noise. Bijan Robinson and Brian
    Robinson Jr. are both RB/ATL and both abbreviate to 'B. Robinson' - the
    'Jr.' is the only thing separating a top-5 pick from a handcuff. Stripping
    it silently merged them and deleted Bijan from the board.

    Surname is the last NON-suffix token, so 'L. Allen Jr.' still keys on
    'allen', not 'jr'. Team stays in the key to separate A.J. Brown from
    Amon-Ra St. Brown, and Travis Etienne Jr. (NO) from Trevor Etienne (CAR).
    """
    if pos == "DST":
        return f"DST|{team}"
    toks = norm_tokens(name)
    suffix = ""
    while toks and toks[-1] in SUFFIXES:
        suffix = toks[-1] + suffix
        toks = toks[:-1]
    if not toks:
        return None
    return f"{toks[0][0]}|{toks[-1]}|{suffix}|{pos}|{team}"

def load(path):
    """Load a source list. Hard-fails on any two players sharing a match key -
    that means the merge would silently overwrite one with the other."""
    out = []
    seen = {}
    for i, line in enumerate(open(DATA / path)):
        line = line.strip()
        if not line:
            continue
        name, pos, team = line.split("|")
        k = mkey(name, pos, team)
        if k in seen:
            raise SystemExit(
                f"KEY COLLISION in {path}: '{seen[k]}' and '{name}' both map to "
                f"'{k}'. Merging them would delete one player's ranks. Make the "
                f"key more specific before continuing.")
        seen[k] = name
        out.append({"name": name, "pos": pos, "team": team,
                    "rank": i + 1, "key": k})
    return out

FILES = {
    "half": {"Winks": "winks_half.txt", "Norris": "norris_half.txt", "FantasyPros": "fp_half.txt"},
    "ppr":  {"Winks": "winks_full.txt", "Norris": "norris_full.txt", "FantasyPros": "fp_ppr.txt"},
}

def aggregate(fmt):
    srcs = {k: load(v) for k, v in FILES[fmt].items()}
    sizes = {k: len(v) for k, v in srcs.items()}

    universe = {}
    for sname, rows in srcs.items():
        for r in rows:
            rec = universe.setdefault(r["key"], {
                "key": r["key"], "names": {}, "pos": r["pos"], "team": r["team"], "ranks": {}
            })
            # prefer the longest (most complete) spelling of the name
            rec["names"][r["name"]] = rec["names"].get(r["name"], 0) + 1
            rec["ranks"][sname] = r["rank"]

    out = []
    for rec in universe.values():
        num = den = 0.0
        for sname in srcs:
            r = rec["ranks"].get(sname)
            if r is None:
                r = sizes[sname] + 15          # omission penalty
            w = SRC_WEIGHT[sname]
            num += r * w
            den += w
        real = [v for v in rec["ranks"].values()]
        display = max(rec["names"], key=lambda n: (len(n), rec["names"][n]))
        out.append({
            "name": display, "pos": rec["pos"], "team": rec["team"],
            "ranks": rec["ranks"], "avg": num / den,
            "best": min(real), "worst": max(real), "spread": max(real) - min(real),
            "n": len(real),
        })

    for sname, rows in srcs.items():
        kept = sum(1 for r in out if sname in r["ranks"])
        if kept != len(rows):
            raise SystemExit(
                f"LOST PLAYERS: {sname} has {len(rows)} rows but only {kept} "
                f"survived the merge in '{fmt}'. {len(rows)-kept} were dropped.")

    out.sort(key=lambda r: (r["avg"], r["name"]))
    pc = defaultdict(int)
    for i, r in enumerate(out):
        r["overall"] = i + 1
        pc[r["pos"]] += 1
        r["posrank"] = pc[r["pos"]]
    return out, sizes

def break_blocks(seq, floor, frac, max_size):
    b = [0]
    for i in range(1, len(seq)):
        if seq[i]["avg"] - seq[i-1]["avg"] > max(floor, frac * seq[i-1]["avg"]):
            b.append(i)
    b.append(len(seq))
    changed = True
    while changed:
        changed = False
        new = [b[0]]
        for a, z in zip(b, b[1:]):
            if z - a > max_size:
                bi, bg = None, -1
                for i in range(a+1, z):
                    g = seq[i]["avg"] - seq[i-1]["avg"]
                    if g > bg: bg, bi = g, i
                if bi:
                    new.append(bi); changed = True
            new.append(z)
        b = sorted(set(new))
    return set(b[:-1])

data = {}
for fmt in ("half", "ppr"):
    rows, sizes = aggregate(fmt)
    bs = break_blocks(rows, 1.25, 0.055, 11)
    t = 0
    for i, r in enumerate(rows):
        if i in bs: t += 1
        r["tier"] = t
    for pos in ("QB","RB","WR","TE","K","DST"):
        grp = [r for r in rows if r["pos"] == pos]
        pbs = break_blocks(grp, 2.5, 0.055, 7)
        pt = 0
        for i, r in enumerate(grp):
            if i in pbs: pt += 1
            r["ptier"] = pt
    data[fmt] = {"rows": rows, "sizes": sizes}
    print(f"{fmt}: {len(rows)} players, {t} overall tiers, sizes={sizes}")

    matched3 = sum(1 for r in rows if r["n"] == 3)
    matched1 = [r for r in rows if r["n"] == 1 and r["overall"] <= 200]
    print(f"   matched by all three: {matched3}")
    if matched1:
        print("   WARNING single-source inside top 200 (possible name mismatch):")
        for r in matched1[:20]:
            print(f"      #{r['overall']} {r['name']} {r['pos']} {r['team']} -> {r['ranks']}")

json.dump(data, open(CONSENSUS, "w"))
print("\nsaved")
