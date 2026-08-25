"""The player match key, shared by the aggregator and the live fetchers.

Moved verbatim from agg_three.py so fetch_live.py can key its sidecar data
the same way without duplicating the logic. Nothing about the key changed —
see the mkey docstring and CLAUDE.md before touching any of it.
"""
import re, unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm_tokens(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"['’.]", "", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return [t for t in s.split() if t]


def mkey(name, pos, team):
    """first-initial + surname + generational suffix + pos + team.

    The suffix is part of the identity, NOT noise. Bijan Robinson and Brian
    Robinson Jr. are both RB/ATL and both abbreviate to 'B. Robinson' - the
    'Jr.' is the only thing separating a top-5 pick from a handcuff. Stripping
    it silently merged them and deleted Bijan from the board.

    Surname is the last NON-suffix token, so 'L. Allen Jr.' still keys on
    'allen', not 'jr'. Team stays in the key to separate A.J. Brown from
    Amon-Ra St. Brown, and Travis Etienne Jr. (NO) from Trevor Etienne (CAR).
    """
    if pos == "DST":
        return f"DST|{team}"
    toks = norm_tokens(name)
    suffix = ""
    while toks and toks[-1] in SUFFIXES:
        suffix = toks[-1] + suffix
        toks = toks[:-1]
    if not toks:
        return None
    return f"{toks[0][0]}|{toks[-1]}|{suffix}|{pos}|{team}"
