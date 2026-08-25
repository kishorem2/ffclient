# 2026 Fantasy Draft Board

Blended consensus rankings and printable draft sheets for half-PPR and full PPR.

## Run it offline (static transcribed rankings)

    python3 scripts/agg_three.py
    python3 scripts/fix_names.py
    python3 scripts/build_four.py
    python3 scripts/build_xlsx3.py
    python3 scripts/audit.py       # must end TOTAL PROBLEMS: 0

Requires `reportlab`, `openpyxl` (and `requests` for the live pulls).
Outputs land in `output/`.

## Go live (FantasyPros + Sleeper)

    cp .env.example .env           # then paste your FantasyPros key in
    python3 scripts/fpapi.py verify    # ONE request: confirms the key and base URL
    python3 scripts/fetch_live.py      # 3 more requests on a cold cache + Sleeper
    # ...then the five pipeline commands above

Every FantasyPros response is cached to `cache/<endpoint>-<date>.json`; nothing
refetches the same day without `--force`, and a persistent counter hard-stops
at `FP_DAILY_BUDGET` (the API limit is 50/day). `python3 scripts/fpapi.py status`
shows the counter and cache without spending anything. With live data the
deliverables grow an ECR−ADP value column, a rank_std-driven disagreement
flag, and Sleeper trending markers.

Offline test suites (no network, nothing real touched):

    python3 scripts/test_fpapi.py
    python3 scripts/test_fetch_live.py

## What's in output/

- `cheat-sheet-half-ppr.pdf` / `cheat-sheet-ppr.pdf` — tiered, position
  columns, print these and bring them to the draft
- `rankings-half-ppr.pdf` / `rankings-ppr.pdf` — straight top-300 order
- `draft-cheat-sheet.xlsx` — both formats, filterable, with a Drafted
  dropdown and editable source weights on the Legend tab

See `CLAUDE.md` for the full brief and every design decision worth preserving.
