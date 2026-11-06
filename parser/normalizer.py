"""Text normalisation helpers shared by the parsers."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from config import FUNCTION_CLASSES, FUNCTION_NORMALISE


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
    if t and t[0].isdigit():
        t = "x" + t
    return t


def normalize_phrase(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text)).lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_INS = re.compile(r"^(?:(?:e|ins)\s*)?(\d{3,4})\s*(?:\(?([a-z]|[ivx]+)\)?)?$")


def parse_ins_code(text: str) -> Optional[str]:
    """'INS 102', 'E102', '150d', '322(i)' -> '102', '150d', '322i'."""
    t = normalize_phrase(text).replace(" ", "")
    m = re.match(r"^(?:e|ins)?(\d{3,4})([a-z]{0,3})$", t)
    return (m.group(1) + m.group(2)) if m else None


def function_class(text: str) -> Optional[str]:
    t = normalize_phrase(text)
    cands = [t]
    for suf in ("s", "es"):
        if t.endswith(suf): cands.append(t[: -len(suf)])
    for c in cands:
        if c in FUNCTION_CLASSES:
            return FUNCTION_NORMALISE.get(c, c).replace(" ", "_")
    return None


@dataclass
class Resolution:
    canonical: str
    match: str           # exact | ins | partial | ins_unknown | none
    display: str


class Normalizer:
    def __init__(self, kb):
        self.kb = kb

    def _lookup(self, phrase: str):
        a = self.kb.alias_map
        if phrase in a: return a[phrase]
        for suf in ("s", "es"):
            if phrase.endswith(suf) and phrase[: -len(suf)] in a:
                return a[phrase[: -len(suf)]]
        return None

    def resolve_ingredient(self, raw: str) -> Resolution:
        phrase = normalize_phrase(raw)
        phrase = re.sub(r"\b(organic|natural identical|permitted)\b", " ", phrase)
        phrase = re.sub(r"\s+", " ", phrase).strip()
        code = parse_ins_code(phrase)
        if code:
            aid = self.kb.ins_to_additive.get(code)
            if aid:
                return Resolution(aid, "ins", self.kb.display(aid))
            return Resolution(f"ins_{code}", "ins_unknown", f"INS {code}")
        hit = self._lookup(phrase)
        if hit:
            return Resolution(hit, "exact", self.kb.display(hit))
        best = None
        for alias, cid in self.kb.alias_map.items():
            if len(alias) >= 4 and re.search(rf"\b{re.escape(alias)}s?\b", phrase):
                if best is None or len(alias) > len(best[0]):
                    best = (alias, cid)
        if best:
            return Resolution(best[1], "partial", self.kb.display(best[1]))
        return Resolution(slug(phrase) or "unknown", "none", raw.strip())

    def resolve_allergen(self, raw: str) -> Optional[str]:
        phrase = normalize_phrase(raw)
        hit = self._lookup(phrase)
        return hit if hit in self.kb.allergens else None

    def resolve_claim(self, raw: str) -> str:
        phrase = normalize_phrase(raw)
        return self._lookup(phrase) or slug(phrase)
