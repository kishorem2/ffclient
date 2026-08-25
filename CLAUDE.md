# CLAUDE.md — 2026 Fantasy Draft Board

Context for a fresh session. Everything here was built and tested in a prior
claude.ai conversation; nothing carried over automatically, so read this first.

## Goal

Produce five draft deliverables from a blended consensus of multiple ranking
sources, for **two separate scoring formats** (half-PPR and full PPR):

| File | What it is |
|---|---|
| `cheat-sheet-half-ppr.pdf` | Position-column tiered sheet, printable, for use during the draft |
| `cheat-sheet-ppr.pdf` | Same, full PPR |
| `rankings-half-ppr.pdf` | Straight top-300 consensus order, one page |
| `rankings-ppr.pdf` | Same, full PPR |
| `draft-cheat-sheet.xlsx` | Both formats as filterable tabs + editable weights |

**Half PPR and full PPR are never pooled.** They are genuinely different
rankings, not one list rescored. Every step keeps them separate.

## The owner's leagues

- Multiple redraft leagues: some 10-team, some 12-team.
- All standard 1QB. **One league has an extra FLEX instead of a kicker** —
  which is why the cheat sheet carries a "DEEP FLEX" block (RB 61–74,
  WR 73–86) in the space under the K/DST column.
- Draft depth target: ~200 relevant players; sheets print QB24 / RB60 /
  WR72 / TE24 / K12 / DST12.

## Current state

`scripts/` runs end-to-end from `data/` with **no network access**, using
transcribed static rankings. Run in this order:

```bash
python3 scripts/agg_three.py     # merge sources -> data/consensus.json
python3 scripts/fix_names.py     # expand abbreviated names
python3 scripts/build_four.py    # the four PDFs
python3 scripts/build_xlsx3.py   # the workbook
```

Outputs land in `output/`. `scripts/audit.py` after any change; it must end
`TOTAL PROBLEMS: 0`.

## Live API layer (built, awaiting a network that can reach the APIs)

`scripts/fpapi.py` is the fetch layer (per-day cache in `cache/`, persistent
request counter in `.fp_request_log.json` that hard-stops at `FP_DAILY_BUDGET`);
`scripts/fetch_live.py` orchestrates the pulls and rewrites `data/fp_*.txt`
plus a `data/fp_meta.json` sidecar (ECR, rank_std, ADP, bye, Sleeper trending
keyed by `mkey()`). The pipeline picks the sidecar up automatically: without
it the build is the original static blend, with it the deliverables grow the
ECR−ADP column, the rank_std disagreement flag, and trending markers.
Sequence: `fpapi.py verify` (1 request, discovers which base URL the key
accepts), then `fetch_live.py` (3 more on a cold cache), then the pipeline.
`test_fpapi.py` and `test_fetch_live.py` exercise all of it offline.

Sleeper names sometimes omit generational suffixes, which makes a suffixless
Brian Robinson key identical to Bijan's. Trending attribution therefore drops
any ambiguous key on either side — a missing hype flag is fine, a wrong one
is not — and trending never enters the consensus.

### FantasyPros

- Base: `https://api.fantasypros.com/v2/json` — the newer marketing page
  advertises `https://api.fantasypros.com/public/v2/json`. **Try both and
  report which the key accepts.**
- Auth header: `x-api-key: <key>`. Key goes in `.env`, never in source.
- **Rate limit: 50 requests/day.** This is the binding constraint. Cache
  every raw response to `cache/<endpoint>-<date>.json` and never refetch
  without `--force`. Keep a persistent counter and hard-stop at a budget.

Endpoint: `GET /nfl/{season}/consensus-rankings`

| Param | Values |
|---|---|
| `position` | `ALL` (required) |
| `scoring` | `STD`, `PPR`, `HALF` |
| `type` | omit for preseason draft; `ADP`, `ROS`, `DK`, `WW` |

Per-player fields worth having: `rank_ecr`, `rank_min`, `rank_max`,
`rank_ave`, **`rank_std`**, `pos_rank`, `player_bye_week`,
`player_owned_avg`. Top level: `total_experts`, `last_updated`.

`rank_std` is a real upgrade over what the static build has — dispersion
across all ~111 experts, versus the current 3-source min/max range. Use it
for the disagreement flag once available.

**Planned request budget — 7 per full refresh:**

1. `consensus-rankings?position=ALL&scoring=HALF`
2. `consensus-rankings?position=ALL&scoring=PPR`
3. `consensus-rankings?position=ALL&scoring=HALF&type=ADP`
4. `consensus-rankings?position=ALL&scoring=PPR&type=ADP`
5. `nfl/news?category=injury&limit=25`
6–7. `nfl/{season}/projections?positions=QB:RB:WR:TE:DST:K&scoring=HALF|PPR`

**ECR minus ADP is the most valuable new column** — where the room drafts a
player versus where the experts rank him. Add it to both the workbook and
the straight-rankings PDF.

Also drop the top-300 cap on FantasyPros data; that was a transcription
limit, not an API one. The API returns ~590.

### Sleeper

No auth, no meaningful rate limit (stay under 1000/min). **Sleeper has no
expert rankings** — do not look for them. What it has:

- `GET /v1/players/nfl` — id→player map, ~5MB. Fetch **once per day max**,
  cache to disk. Supports `?position=RB&active=true` to shrink it.
- `GET /v1/players/nfl/trending/add?lookback_hours=48&limit=50` — add counts
  across all Sleeper leagues. Same for `/drop`.

Trending measures **attention, not value** — pre-draft it is mostly hype and
injury reaction. Render it as a flag column on the sheets. Never feed it
into the consensus average.

## Design decisions to preserve

**Name matching.** Sources abbreviate differently (`J. Gibbs` vs
`Jahmyr Gibbs`). The key is
`first-initial | surname | generational-suffix | pos | team`, lowercased and
de-punctuated. Every component is load-bearing:

- **Suffix.** `Bijan Robinson` and `Brian Robinson Jr.` are both RB/ATL and
  both abbreviate to `B. Robinson`. The `Jr.` is the *only* thing separating
  them. An early version stripped suffixes as noise and silently merged the
  RB2 overall into a backup — Bijan vanished from the board entirely and
  nobody noticed until a human read the sheet and asked where he was.
  **Never strip suffixes from the key.**
- **Team.** `A.J. Brown` (WR NE) and `Amon-Ra St. Brown` (WR DET) both reduce
  to `a|brown|WR`. `Travis Etienne Jr.` (NO) and `Trevor Etienne` (CAR) both
  reduce to `t|etienne||RB`.
- **D/ST** keys on team alone — naming varies wildly (`HOU` vs
  `Houston Texans`).

Three guards enforce this, and all three must stay:

1. `load()` raises on any duplicate key **within** a source. Two players
   sharing a key means one gets silently overwritten.
2. `aggregate()` raises if a source's surviving rank count != its row count.
   This is the real safety net — it catches losses no matter the cause.
3. A warning prints for any single-source player inside the top 200, which
   flags a matching regression. It should print nothing.

`scripts/audit.py` is the full verification pass — run it after any change to
sources or matching. It checks four things and must end with
`TOTAL PROBLEMS: 0`:

- **A. Round trip.** Every row of every source file appears in the output with
  that source's rank intact and consistent pos/team. Currently 1,809 rows
  across six files, all accounted for.
- **B. Split suspects.** Two records sharing a surname+position whose source
  sets are *disjoint* — the signature of a failed merge, where one player
  became two half-covered ghosts.
- **C. Team conflicts.** A player one source lists on a different team than
  another, which would split them. Note that D/ST names legitimately differ
  (`HOU` vs `Houston Texans`) and are compared on team only.
- **D. Coverage.** Where the thinly-covered players sit. Single-source players
  should all be deep (currently #285+); any near the top means a merge failed.

The audit had two false-positive classes of its own when first written — it
compared D/ST names as if they were surnames, and its own grouping key
dropped suffix and team so both Etiennes collided inside the audit. Both are
fixed. If you extend it, remember the audit needs to be at least as precise
as the thing it is auditing.

If you add a source or touch `mkey()`: run the pipeline, run `audit.py`, and
confirm Bijan Robinson is RB2 in both formats.

**Weighting.** FantasyPros ECR is itself ~111 experts averaged, so it is not
a peer of one analyst. It carries **double weight**; Winks and Norris carry
1.0 each. Editable in the workbook's Legend tab.

**Omission penalty.** A source leaving a player off entirely counts as a rank
just past the end of that source's list, not as missing data. Being left off
a 300-player board is information.

**Tiers.** Two kinds, both by gap detection with a proportional threshold
(`max(1.25, 0.055 * prev_avg)`), then any block over the size cap is split at
its largest internal gap:

- *Overall* tiers (cap 11) — used in the workbook.
- *Positional* tiers (cap 7) — used on the cheat sheets. These are the ones
  that matter mid-draft: they tell you how many comparable players are left
  at a position, which is the actual reach signal.

**Disagreement flag.** Threshold is the 85th percentile of spread among
draft-relevant skill players — computed in `agg_three.py` and stored in
`consensus.json` so the PDFs and workbook can't drift (currently 40; an
earlier draft of this doc said 42, the shipped PDFs always said 40). With
live data the flag reads `rank_std` instead, same 85th-percentile rule.
Players ranked by only one source get `·1`, never the gold flag: unknown
spread is not high spread. Recompute the threshold when a source is added.

**K/DST caveat.** The sources split on *philosophy* rather than talent for
kickers and defenses — Norris buries them, Winks slots them by projected
points. Their apparent "disagreement" is an artifact. They are hidden by
default in the interactive board and footnoted on the PDFs. Keep that.

## Files

```
data/
  winks_half.txt, winks_full.txt      Hayden Winks, Yahoo, Aug 12 2026
  norris_half.txt, norris_full.txt    Josh Norris, Yahoo, Aug 12 2026
  fp_half.txt, fp_ppr.txt             FantasyPros ECR top 300, Aug 25 2026
  consensus.json                      merged output, regenerated by agg_three
scripts/                              the four build steps, in run order
output/                               the five current deliverables
```

Data files are `Name|POS|TEAM`, one per line, rank implied by line number.

## Conventions

- `.env` and `cache/` stay gitignored. The FantasyPros key was exposed in a
  chat log once already and should be rotated.
- PDFs are letter portrait, ReportLab canvas, hand-placed. Row height is
  solved from the densest column so nothing runs off the page — check
  rendered output with `pdf2image` after any layout change rather than
  trusting it.
- Don't reproduce any single source's ranking wholesale as a deliverable.
  The whole point is a derived blend the owner controls.
