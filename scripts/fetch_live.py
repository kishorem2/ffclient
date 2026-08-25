"""Live refresh: FantasyPros rankings + ADP and Sleeper trending -> data/.

Everything goes through fpapi's cache and budget. A full rankings refresh is
4 FantasyPros requests on a cold cache (1 of which is the verify probe),
0 on a warm one:

    python3 scripts/fetch_live.py                # rankings + ADP + sleeper
    python3 scripts/fetch_live.py --news --projections   # the other 3 of the 7-request plan
    python3 scripts/fetch_live.py --force        # ignore today's cache (spends budget!)
    python3 scripts/fetch_live.py --no-sleeper

Writes:
  data/fp_half.txt / fp_ppr.txt   Name|POS|TEAM in ECR order, the FULL list
                                  (~590 - the old top-300 cap was a
                                  transcription limit, not an API one)
  data/fp_meta.json               per-player sidecar keyed by mkey():
                                  ECR, rank_std, ADP, bye, ownership, plus
                                  Sleeper trending add/drop counts. Consumed
                                  by agg_three for the new columns. Trending
                                  is attention, not value - it decorates the
                                  sheets and NEVER enters the consensus.

Run the pipeline (agg_three -> fix_names -> build_four -> build_xlsx3) and
scripts/audit.py after this, and confirm Bijan Robinson is still RB2 in both
formats - live data changes the sources, and the audit is the safety net.
"""
import json, os, sys, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpapi
from matchkey import mkey

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FF_DATA_DIR", ROOT / "data"))

KEEP_POS = {"QB", "RB", "WR", "TE", "K", "DST"}

# Normalize other services' team codes to this repo's convention (the codes
# already used in data/*.txt - FantasyPros style: JAC, LAR, LAC, WAS, LV).
TEAM_FIX = {"JAX": "JAC", "WSH": "WAS", "LA": "LAR", "OAK": "LV", "SD": "LAC",
            "STL": "LAR", "HST": "HOU", "BLT": "BAL", "CLV": "CLE", "ARZ": "ARI"}


def team(code):
    code = (code or "FA").upper()
    return TEAM_FIX.get(code, code)


def fp_players(api_json):
    """FP consensus-rankings JSON -> [(name, pos, team, player_dict)] in rank
    order, skill/K/DST only. Position ids arrive like 'RB' or occasionally
    'RB1' - strip the digits. DSTs come named like 'Houston Texans'."""
    out = []
    for p in sorted(api_json.get("players", []), key=lambda p: p["rank_ecr"]):
        pos = "".join(c for c in str(p.get("player_position_id", "")).upper() if not c.isdigit())
        if pos not in KEEP_POS:
            continue
        out.append((p["player_name"].strip(), pos, team(p.get("player_team_id")), p))
    return out


def write_source_txt(path, players):
    lines = [f"{n}|{p}|{t}" for n, p, t, _ in players]
    path.write_text("\n".join(lines) + "\n")
    print(f"[write] {path.name}: {len(lines)} rows")


def meta_for_format(rank_json, adp_json):
    """Sidecar per player: ECR + dispersion from the draft pull, ADP rank from
    the ADP pull, joined on mkey. rank_std is dispersion across the full
    expert pool - a real upgrade on the 3-source min/max spread."""
    players = {}
    for name, pos, tm, p in fp_players(rank_json):
        k = mkey(name, pos, tm)
        players[k] = {
            "name": name, "pos": pos, "team": tm,
            "ecr": p.get("rank_ecr"),
            "std": p.get("rank_std"),
            "ave": p.get("rank_ave"),
            "min": p.get("rank_min"), "max": p.get("rank_max"),
            "pos_rank": p.get("pos_rank"),
            "bye": p.get("player_bye_week"),
            "own": p.get("player_owned_avg"),
        }
    if adp_json:
        for name, pos, tm, p in fp_players(adp_json):
            k = mkey(name, pos, tm)
            if k in players:
                players[k]["adp"] = p.get("rank_ecr")
    return {"total_experts": rank_json.get("total_experts"),
            "last_updated": rank_json.get("last_updated"),
            "players": players}


def sleeper_trending(force=False, transport=None):
    """Trending add/drop counts keyed by mkey. Needs the id->player map to
    resolve ids; that map is ~5MB and the date-stamped cache is what holds it
    to once per day. Sleeper DEF entries use the team code as the id."""
    pmap = fpapi.sleeper_get("sleeper-players", "v1/players/nfl",
                             force=force, transport=transport)
    out = {}
    for kind in ("add", "drop"):
        trend = fpapi.sleeper_get(
            f"sleeper-trending-{kind}",
            f"v1/players/nfl/trending/{kind}?lookback_hours=48&limit=50",
            force=force, transport=transport)
        counts, claimed, ambiguous = {}, {}, set()
        for row in trend:
            pid = str(row.get("player_id"))
            p = pmap.get(pid)
            if not p:
                continue
            pos = (p.get("position") or "").upper()
            if pos == "DEF":
                k = mkey("", "DST", team(pid))
            else:
                if pos not in KEEP_POS:
                    continue
                name = p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}"
                k = mkey(name.strip(), pos, team(p.get("team")))
            if not k:
                continue
            # Sleeper sometimes spells suffixed names without the suffix, so
            # two DIFFERENT players can reduce to one key (Bijan / a suffixless
            # Brian Robinson, both RB/ATL). Trending is a decoration - when we
            # can't tell whose count it is, nobody gets it.
            if k in ambiguous:
                continue
            if k in claimed and claimed[k] != pid:
                counts.pop(k, None)
                ambiguous.add(k)
                print(f"[sleeper] ambiguous {kind} key {k} (two different players) - dropped")
                continue
            claimed[k] = pid
            counts[k] = counts.get(k, 0) + row.get("count", 0)
        out[kind] = counts
        print(f"[sleeper] trending {kind}: {len(counts)} players")
    return out


def main(argv):
    force = "--force" in argv
    env = fpapi.load_env()
    season = env.get("FANTASYPROS_SEASON", "2026")

    fpapi.verify()   # 1 request on a cold day; 0 once verified (caches HALF)

    path = f"nfl/{season}/consensus-rankings"
    pulls = {}
    for fmt, scoring in (("half", "HALF"), ("ppr", "PPR")):
        pulls[fmt] = fpapi.fp_get(f"consensus-rankings-{fmt}", path,
                                  {"position": "ALL", "scoring": scoring}, force=force)
        pulls[fmt + "_adp"] = fpapi.fp_get(f"consensus-rankings-{fmt}-adp", path,
                                           {"position": "ALL", "scoring": scoring,
                                            "type": "ADP"}, force=force)

    if "--news" in argv:
        fpapi.fp_get("news-injury", "nfl/news", {"category": "injury", "limit": 25}, force=force)
    if "--projections" in argv:
        for fmt, scoring in (("half", "HALF"), ("ppr", "PPR")):
            fpapi.fp_get(f"projections-{fmt}", f"nfl/{season}/projections",
                         {"positions": "QB:RB:WR:TE:DST:K", "scoring": scoring}, force=force)

    DATA.mkdir(parents=True, exist_ok=True)
    half = fp_players(pulls["half"])
    ppr = fp_players(pulls["ppr"])
    write_source_txt(DATA / "fp_half.txt", half)
    write_source_txt(DATA / "fp_ppr.txt", ppr)

    meta = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "season": season,
        "half": meta_for_format(pulls["half"], pulls["half_adp"]),
        "ppr": meta_for_format(pulls["ppr"], pulls["ppr_adp"]),
        "trending": ({"add": {}, "drop": {}} if "--no-sleeper" in argv
                     else sleeper_trending(force=force)),
    }
    (DATA / "fp_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"[write] fp_meta.json: {len(meta['half']['players'])} half / "
          f"{len(meta['ppr']['players'])} ppr players")
    print("\nNow rerun the pipeline and the audit:\n"
          "  python3 scripts/agg_three.py && python3 scripts/fix_names.py\n"
          "  python3 scripts/build_four.py && python3 scripts/build_xlsx3.py\n"
          "  python3 scripts/audit.py   # must end TOTAL PROBLEMS: 0")


if __name__ == "__main__":
    main(sys.argv[1:])
