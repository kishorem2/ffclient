import json, statistics
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
D = json.load(open(ROOT / "data" / "consensus.json"))
W, H = letter
M = 22
INK = HexColor("#15181F")
GREY = HexColor("#8A9099")
FAINT = HexColor("#B9BEC6")
RULE = HexColor("#C9CED6")
BAND = HexColor("#F2F4F7")
POS_C = {"QB": "#C97A16", "RB": "#1F8A55", "WR": "#2360A5", "TE": "#B03A6B",
         "K": "#5B48A8", "DST": "#1D7E77"}
SRCS = ["Winks", "Norris", "FantasyPros"]

# flag threshold: top ~15% most-divided among draft-relevant skill players
pool = [r["spread"] for r in D["half"]["rows"][:200] if r["pos"] not in ("K", "DST")]
FLAG = round(statistics.quantiles(pool, n=20)[16])
print("disagreement flag threshold:", FLAG)


def spread_of(r):
    """Disagreement only means something with 2+ sources. A player just one
    source ranked has unknown spread, not high spread - never flag them."""
    return r["spread"] if r["n"] > 1 else -1


def header(c, title, sub1, sub2):
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 17)
    c.drawString(M, H - 40, title)
    c.setFont("Helvetica", 7.6); c.setFillColor(GREY)
    c.drawString(M, H - 51, sub1)
    c.drawString(M, H - 60, sub2)
    c.setStrokeColor(INK); c.setLineWidth(1.1)
    c.line(M, H - 68, W - M, H - 68)


# ---------------------------------------------------------------- cheat sheet
DEPTH = {"QB": 24, "RB": 60, "WR": 72, "TE": 24, "K": 12, "DST": 12}
COLS = ["QB", "RB", "WR", "TE", "KDST"]
BODY_TOP, BODY_BOT = 726, 46


def cheat_page(c, fmt, title):
    rows = D[fmt]["rows"]
    bypos = {p: sorted([r for r in rows if r["pos"] == p], key=lambda r: r["avg"])
             for p in DEPTH}

    header(c, title,
           "Consensus of Hayden Winks + Josh Norris (Yahoo) + FantasyPros ECR, with FantasyPros weighted double. "
           "Number is the overall consensus rank.",
           f"\u2022 marks a player the sources place {FLAG}+ ranks apart \u2014 no real consensus, so it's your call. Rules between names are tier breaks.")

    def demand(pos, depth):
        pl = bypos[pos][:depth]
        return len(pl), max(0, len({p["ptier"] for p in pl}) - 1)

    worst = max(n + 0.42 * b for n, b in (demand(p, DEPTH[p]) for p in ("QB", "RB", "WR", "TE")))
    ROW = min(8.9, (BODY_TOP - BODY_BOT - 16) / worst)
    TG = 0.42 * ROW
    colw = (W - 2 * M - 4 * 6) / 5

    def bar(x, y, label, color, sub):
        c.setFillColor(HexColor(color)); c.rect(x, y, colw, 13, stroke=0, fill=1)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 4, y + 3.6, label)
        c.setFont("Helvetica", 6.5); c.drawRightString(x + colw - 4, y + 3.8, sub)

    def block(x, y, pos, depth):
        pl = bypos[pos][:depth]
        bar(x, y - 13, "D/ST" if pos == "DST" else pos, POS_C[pos], f"top {len(pl)}")
        y -= 13 + 8
        cur = None
        for p in pl:
            if p["ptier"] != cur:
                if cur is not None:
                    c.setStrokeColor(RULE); c.setLineWidth(0.5)
                    c.line(x + 1, y + 2.2, x + colw - 1, y + 2.2)
                    y -= TG
                cur = p["ptier"]
            c.setFont("Helvetica", 6.2); c.setFillColor(GREY)
            c.drawRightString(x + 14, y, str(p["overall"]))
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold" if p["ptier"] <= 2 else "Helvetica", 6.9)
            c.drawString(x + 17, y, (p["team"] if pos == "DST" else p["name"])[:23])
            c.setFont("Helvetica", 6.0); c.setFillColor(GREY)
            tail = ("\u2022 " if spread_of(p) >= FLAG else "") + ("" if pos == "DST" else p["team"])
            c.drawRightString(x + colw - 2, y, tail)
            y -= ROW
        return y

    for i, key in enumerate(COLS):
        x = M + i * (colw + 6)
        if key != "KDST":
            block(x, BODY_TOP, key, DEPTH[key])
        else:
            y = block(x, BODY_TOP, "K", DEPTH["K"])
            y = block(x, y - 10, "DST", DEPTH["DST"])
            y -= 12
            c.setFillColor(HexColor("#3B4250")); c.rect(x, y - 13, colw, 13, stroke=0, fill=1)
            c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 8)
            c.drawString(x + 4, y - 9.4, "DEEP FLEX")
            c.setFont("Helvetica", 5.8); c.drawRightString(x + colw - 4, y - 9.2, "no-K league")
            y -= 13 + 9
            c.setFillColor(GREY); c.setFont("Helvetica-Oblique", 5.8)
            c.drawString(x + 1, y, "past the printed RB/WR depth")
            y -= 8
            for pos, lo, hi in (("RB", 60, 74), ("WR", 72, 86)):
                c.setFillColor(HexColor(POS_C[pos])); c.setFont("Helvetica-Bold", 6.4)
                c.drawString(x + 1, y, f"{pos} {lo+1}\u2013{hi}")
                y -= 7.6
                for p in bypos[pos][lo:hi]:
                    c.setFillColor(GREY); c.setFont("Helvetica", 5.8)
                    c.drawRightString(x + 14, y, str(p["overall"]))
                    c.setFillColor(INK); c.setFont("Helvetica", 6.2)
                    c.drawString(x + 17, y, p["name"][:22])
                    y -= 7.2
                y -= 3

    c.setStrokeColor(RULE); c.setLineWidth(0.5)
    c.line(M, BODY_BOT - 6, W - M, BODY_BOT - 6)
    c.setFillColor(GREY); c.setFont("Helvetica", 6.4)
    c.drawString(M, BODY_BOT - 15,
        "Tiers are positional, not overall \u2014 inside a tier the sources see the players as roughly interchangeable, so take need over rank.")
    c.drawString(M, BODY_BOT - 23,
        "A tier about to empty out is the real signal to reach. K and D/ST are where the sources split on philosophy rather than talent \u2014 order of preference only.")
    c.setFont("Helvetica-Oblique", 6.4)
    c.drawString(M, BODY_BOT - 31, "Three-source consensus computed from your own lists. FantasyPros ECR as of Aug 25 2026, top 300 only.")


# ---------------------------------------------------------------- straight list
def list_page(c, fmt, title, depth=300):
    rows = D[fmt]["rows"][:depth]
    header(c, title,
           "Straight consensus order: Winks + Norris + FantasyPros ECR (double-weighted). "
           "'Range' is the highest and lowest rank any single source gave.",
           "A wide range means the sources disagree. Thinly-covered players are marked \u00b71 rather than given a false range.")

    ncol = 3
    colw = (W - 2 * M - (ncol - 1) * 10) / ncol
    top, bot = 716, 40
    per = -(-len(rows) // ncol)
    rh = (top - bot) / per

    for ci in range(ncol):
        x = M + ci * (colw + 10)
        chunk = rows[ci*per:(ci+1)*per]
        y = top
        # column head
        c.setFillColor(HexColor("#3B4250")); c.rect(x, y, colw, 11, stroke=0, fill=1)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 6.2)
        c.drawString(x + 4, y + 3.2, "#")
        c.drawString(x + 22, y + 3.2, "PLAYER")
        c.drawRightString(x + colw - 44, y + 3.2, "POS")
        c.drawRightString(x + colw - 3, y + 3.2, "RANGE")
        y -= 9
        for i, p in enumerate(chunk):
            yy = y - i * rh
            if i % 2 == 1:
                c.setFillColor(BAND)
                c.rect(x, yy - rh + 3.0, colw, rh, stroke=0, fill=1)
            c.setFillColor(GREY); c.setFont("Helvetica", 6.0)
            c.drawRightString(x + 15, yy, str(p["overall"]))
            c.setFillColor(INK); c.setFont("Helvetica", 6.8)
            nm = p["team"] + " D/ST" if p["pos"] == "DST" else p["name"]
            c.drawString(x + 19, yy, nm[:26])
            c.setFillColor(HexColor(POS_C[p["pos"]])); c.setFont("Helvetica-Bold", 6.0)
            c.drawRightString(x + colw - 47, yy, f'{p["pos"]}{p["posrank"]}')
            c.setFillColor(FAINT); c.setFont("Helvetica", 5.6)
            c.drawRightString(x + colw - 33, yy, "" if p["pos"] == "DST" else p["team"])
            hot = spread_of(p) >= FLAG
            rng = f'{p["best"]}\u2013{p["worst"]}' if p["n"] > 1 else f'{p["best"]} \u00b71'
            c.setFillColor(HexColor("#B8860B") if hot else (FAINT if p["n"] == 1 else GREY))
            c.setFont("Helvetica-Bold" if hot else "Helvetica", 5.9)
            c.drawRightString(x + colw - 3, yy, rng)

    c.setStrokeColor(RULE); c.setLineWidth(0.5)
    c.line(M, bot - 8, W - M, bot - 8)
    c.setFillColor(GREY); c.setFont("Helvetica", 6.4)
    c.drawString(M, bot - 17, f"Gold ranges differ by {FLAG}+ \u2014 the sources genuinely disagree and the pick is a judgment call.  \u00b71 means only one source ranked them, so there is no consensus to read.")
    c.setFont("Helvetica-Oblique", 6.4)
    c.drawString(M, bot - 25, "Three-source consensus computed from your own lists. FantasyPros ECR as of Aug 25 2026, top 300 only.")


jobs = [
    ("cheat-sheet-half-ppr.pdf", cheat_page, "half", "HALF PPR \u2014 Tiered Cheat Sheet"),
    ("cheat-sheet-ppr.pdf",      cheat_page, "ppr",  "FULL PPR \u2014 Tiered Cheat Sheet"),
    ("rankings-half-ppr.pdf",    list_page,  "half", "HALF PPR \u2014 Top 300 Consensus Rankings"),
    ("rankings-ppr.pdf",         list_page,  "ppr",  "FULL PPR \u2014 Top 300 Consensus Rankings"),
]
for fname, fn, fmt, title in jobs:
    c = canvas.Canvas(str(OUT / fname), pagesize=letter)
    c.setTitle(title)
    fn(c, fmt, title)
    c.showPage(); c.save()
    print("wrote", fname)
