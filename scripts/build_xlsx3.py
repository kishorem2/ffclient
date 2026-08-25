import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule, CellIsRule

ROOT = Path(__file__).resolve().parent.parent
D = json.load(open(ROOT / "data" / "consensus.json"))
ARIAL = "Arial"
HDR = "1F2430"
thin = Side(style="thin", color="D0D4DC")
box = Border(left=thin, right=thin, top=thin, bottom=thin)
POS_FILL = {"QB": "FFF0D5", "RB": "D9F7E6", "WR": "D9EAFB", "TE": "FBDCE9", "K": "E8E2FB", "DST": "D5F2F0"}
HDRS = ["Rank","Tier","PosTier","Player","Pos","PosRank","Team","Avg",
        "Winks","Norris","FantasyPros","Range","Drafted","Notes"]

wb = Workbook()
lg = wb.active; lg.title = "Legend"; lg.sheet_view.showGridLines = False

def put(cell, val, size=10, bold=False, color="000000", fill=None, italic=False):
    c = lg[cell]; c.value = val
    c.font = Font(name=ARIAL, size=size, bold=bold, color=color, italic=italic)
    if fill: c.fill = PatternFill("solid", fgColor=fill)
    return c

put("A1", "2026 Draft Cheat Sheet \u2014 Three-Source Consensus", 15, True)
put("A2", "Blends Hayden Winks and Josh Norris (Yahoo Sports, Aug 12 2026) with the FantasyPros Expert Consensus Ranking (Aug 25 2026, 111 experts half-PPR / 108 PPR).", 9, color="555555")
put("A3", "Half PPR and Full PPR are separate boards. FantasyPros is capped at its top 300; anyone it ranks below that is treated as omitted.", 9, color="555555")

put("A5", "WHICH CELLS YOU EDIT", 11, True)
put("A6", "Two columns are yours: Drafted and Notes. The weights and penalties below are also editable. Everything else recalculates \u2014 but the rows will not resort themselves, so use the header filters to sort by Avg after changing a weight.", 9)
put("A7", "Drafted", 10, True, fill="FFF3B0"); put("B7", "Pick ME or TAKEN from the dropdown. Rows turn green or grey out.", 9)
put("A8", "Notes", 10, True, fill="FFF3B0"); put("B8", "Your own reads \u2014 injury notes, 'do not draft', target round.", 9)

put("A10", "EXAMPLE OF A FILLED ROW", 11, True)
for i, h in enumerate(HDRS):
    c = lg.cell(row=11, column=1+i, value=h)
    c.font = Font(name=ARIAL, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=HDR); c.border = box
for i, v in enumerate([19,7,4,"Omarion Hampton","RB",9,"LAC",19.0,24,15,19,9,"ME","volume is there, line is shaky"]):
    c = lg.cell(row=12, column=1+i, value=v)
    c.font = Font(name=ARIAL, size=9); c.border = box
    if i in (12,13): c.fill = PatternFill("solid", fgColor="FFF3B0")

put("A14", "COLUMN MEANINGS", 11, True)
for r, (k, v) in enumerate([
    ("Tier", "Overall tier. A break means a real drop-off in consensus value."),
    ("PosTier", "Tier within the position \u2014 the one to use mid-draft. It tells you how many comparable players remain at that spot."),
    ("Avg", "Weighted average of the three sources. Formula \u2014 driven by the weights and penalties below."),
    ("Winks / Norris / FantasyPros", "Each source's own rank. Blank means that source left the player off (or ranked them past FantasyPros' top 300)."),
    ("Range", "Highest minus lowest rank across the sources. A big number means they genuinely disagree and the pick is a judgment call."),
], start=15):
    put(f"A{r}", k, 10, True); put(f"B{r}", v, 9)

put("A21", "WEIGHTS", 11, True)
put("A22", "FantasyPros ECR is itself an average of 100+ experts, so weighting it equal to one analyst would understate the market. It is set to double. Change these to shift the blend \u2014 set FantasyPros to 1 to treat all three as equal opinions.", 9, color="555555")
for r, (label, val) in enumerate([("Winks weight", 1.0), ("Norris weight", 1.0), ("FantasyPros weight", 2.0)], start=23):
    put(f"A{r}", label, 9)
    c = put(f"B{r}", val, 9, True, color="0000FF", fill="FFFF00"); c.border = box

put("A27", "OMISSION PENALTIES", 11, True)
put("A28", "When a source leaves a player off entirely, that counts as a rank just past the end of their list rather than being ignored \u2014 being omitted from a 300-player board is information.", 9, color="555555")
PEN = [("Half PPR \u2014 Winks", 315, "list is 300 deep"), ("Half PPR \u2014 Norris", 321, "list is 306 deep"),
       ("Half PPR \u2014 FantasyPros", 315, "capped at top 300"), ("Full PPR \u2014 Winks", 316, "list is 301 deep"),
       ("Full PPR \u2014 Norris", 317, "list is 302 deep"), ("Full PPR \u2014 FantasyPros", 315, "capped at top 300")]
for r, (label, val, why) in enumerate(PEN, start=29):
    put(f"A{r}", label, 9)
    c = put(f"B{r}", val, 9, True, color="0000FF", fill="FFFF00"); c.border = box
    put(f"C{r}", why, 9, color="777777", italic=True)

put("A36", "Blue on yellow are hard-coded inputs you can change. Black is a formula.", 8, color="777777", italic=True)
put("A37", "Your no-kicker league: the extra flex makes RB/WR depth matter more than the K column. Filter by Pos and work past RB60 / WR72.", 9, color="555555")

lg.column_dimensions["A"].width = 30
lg.column_dimensions["B"].width = 60
lg.column_dimensions["C"].width = 30
for col in "DEFGHIJKLMN": lg.column_dimensions[col].width = 9

WIDTHS = [7,6,8,24,6,8,7,8,8,8,11,8,10,32]
WCELL = {"Winks": "Legend!$B$23", "Norris": "Legend!$B$24", "FantasyPros": "Legend!$B$25"}
PENCELL = {"half": ("Legend!$B$29","Legend!$B$30","Legend!$B$31"),
           "ppr":  ("Legend!$B$32","Legend!$B$33","Legend!$B$34")}

for fmt, tab in (("half","Half PPR"), ("ppr","Full PPR")):
    ws = wb.create_sheet(tab); ws.sheet_view.showGridLines = False
    rows = D[fmt]["rows"]
    ws["A1"] = f"{tab} \u2014 Winks + Norris + FantasyPros consensus"
    ws["A1"].font = Font(name=ARIAL, size=13, bold=True)
    ws["A2"] = "Filter with the header arrows. Set Drafted to dim a row. A shaded Range means the sources disagree by 42 or more."
    ws["A2"].font = Font(name=ARIAL, size=9, color="666666")

    for i, h in enumerate(HDRS):
        c = ws.cell(row=4, column=1+i, value=h)
        c.font = Font(name=ARIAL, size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=HDR)
        c.alignment = Alignment(horizontal="center", vertical="center"); c.border = box
    ws.row_dimensions[4].height = 20

    pW, pN, pF = PENCELL[fmt]
    for idx, p in enumerate(rows):
        r = 5 + idx
        rk = p["ranks"]
        avg = (f'=(IF(I{r}="",{pW},I{r})*{WCELL["Winks"]}'
               f'+IF(J{r}="",{pN},J{r})*{WCELL["Norris"]}'
               f'+IF(K{r}="",{pF},K{r})*{WCELL["FantasyPros"]})'
               f'/({WCELL["Winks"]}+{WCELL["Norris"]}+{WCELL["FantasyPros"]})')
        rng = f'=IF(COUNT(I{r}:K{r})<2,"",MAX(I{r}:K{r})-MIN(I{r}:K{r}))'
        vals = [idx+1, p["tier"], p["ptier"], p["name"], p["pos"], p["posrank"], p["team"], avg,
                rk.get("Winks"), rk.get("Norris"), rk.get("FantasyPros"), rng, None, None]
        for ci, v in enumerate(vals):
            c = ws.cell(row=r, column=1+ci, value=v)
            c.font = Font(name=ARIAL, size=9); c.border = box
            if ci not in (3, 13): c.alignment = Alignment(horizontal="center")
            if ci == 7: c.number_format = "0.0"
            if ci == 4:
                c.fill = PatternFill("solid", fgColor=POS_FILL.get(p["pos"], "FFFFFF"))
                c.font = Font(name=ARIAL, size=9, bold=True)
            if ci in (12, 13): c.fill = PatternFill("solid", fgColor="FFF9DB")

    last = 4 + len(rows)
    ws.auto_filter.ref = f"A4:N{last}"
    ws.freeze_panes = "A5"
    for i, w in enumerate(WIDTHS):
        ws.column_dimensions[get_column_letter(i+1)].width = w

    dv = DataValidation(type="list", formula1='"ME,TAKEN"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f"M5:M{last}")

    rng_all = f"A5:N{last}"
    ws.conditional_formatting.add(rng_all, FormulaRule(
        formula=['$M5="TAKEN"'], fill=PatternFill("solid", fgColor="EDEDED"),
        font=Font(name=ARIAL, size=9, color="AAAAAA", strike=True)))
    ws.conditional_formatting.add(rng_all, FormulaRule(
        formula=['$M5="ME"'], fill=PatternFill("solid", fgColor="DCF5E4")))
    ws.conditional_formatting.add(f"L5:L{last}", CellIsRule(
        operator="greaterThanOrEqual", formula=["42"],
        fill=PatternFill("solid", fgColor="FFE9A8"), font=Font(name=ARIAL, size=9, bold=True)))

wb.save(ROOT / "output" / "draft-cheat-sheet.xlsx")
print("saved")
