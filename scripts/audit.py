import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
D = json.load(open(DATA / "consensus.json"))
FILES = {
    "half": {"Winks": "winks_half.txt", "Norris": "norris_half.txt", "FantasyPros": "fp_half.txt"},
    "ppr":  {"Winks": "winks_full.txt", "Norris": "norris_full.txt", "FantasyPros": "fp_ppr.txt"},
}

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"['\u2019.]", "", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

SUF = {"jr","sr","ii","iii","iv","v"}
def surname(name):
    p = [t for t in norm(name).split() if t not in SUF]
    return p[-1] if p else ""

problems = 0

# ---------------------------------------------------------------- A. round trip
print("=" * 66)
print("A. ROUND TRIP - every source row must appear with its rank intact")
print("=" * 66)
for fmt, srcs in FILES.items():
    rows = D[fmt]["rows"]
    for sname, path in srcs.items():
        # rank -> output record, for this source
        by_rank = {}
        for r in rows:
            if sname in r["ranks"]:
                v = r["ranks"][sname]
                if v in by_rank:
                    print(f"  !! {fmt}/{sname}: rank {v} claimed by both "
                          f"'{by_rank[v]['name']}' and '{r['name']}'")
                    problems += 1
                by_rank[v] = r
        missing = []
        mismatch = []
        for i, line in enumerate(open(DATA / path)):
            line = line.strip()
            if not line: continue
            nm, pos, team = line.split("|")
            rank = i + 1
            rec = by_rank.get(rank)
            if rec is None:
                missing.append((rank, nm, pos, team)); continue
            name_ok = True if pos == "DST" else surname(rec["name"]) == surname(nm)
            if rec["pos"] != pos or rec["team"] != team or not name_ok:
                mismatch.append((rank, nm, pos, team, rec["name"], rec["pos"], rec["team"]))
        tag = f"{fmt}/{sname}"
        if missing:
            problems += len(missing)
            print(f"  MISSING from {tag}: {len(missing)}")
            for m in missing[:20]: print("     rank", m)
        if mismatch:
            problems += len(mismatch)
            print(f"  MISMATCH in {tag}: {len(mismatch)}")
            for m in mismatch[:20]: print("     ", m)
        if not missing and not mismatch:
            print(f"  ok  {tag:<22} all {rank} rows present and consistent")

# ------------------------------------------------- B. failed-merge suspects
print()
print("=" * 66)
print("B. SPLIT SUSPECTS - two records that may be the same human")
print("=" * 66)
for fmt in ("half", "ppr"):
    rows = D[fmt]["rows"]
    groups = defaultdict(list)
    for r in rows:
        if r["pos"] == "DST": continue
        groups[(surname(r["name"]), r["pos"])].append(r)
    hits = 0
    for (sn, pos), grp in sorted(groups.items()):
        if len(grp) < 2: continue
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                a, b = grp[i], grp[j]
                sa, sb = set(a["ranks"]), set(b["ranks"])
                disjoint = not (sa & sb)
                same_team = a["team"] == b["team"]
                init_a = norm(a["name"])[0]
                init_b = norm(b["name"])[0]
                # disjoint sources = classic failed merge. same team = extra suspicious.
                if disjoint and (same_team or init_a == init_b):
                    hits += 1; problems += 1
                    print(f"  SUSPECT {fmt}: '{a['name']}' {a['pos']} {a['team']} {sorted(sa)} "
                          f"vs '{b['name']}' {b['pos']} {b['team']} {sorted(sb)}")
                elif same_team and init_a == init_b:
                    print(f"  note {fmt}: same team+initial+surname, sources overlap so "
                          f"they are distinct: '{a['name']}' / '{b['name']}' ({a['pos']} {a['team']})")
    if not hits:
        print(f"  ok  {fmt}: no disjoint-source same-surname pairs")

# ------------------------------------------- C. team disagreement across sources
print()
print("=" * 66)
print("C. TEAM CONFLICTS - same player listed on different teams would split")
print("=" * 66)
for fmt, srcs in FILES.items():
    seen = defaultdict(lambda: defaultdict(list))
    for sname, path in srcs.items():
        for line in open(DATA / path):
            line = line.strip()
            if not line: continue
            nm, pos, team = line.split("|")
            if pos == "DST": continue
            n = norm(nm)
            seen[(n[0] if n else "", surname(nm), pos)][sname].append((nm, team))
    conflicts, ambiguous = [], []
    for k, per_src in seen.items():
        if any(len(v) > 1 for v in per_src.values()):
            ambiguous.append((k, per_src)); continue
        teams = {v[0][1] for v in per_src.values()}
        if len(teams) > 1:
            conflicts.append((k, per_src))
    for k, v in conflicts:
        print(f"  CONFLICT {fmt}: {k} -> " +
              ", ".join(f"{s}={x[0][1]}" for s, x in v.items()))
        problems += 1
    for k, v in ambiguous:
        names = {x[0] for lst in v.values() for x in lst}
        teams = {x[1] for lst in v.values() for x in lst}
        print(f"  ambiguous {fmt}: {k[1]} {k[2]} covers {sorted(names)} on {sorted(teams)}"
              f" - distinct players, separated by suffix+team in the real key")
    if not conflicts:
        print(f"  ok  {fmt}: no source disagrees on any player's team")

# ---------------------------------------------------------- D. thin coverage
print()
print("=" * 66)
print("D. COVERAGE - where the single-source players actually sit")
print("=" * 66)
for fmt in ("half", "ppr"):
    rows = D[fmt]["rows"]
    ones = [r for r in rows if r["n"] == 1]
    twos = [r for r in rows if r["n"] == 2]
    print(f"  {fmt}: {len(rows)} total | 3 sources {sum(1 for r in rows if r['n']==3)} "
          f"| 2 sources {len(twos)} | 1 source {len(ones)}")
    worst = min([r["overall"] for r in ones], default=None)
    print(f"        highest-ranked single-source player: #{worst}")
    early2 = [r for r in twos if r["overall"] <= 100]
    if early2:
        print(f"        two-source players inside top 100 ({len(early2)}):")
        for r in early2: print(f"           #{r['overall']:<4}{r['name']:<22}{sorted(r['ranks'])}")

print()
print("=" * 66)
print(f"TOTAL PROBLEMS: {problems}")
print("=" * 66)
