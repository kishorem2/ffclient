"""Fetch layer for FantasyPros + Sleeper: disk cache, hard daily budget.

Every FantasyPros response is cached to cache/<endpoint>-<YYYY-MM-DD>.json and
never refetched the same day without force=True. A persistent counter (kept
OUTSIDE cache/ so wiping the cache can't reset it) hard-stops at
FP_DAILY_BUDGET from .env — the real limit is 50/day and discovery mistakes
count against it.

Base-URL discovery is a separate, deliberate step:

    python3 scripts/fpapi.py verify    # exactly 1 request (2 only if the first 401s)

It tries /v2/json first, falls back to /public/v2/json on 401, records the
winner in the state file, and saves the response into the half-PPR rankings
cache slot so the request is not wasted — it IS planned request #1.

Ordinary fetches refuse to run until a base URL has been verified, so a bad
guess can never burn budget on 401s.

    python3 scripts/fpapi.py status    # counter, budget, cache contents; no requests

Sleeper needs no key and has no meaningful limit; it shares the same
per-day cache files (which is what enforces "players map once per day").
"""
import json, os, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Overridable so tests/demos can point at a sandbox instead of the real
# counter and cache — never let a demo consume accounting for real requests.
CACHE = Path(os.environ.get("FP_CACHE_DIR", ROOT / "cache"))
STATE = Path(os.environ.get("FP_STATE_FILE", ROOT / ".fp_request_log.json"))

BASES = ["https://api.fantasypros.com/v2/json",
         "https://api.fantasypros.com/public/v2/json"]
SLEEPER = "https://api.sleeper.app"


def load_env():
    env = {}
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in open(envfile):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: os.environ[k] for k in
                ("FANTASYPROS_API_KEY", "FANTASYPROS_SEASON", "FP_DAILY_BUDGET")
                if k in os.environ})
    return env


def today():
    return datetime.date.today().isoformat()


def _load_state():
    s = json.load(open(STATE)) if STATE.exists() else {}
    if s.get("date") != today():
        # new day: counter resets, the verified base URL carries over
        s = {"date": today(), "count": 0, "base": s.get("base"), "requests": []}
    s.setdefault("count", 0)
    s.setdefault("requests", [])
    return s


def _save_state(s):
    STATE.write_text(json.dumps(s, indent=1))


def cache_path(slug):
    return CACHE / f"{slug}-{today()}.json"


def _http_get(url, params, headers):
    import requests
    r = requests.get(url, params=params, headers=headers, timeout=30)
    return r.status_code, r.text


def _spend(state, budget, url, status, note=""):
    state["count"] += 1
    state["requests"].append({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                              "url": url, "status": status, "note": note})
    _save_state(state)
    print(f"[budget] {state['count']}/{budget} FantasyPros requests used today")


def _check_budget(state, budget):
    if state["count"] >= budget:
        raise SystemExit(
            f"[budget] HARD STOP: {state['count']}/{budget} FantasyPros requests "
            f"already used today ({state['date']}). Raise FP_DAILY_BUDGET in .env "
            f"only if you are sure — the API limit is 50/day.")


def fp_get(slug, path, params=None, force=False, transport=None):
    """GET a FantasyPros endpoint through the cache.

    slug   cache filename stem, e.g. 'consensus-rankings-half'
    path   endpoint path under the verified base, e.g. 'nfl/2026/consensus-rankings'
    """
    p = cache_path(slug)
    if p.exists() and not force:
        print(f"[cache] hit  {p.name} — 0 requests")
        return json.load(open(p))

    env = load_env()
    budget = int(env.get("FP_DAILY_BUDGET", "20"))
    state = _load_state()
    _check_budget(state, budget)

    base = state.get("base")
    if not base:
        raise SystemExit("[fpapi] no verified base URL yet - run "
                         "'python3 scripts/fpapi.py verify' first (1 request) so "
                         "ordinary fetches can never burn budget on a wrong base.")
    key = env.get("FANTASYPROS_API_KEY", "")
    if not key or key == "your_key_here":
        raise SystemExit("[fpapi] FANTASYPROS_API_KEY missing from .env")

    url = f"{base}/{path}"
    why = "force refetch" if (force and p.exists()) else "cache miss"
    print(f"[fetch] {slug} ({why}) -> {url}")
    status, text = (transport or _http_get)(url, params or {}, {"x-api-key": key})
    _spend(state, budget, url, status)
    if status != 200:
        raise SystemExit(f"[fpapi] {url} returned {status}: {text[:300]}")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"[cache] saved {p.name} ({len(text)} bytes)")
    return json.loads(text)


def verify(transport=None):
    """One-request key + base-URL check. Doubles as planned request #1: on
    success the response lands in the half-PPR rankings cache slot."""
    env = load_env()
    budget = int(env.get("FP_DAILY_BUDGET", "20"))
    season = env.get("FANTASYPROS_SEASON", "2026")
    key = env.get("FANTASYPROS_API_KEY", "")
    if not key or key == "your_key_here":
        raise SystemExit("[fpapi] FANTASYPROS_API_KEY missing from .env")
    state = _load_state()

    slot = cache_path("consensus-rankings-half")
    if state.get("base") and slot.exists():
        print(f"[verify] already verified today: base={state['base']}, "
              f"{slot.name} cached — 0 requests")
        return state["base"]

    path = f"nfl/{season}/consensus-rankings"
    params = {"position": "ALL", "scoring": "HALF"}
    for base in BASES:
        _check_budget(state, budget)
        url = f"{base}/{path}"
        print(f"[verify] trying {base} ...")
        status, text = (transport or _http_get)(url, params, {"x-api-key": key})
        _spend(state, budget, url, status, note="verify")
        if status == 200:
            state["base"] = base
            _save_state(state)
            CACHE.mkdir(parents=True, exist_ok=True)
            slot.write_text(text)
            d = json.loads(text)
            print(f"[verify] OK  base={base}")
            print(f"[verify] saved {slot.name} — this was planned request #1, not a throwaway")
            print(f"[verify] total_experts={d.get('total_experts')} "
                  f"last_updated={d.get('last_updated')} players={len(d.get('players', []))}")
            return base
        if status == 401:
            print(f"[verify] 401 from {base} — trying the other base")
            continue
        raise SystemExit(f"[verify] unexpected {status} from {url}: {text[:300]}")
    raise SystemExit("[verify] both base URLs returned 401 — key is not valid on either. "
                     "It was exposed in a chat log once; it may have been rotated/revoked.")


def sleeper_get(slug, path, force=False, transport=None):
    """GET a Sleeper endpoint through the same per-day cache. No key, no
    budget — but the date-stamped cache file is what enforces 'players map
    at most once per day', so it still goes through the cache."""
    p = cache_path(slug)
    if p.exists() and not force:
        print(f"[cache] hit  {p.name} — 0 requests")
        return json.load(open(p))
    url = f"{SLEEPER}/{path}"
    print(f"[fetch] {slug} -> {url}")
    status, text = (transport or _http_get)(url, {}, {})
    if status != 200:
        raise SystemExit(f"[sleeper] {url} returned {status}: {text[:300]}")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"[cache] saved {p.name} ({len(text)} bytes)")
    return json.loads(text)


def status():
    env = load_env()
    budget = int(env.get("FP_DAILY_BUDGET", "20"))
    state = _load_state()
    print(f"date            {state['date']}")
    print(f"requests used   {state['count']}/{budget}  (API hard limit: 50/day)")
    print(f"verified base   {state.get('base') or 'NOT YET VERIFIED - run: python3 scripts/fpapi.py verify'}")
    for r in state["requests"]:
        print(f"   {r['ts']}  {r['status']}  {r['url']}  {r.get('note','')}")
    files = sorted(CACHE.glob("*.json")) if CACHE.exists() else []
    print(f"cache           {len(files)} file(s) in {CACHE}/")
    for f in files:
        print(f"   {f.name}  {f.stat().st_size} bytes")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "verify":
        verify()
    elif cmd == "status":
        status()
    else:
        raise SystemExit(f"usage: fpapi.py [verify|status]  (got '{cmd}')")
