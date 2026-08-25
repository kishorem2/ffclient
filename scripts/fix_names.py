import json, re
from pathlib import Path

CONSENSUS = Path(__file__).resolve().parent.parent / "data" / "consensus.json"

# Full names for players FantasyPros ranks past its top 300, so only the
# abbreviated Yahoo spelling survived the merge. Sourced from the FantasyPros
# half-PPR list rows 301-590. A.J. Brown / J.K. Dobbins / C.J. Stroud /
# T.J. Hockenson are left alone - that IS how they are written.
NAME_FIX = {
    ("T. Burks","WR","WAS"): "Treylon Burks",
    ("C. Kolar","TE","LAC"): "Charlie Kolar",
    ("T. Smack","K","GB"): "Trey Smack",
    ("J. Dotson","WR","ATL"): "Jahan Dotson",
    ("M. Gesicki","TE","CIN"): "Mike Gesicki",
    ("O. Delp","TE","NO"): "Oscar Delp",
    ("A. Iosivas","WR","CIN"): "Andrei Iosivas",
    ("C. Austin III","WR","NYG"): "Calvin Austin III",
    ("B. Aiyuk","WR","SF"): "Brandon Aiyuk",
    ("L. McCaffrey","WR","WAS"): "Luke McCaffrey",
    ("K. Johnson","RB","PIT"): "Kaleb Johnson",
    ("D. Washington","TE","PIT"): "Darnell Washington",
    ("E. All Jr.","TE","CIN"): "Erick All Jr.",
    ("K. Williams","WR","NE"): "Kyle Williams",
    ("I. Bond","WR","CLE"): "Isaiah Bond",
    ("S. Bell","WR","BUF"): "Skyler Bell",
    ("K. Bourne","WR","ARI"): "Kendrick Bourne",
    ("J. Tolbert","WR","MIA"): "Jalen Tolbert",
    ("J. Elliott","K","PHI"): "Jake Elliott",
    ("J. Hunter","RB","LAR"): "Jarquez Hunter",
    ("B. Grupe","K","IND"): "Blake Grupe",
    ("C. Smyth","K","NO"): "Charlie Smyth",
    ("T. Bass","K","BUF"): "Tyler Bass",
    ("N. Folk","K","ATL"): "Nick Folk",
    ("Z. Gonzalez","K","FA"): "Zane Gonzalez",
    ("R. Fitzgerald","K","CAR"): "Ryan Fitzgerald",
    ("S. Shrader","K","IND"): "Spencer Shrader",
    ("B. Sauls","K","NYG"): "Ben Sauls",
    ("T. Brooks","RB","CIN"): "Tahj Brooks",
    ("M. Davis","RB","DAL"): "Malik Davis",
    ("Ty Johnson","RB","BUF"): "Ty Johnson",
}

d = json.load(open(CONSENSUS))
fixed = 0
for fmt in ("half", "ppr"):
    for r in d[fmt]["rows"]:
        k = (r["name"], r["pos"], r["team"])
        if k in NAME_FIX and NAME_FIX[k] != r["name"]:
            r["name"] = NAME_FIX[k]
            fixed += 1
json.dump(d, open(CONSENSUS, "w"))
print("expanded", fixed, "names")

left = [r["name"] for f in ("half","ppr") for r in d[f]["rows"]
        if re.match(r"^[A-Z]\. ", r["name"])]
print("still abbreviated:", sorted(set(left)) or "none")
