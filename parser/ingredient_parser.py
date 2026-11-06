"""Parses free-text ingredient lists into structured items (with nesting, percentages,
INS/E-numbers, functional classes, quantities and allergen statements)."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from parser.normalizer import (Normalizer, function_class, normalize_phrase,
                               parse_ins_code, slug)

_QTY = re.compile(r"(\d+(?:\.\d+)?)\s*(mg/kg|ppm|mg/l)", re.I)
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@dataclass
class ParsedIngredient:
    raw: str
    canonical: str
    display: str
    match: str                       # exact | ins | partial | ins_unknown | none
    position: int
    depth: int = 0
    parent: Optional[str] = None
    percent: Optional[float] = None
    function: Optional[str] = None
    quantity_mg_kg: Optional[float] = None


@dataclass
class ParsedLabel:
    items: list = field(default_factory=list)
    declared_allergens: set = field(default_factory=set)
    advisory_allergens: set = field(default_factory=set)
    notes: list = field(default_factory=list)


def split_top(text: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([": depth += 1
        elif ch in ")]": depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _split_brackets(part: str):
    """'Head (inner) tail' -> (head, inner) using the first balanced bracket pair."""
    m = re.search(r"[(\[]", part)
    if not m: return part.strip(), None
    depth = 0
    for j in range(m.start(), len(part)):
        if part[j] in "([": depth += 1
        elif part[j] in ")]":
            depth -= 1
            if depth == 0:
                return part[: m.start()].strip(), part[m.start() + 1: j].strip()
    return part[: m.start()].strip(), part[m.start() + 1:].strip()


def _statement_tokens(text: str) -> list[str]:
    t = re.sub(r"\b(traces? of|may contain|contains?|allergen advice|allergy advice|and|&)\b", ",", text, flags=re.I)
    return [x.strip(" :.-") for x in re.split(r"[,/;]", t) if x.strip(" :.-")]


def parse_ingredients(text: str, nz: Normalizer) -> ParsedLabel:
    out = ParsedLabel()
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    text = re.sub(r"^\s*ingredients?\s*[:\-]\s*", "", text, flags=re.I)
    if not text:
        return out
    # 1. allergen statements are separate sentences: "Contains: milk, soy." / "May contain traces of nuts."
    sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)\s*", text) if s.strip()]
    ing_parts = []
    for s in sentences:
        low = s.lower()
        if re.match(r"^(allergen|allergy) advice", low) or low.startswith("contains") or low.startswith("may contain"):
            may = low.startswith("may contain") or "may contain" in low
            for tok in _statement_tokens(s):
                a = nz.resolve_allergen(tok)
                if a:
                    (out.advisory_allergens if may else out.declared_allergens).add(a)
                else:
                    out.notes.append(f"Allergen statement token '{tok}' not recognised as an allergen")
        else:
            ing_parts.append(s)
    body = ", ".join(ing_parts)
    pos = 0
    for top in split_top(body):
        pos += 1
        _parse_item(top, nz, out, pos, 0, None, None)
    return out


def _add(out, nz, raw, pos, depth, parent, function=None, percent=None, qty=None):
    res = nz.resolve_ingredient(raw)
    item = ParsedIngredient(raw.strip(), res.canonical, res.display, res.match, pos, depth,
                            parent, percent, function, qty)
    out.items.append(item)
    if res.match == "partial":
        out.notes.append(f"'{raw.strip()}' only partially matched knowledge-base entry '{res.display}'")
    return item


def _parse_item(part, nz, out, pos, depth, parent, function):
    qty = None
    m = _QTY.search(part)
    if m:
        qty = float(m.group(1)); part = _QTY.sub(" ", part).strip(" -:")
    pm = _PCT.search(part)
    pct = float(pm.group(1)) if pm else None
    clean = _PCT.sub(" ", part).strip()
    # "Preservative 211" / "Colour E102"
    m2 = re.match(r"^([A-Za-z ]+?)\s+((?:e|ins)?\s*\d{3,4}[a-z]?)$", clean, re.I)
    if m2 and function_class(m2.group(1)) and not function:
        _add(out, nz, m2.group(2), pos, depth, parent, function_class(m2.group(1)), pct, qty)
        return
    head, inner = _split_brackets(clean)
    head = head.strip(" -:")
    fn = function_class(head) if head else None
    if inner is None:
        if fn and not function:
            out.notes.append(f"Functional class '{head}' listed without an additive name/number")
            return
        if not head:
            return
        _add(out, nz, head, pos, depth, parent, function, pct, qty)
        return
    kids = split_top(inner)
    if fn:                                           # Preservative (211, 202) -> additives with declared function
        last = None
        for k in kids:
            if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(mg/kg|ppm|mg/l)\s*", k, re.I) and last is not None:
                last.quantity_mg_kg = float(re.match(r"\s*(\d+(?:\.\d+)?)", k).group(1)); continue
            sub = _parse_sub(k, nz, out, pos, depth, parent, fn, qty)
            last = sub or last
        return
    if not head:                                     # "(45%)" or bare bracket
        head = inner; kids = []
    only_codes = len(kids) == 1 and parse_ins_code(kids[0]) is not None
    if only_codes:
        res = nz.resolve_ingredient(head)
        raw = kids[0] if res.match == "none" else head
        _add(out, nz, raw, pos, depth, parent, function, pct, qty)
        return
    if len(kids) == 1 and _PCT.fullmatch(kids[0].strip()):   # "Wheat flour (45%)"
        _add(out, nz, head, pos, depth, parent, function, float(_PCT.search(kids[0]).group(1)), qty)
        return
    h = _add(out, nz, head, pos, depth, parent, function, pct, qty)   # compound ingredient
    for k in kids:
        _parse_item(k, nz, out, pos, depth + 1, h.canonical, function)


def _parse_sub(k, nz, out, pos, depth, parent, fn, qty0):
    qty = None
    m = _QTY.search(k)
    if m:
        qty = float(m.group(1)); k = _QTY.sub(" ", k).strip(" -:")
    k = _PCT.sub(" ", k).strip(" -:")
    if not k: return None
    item = _add(out, nz, k, pos, depth + 1 if depth else depth, parent, fn, None, qty or qty0)
    return item
