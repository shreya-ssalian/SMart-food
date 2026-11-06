"""Incomplete-information handling.

Classical logic under the closed-world assumption would silently treat "unknown" as
"safe".  SmartFood AI therefore (1) derives explicit gap/3 facts, (2) adds parsing
uncertainty, and (3) turns both into a confidence level that tempers the verdict."""
from __future__ import annotations
from models import Gap

_MSG = {
    "unknown_ingredient": ("Ingredient '{s}' is not in the knowledge base, so allergen/additive checks could not cover it.", "medium"),
    "additive_no_limit_data": ("No permission/limit data for additive '{s}' in this product's category - it could not be verified.", "medium"),
    "nutrient_missing": ("Nutrient '{s}' is needed by an applicable rule but was not found in the nutrition text.", "medium"),
    "category_unknown": ("Product category is missing or not in the knowledge base - category-specific rules were skipped.", "high"),
    "no_ingredients": ("No ingredient list was provided - nothing could be analysed.", "high"),
}


def collect_gaps(ctx) -> list[Gap]:
    gaps: list[Gap] = []
    for _, kind, subj in ctx.forward.query("gap", ctx.pid):
        msg, impact = _MSG.get(kind, ("{s}", "medium"))
        gaps.append(Gap(kind, str(subj), msg.format(s=ctx.kb.display(subj) if subj != "none" else ""), impact))
    for n in ctx.notes + ctx.label.notes + ctx.nutrition.notes:
        gaps.append(Gap("parse_note", "", n, "low"))
    for it in ctx.label.items:
        if it.match == "ins_unknown":
            pass  # already reported through unknown_ingredient
    if ctx.kb.is_demo:
        gaps.append(Gap("demo_kb", "", "The knowledge base is ILLUSTRATIVE DEMO DATA - conclusions are not authoritative.", "high"))
    seen, uniq = set(), []
    for g in gaps:
        if (g.kind, g.subject, g.message) not in seen:
            seen.add((g.kind, g.subject, g.message)); uniq.append(g)
    return uniq


def assess_confidence(ctx, gaps: list[Gap]) -> str:
    items = ctx.label.items
    if not items:
        return "very low"
    recognised = sum(1 for i in items if i.match in ("exact", "ins")) / len(items)
    score = recognised
    if not ctx.nutrition.values: score -= 0.2
    if ctx.category is None: score -= 0.15
    score -= 0.05 * sum(1 for g in gaps if g.kind in ("additive_no_limit_data",))
    if ctx.kb.is_demo: score -= 0.1
    return "high" if score >= 0.8 else "medium" if score >= 0.55 else "low"
