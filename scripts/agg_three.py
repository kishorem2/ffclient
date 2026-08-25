import json, os
from collections import defaultdict
from pathlib import Path

from matchkey import mkey   # the key lives in matchkey.py now - same logic, do not fork it

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FF_DATA_DIR", ROOT / "data"))   # override for tests only
CONSENSUS = DATA / "consensus.json"

FP_WEIGHT = 2.0   # FantasyPros ECR = 111 experts; weighted double vs a single analyst
SRC_WEIGHT = {"Winks": 1.0, "Norris": 1.0, "FantasyPros": FP_WEIGHT}

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

# Live-API sidecar (fetch_live.py). Optional: without it the build is the
# original static three-source blend and the output is unchanged.
_mp = DATA / "fp_meta.json"
META = json.load(open(_mp)) if _mp.exists() else None


def _sans_suffix(key):
    """Match-key with the suffix component blanked - ONLY for decorating rows
    with Sleeper trending counts, never for merging identities. Used when both
    sides reduce to it uniquely, so Bijan/Brian Robinson (same pos+team, only
    the suffix apart) can never cross-match: they collide on the stripped key
    and uniqueness fails."""
    parts = key.split("|")
    if parts[0] == "DST":
        return key
    return "|".join((parts[0], parts[1], parts[3], parts[4]))


def attach_meta(fmt, universe):
    """Bolt ECR/rank_std/ADP and trending counts onto merged records, keyed by
    the same mkey the merge used. Trending is a decoration column - it NEVER
    touches ranks or the consensus average."""
    if not META:
        return
    players = META.get(fmt, {}).get("players", {})
    trends = {}
    for kind in ("add", "drop"):
        trends[kind] = dict(META.get("trending", {}).get(kind, {}))
    # suffixless fallback indexes (Sleeper spells some suffixed names without
    # the suffix); only used when unique on BOTH sides
    strip_rows = defaultdict(list)
    for k in universe:
        strip_rows[_sans_suffix(k)].append(k)
    for kind, counts in trends.items():
        strip_tr = defaultdict(list)
        for k in counts:
            strip_tr[_sans_suffix(k)].append(k)
        for key, rec in universe.items():
            c = counts.get(key)
            if c is not None:
                # An exact hit on a SUFFIXLESS key inside a multi-player strip
                # group is not safe: Sleeper spelling 'Brian Robinson' without
                # the Jr. produces exactly Bijan's key. A suffixED key can't be
                # spoofed that way (dropping a suffix never adds one).
                parts = key.split("|")
                has_suffix = parts[0] != "DST" and parts[2] != ""
                if not has_suffix and len(strip_rows[_sans_suffix(key)]) > 1:
                    c = None
            if c is None:
                s = _sans_suffix(key)
                if len(strip_rows[s]) == 1 and len(strip_tr.get(s, [])) == 1:
                    c = counts.get(strip_tr[s][0])
            if c is not None:
                rec["extras"][f"trend_{kind}"] = c
    for key, rec in universe.items():
        m = players.get(key)
        if not m:
            continue
        rec["extras"]["ecr"] = m.get("ecr")
        rec["extras"]["std"] = m.get("std")
        rec["extras"]["bye"] = m.get("bye")
        if m.get("adp") is not None and m.get("ecr") is not None:
            rec["extras"]["adp"] = m["adp"]
            # ECR minus ADP: negative = experts rank him better than the room
            # drafts him (value); positive = the room reaches for him.
            rec["extras"]["delta"] = m["ecr"] - m["adp"]

def aggregate(fmt):
    srcs = {k: load(v) for k, v in FILES[fmt].items()}
    sizes = {k: len(v) for k, v in srcs.items()}

    universe = {}
    for sname, rows in srcs.items():
        for r in rows:
            rec = universe.setdefault(r["key"], {
                "key": r["key"], "names": {}, "pos": r["pos"], "team": r["team"],
                "ranks": {}, "extras": {}
            })
            # prefer the longest (most complete) spelling of the name
            rec["names"][r["name"]] = rec["names"].get(r["name"], 0) + 1
            rec["ranks"][sname] = r["rank"]

    attach_meta(fmt, universe)

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
        row = {
            "name": display, "pos": rec["pos"], "team": rec["team"],
            "ranks": rec["ranks"], "avg": num / den,
            "best": min(real), "worst": max(real), "spread": max(real) - min(real),
            "n": len(real),
        }
        row.update(rec["extras"])
        out.append(row)

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

# Disagreement-flag threshold: 85th percentile among draft-relevant skill
# players, computed here once so the PDFs and the workbook can't drift apart.
# With live data, rank_std (dispersion across the full ~111-expert pool)
# replaces the 3-source spread as the flag signal.
import statistics
_pool = [r["spread"] for r in data["half"]["rows"][:200] if r["pos"] not in ("K", "DST")]
data["flag"] = {"spread": round(statistics.quantiles(_pool, n=20)[16])}
_stds = [r["std"] for r in data["half"]["rows"][:200]
         if r["pos"] not in ("K", "DST") and r.get("std") is not None]
if len(_stds) >= 20:
    data["flag"]["std"] = round(statistics.quantiles(_stds, n=20)[16], 1)
print("flag thresholds:", data["flag"])

if META:
    data["fp_info"] = {"last_updated": META["half"].get("last_updated"),
                       "experts": META["half"].get("total_experts")}

json.dump(data, open(CONSENSUS, "w"))
print("\nsaved")
