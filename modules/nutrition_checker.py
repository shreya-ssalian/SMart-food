"""Nutrition reasoning: category thresholds and substantiation of claims."""
from models import Finding
from modules._base import collect

KINDS = {"nutrient_threshold", "claim_unsupported"}


def check(ctx) -> list[Finding]:
    return collect(ctx, KINDS, "nutrition", "concern")


def table(ctx) -> list[dict]:
    flagged = set()
    for _, r, n, v, s in ctx.forward.query("nutrition_breach", ctx.pid):
        flagged.add(n)
    return [{"nutrient": n.replace("_", " ").title(),
             "id": n, "per 100 g/ml": v.value, "unit": v.unit,
             "note": "derived" if v.derived else "", "flagged": n in flagged}
            for n, v in ctx.nutrition.values.items()]
