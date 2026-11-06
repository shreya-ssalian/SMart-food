"""Parses nutrition-table text into canonical values per 100 g / 100 ml."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import config

ALIASES = {
    "energy": ["energy", "calories", "calorie"],
    "saturated_fat": ["saturated fatty acids", "of which saturates", "saturated fat", "saturates", "sat fat"],
    "trans_fat": ["trans fatty acids", "trans fat"],
    "fat": ["total fat", "fats", "fat"],
    "added_sugars": ["added sugars", "added sugar"],
    "sugars": ["total sugars", "sugars", "sugar"],
    "carbohydrate": ["total carbohydrate", "carbohydrates", "carbohydrate", "carbs"],
    "protein": ["proteins", "protein"],
    "fibre": ["dietary fibre", "dietary fiber", "fibre", "fiber"],
    "sodium": ["sodium"],
    "salt": ["salt"],
    "cholesterol": ["cholesterol"],
}
_NAME_TO_ID = {a: n for n, al in ALIASES.items() for a in al}
_NAMES = sorted(_NAME_TO_ID, key=len, reverse=True)
_RX = re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in _NAMES) +
                 r")(?![a-z])\s*[:\-=]?\s*[<≤~]?\s*(\d+(?:[.,]\d+)?)\s*(kcal|kj|mcg|µg|ug|mg|kg|g|ml)?", re.I)


@dataclass
class NutrientValue:
    value: float
    unit: str
    derived: bool = False
    raw: str = ""


@dataclass
class NutritionParse:
    values: dict = field(default_factory=dict)
    basis: str = "unknown"
    serving_size: Optional[float] = None
    notes: list = field(default_factory=list)


def _convert(n: str, v: float, unit: Optional[str]) -> float:
    canon = config.CANONICAL_UNITS.get(n, config.DEFAULT_UNIT)
    unit = (unit or canon).lower()
    if n == "energy":
        return v / 4.184 if unit == "kj" else v
    if unit == canon: return v
    if unit in config.UNIT_TO_G and canon in config.UNIT_TO_G:
        return v * config.UNIT_TO_G[unit] / config.UNIT_TO_G[canon]
    return v


def parse_nutrition(text: str) -> NutritionParse:
    out = NutritionParse()
    t = (text or "").strip()
    if not t:
        return out
    low = t.lower()
    ms = re.search(r"(?:per\s+serving|serving\s+size|per\s+portion)[^0-9]{0,15}(\d+(?:\.\d+)?)\s*(g|ml)", low)
    if ms: out.serving_size = float(ms.group(1))
    if re.search(r"per\s*100\s*(g|ml)|100\s*(g|ml)", low):
        out.basis = "per_100"
    elif ms or "per serving" in low:
        out.basis = "per_serving"
    else:
        out.basis = "assumed_per_100"
        out.notes.append("Basis (per 100 g / per serving) not stated - assumed per 100 g/ml")
    factor = 1.0
    if out.basis == "per_serving":
        if out.serving_size:
            factor = 100.0 / out.serving_size
            out.notes.append(f"Values converted from per serving ({out.serving_size:g}) to per 100 g/ml")
        else:
            out.notes.append("Values are per serving but the serving size is unknown - nutrition values ignored")
            return out
    segment = re.sub(r"per\s+serving[^,;\n]*", "", low) if out.basis != "per_serving" else low
    kcal = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", low)
    for m in _RX.finditer(segment):
        n = _NAME_TO_ID[m.group(1).lower()]
        if n in out.values: continue
        v = float(m.group(2).replace(",", "."))
        unit = (m.group(3) or "").lower() or None
        if n == "energy":
            if kcal: v, unit = float(kcal.group(1).replace(",", ".")), "kcal"
        val = _convert(n, v, unit) * factor
        out.values[n] = NutrientValue(round(val, 4), config.CANONICAL_UNITS.get(n, config.DEFAULT_UNIT),
                                      False, f"{m.group(2)} {unit or ''}".strip())
    k = config.SALT_TO_SODIUM_MG_PER_G
    if "sodium" not in out.values and "salt" in out.values:
        out.values["sodium"] = NutrientValue(round(out.values["salt"].value * k, 2), "mg", True)
        out.notes.append("Sodium derived from salt (1 g salt ≈ 400 mg sodium)")
    elif "salt" not in out.values and "sodium" in out.values:
        out.values["salt"] = NutrientValue(round(out.values["sodium"].value / k, 3), "g", True)
        out.notes.append("Salt derived from sodium (400 mg sodium ≈ 1 g salt)")
    if not out.values:
        out.notes.append("No nutrient values could be read from the nutrition text")
    return out
