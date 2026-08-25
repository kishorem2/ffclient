"""Offline proof of the fpapi cache + budget layer. No network: every
"response" comes from a stub transport, and FP_CACHE_DIR / FP_STATE_FILE
point at a throwaway sandbox so nothing touches the real counter or cache.

Run:  python3 scripts/test_fpapi.py
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

sandbox = Path(tempfile.mkdtemp(prefix="fpapi-demo-"))
os.environ["FP_CACHE_DIR"] = str(sandbox / "cache")
os.environ["FP_STATE_FILE"] = str(sandbox / "state.json")
os.environ["FP_DAILY_BUDGET"] = "3"
os.environ["FANTASYPROS_API_KEY"] = "demo-key-not-real"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpapi

calls = []
def stub_401_then_200(url, params, headers):
    calls.append(url)
    assert headers.get("x-api-key") == "demo-key-not-real"
    if url.startswith(fpapi.BASES[0]):
        return 401, "unauthorized"
    return 200, json.dumps({"total_experts": 111, "last_updated": "demo",
                            "players": [{"player_name": "Demo Player", "rank_ecr": 1}]})

def stub_200(url, params, headers):
    calls.append(url)
    return 200, json.dumps({"players": [], "echo": url})

fails = 0
def check(label, cond):
    global fails
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        fails += 1

print("== 1. verify: /v2/json 401s, falls back to /public/v2/json, records base ==")
base = fpapi.verify(transport=stub_401_then_200)
check("fell back to public base", base == fpapi.BASES[1])
check("burned 2 requests (401 counts against budget)", len(calls) == 2)
check("response saved into the half-rankings cache slot",
      fpapi.cache_path("consensus-rankings-half").exists())

print("\n== 2. cache hit: same-day refetch makes zero requests ==")
n = len(calls)
d = fpapi.fp_get("consensus-rankings-half", "nfl/2026/consensus-rankings",
                 {"position": "ALL", "scoring": "HALF"}, transport=stub_200)
check("no request made", len(calls) == n)
check("served the verify response from disk", d["total_experts"] == 111)

print("\n== 3. --force refetches and overwrites the cache file ==")
d = fpapi.fp_get("consensus-rankings-half", "nfl/2026/consensus-rankings",
                 {"position": "ALL", "scoring": "HALF"}, force=True, transport=stub_200)
check("request made", len(calls) == n + 1)
check("cache now holds the fresh response", "echo" in d)

print("\n== 4. budget hard stop: counter is at 3/3, next miss must die ==")
try:
    fpapi.fp_get("consensus-rankings-ppr", "nfl/2026/consensus-rankings",
                 {"position": "ALL", "scoring": "PPR"}, transport=stub_200)
    check("SystemExit raised", False)
except SystemExit as e:
    check("SystemExit raised", True)
    check("message names the budget", "HARD STOP" in str(e))
check("stub never called for it", len(calls) == n + 1)

print("\n== 5. but cached endpoints still work with the budget exhausted ==")
d = fpapi.fp_get("consensus-rankings-half", "nfl/2026/consensus-rankings",
                 {"position": "ALL", "scoring": "HALF"}, transport=stub_200)
check("cache hit, no request, no crash", len(calls) == n + 1)

print("\n== 6. counter survives a cache wipe (it lives outside cache/) ==")
shutil.rmtree(os.environ["FP_CACHE_DIR"])
state = json.load(open(os.environ["FP_STATE_FILE"]))
check("count still 3 after rm -rf cache/", state["count"] == 3)

print("\n== 7. sleeper: cached, keyless, exempt from the FP budget ==")
d = fpapi.sleeper_get("sleeper-trending-add",
                      "v1/players/nfl/trending/add?lookback_hours=48&limit=50",
                      transport=lambda u, p, h: (200, json.dumps([{"player_id": "demo", "count": 9}])))
d = fpapi.sleeper_get("sleeper-trending-add", "v1/players/nfl/trending/add",
                      transport=lambda u, p, h: (_ for _ in ()).throw(AssertionError("refetched!")))
check("second call was a cache hit", d[0]["count"] == 9)
check("FP counter untouched by sleeper", json.load(open(os.environ["FP_STATE_FILE"]))["count"] == 3)

shutil.rmtree(sandbox)
print(f"\n{'ALL CHECKS PASSED' if fails == 0 else f'{fails} CHECKS FAILED'}")
sys.exit(1 if fails else 0)
