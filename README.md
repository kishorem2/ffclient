# 2026 Fantasy Draft Board

Blended consensus rankings and printable draft sheets for half-PPR and full PPR.

## Run it as-is (no network needed)

    python3 scripts/agg_three.py
    python3 scripts/fix_names.py
    python3 scripts/build_four.py
    python3 scripts/build_xlsx3.py

Requires `reportlab`, `openpyxl`. Paths in the build scripts point at
`/mnt/user-data/outputs` — change them to `output/` for local runs.

## What's in output/

- `cheat-sheet-half-ppr.pdf` / `cheat-sheet-ppr.pdf` — tiered, position
  columns, print these and bring them to the draft
- `rankings-half-ppr.pdf` / `rankings-ppr.pdf` — straight top-300 order
- `draft-cheat-sheet.xlsx` — both formats, filterable, with a Drafted
  dropdown and editable source weights on the Legend tab

## Next step

See `CLAUDE.md` — it has the full brief for wiring this up to the live
FantasyPros and Sleeper APIs, including the request budget and every design
decision worth preserving.
