"""Conflict resolution and verdict ranking.

* Specificity conflicts between general and category-specific additive rules are resolved
  *inside* the logic (R-ADD-3/R-ADD-4); `explain_overrides` reports which general rule
  was overridden by which specific rule.
* Evidence conflicts (a 'possible' allergy finding next to a confirmed one) are removed here.
* The verdict is the highest-ranked outcome, tempered by data gaps."""
from __future__ import annotations
import config
from models import Finding


def explain_overrides(ctx) -> list[dict]:
    cand = ctx.forward.query("limit_candidate", ctx.pid)
    eff = {(r[1], r[2]) for r in ctx.forward.query("effective_limit", ctx.pid)}
    out = []
    for _, a, c, perm, mx, src in cand:
        if (a, c) not in eff:
            winners = [e for e in ctx.forward.query("effective_limit", ctx.pid, a)]
            w = winners[0] if winners else None
            out.append({"additive": a, "overridden_category": c, "overridden_permitted": perm,
                        "winning_category": w[2] if w else None,
                        "winning_permitted": w[3] if w else None})
    return out


def resolve(findings: list[Finding]) -> list[Finding]:
    confirmed_allergens = {f.subject for f in findings if f.kind == "allergy_alert"}
    kept = [f for f in findings
            if not (f.kind == "allergy_possible" and f.subject in confirmed_allergens)]
    kept.sort(key=lambda f: (-config.SEVERITY_RANK.get(f.severity, 0), not f.confirmed, f.kind, str(f.subject)))
    return kept


VERDICTS = {
    "ALLERGY_ALERT": "Contains an allergen from your allergy profile.",
    "REGULATORY_CONCERN": "Potential regulatory non-compliance found - see reportable findings.",
    "CAUTION": "Concerns found (advisory) - review the findings.",
    "UNCERTAIN": "Nothing confirmed, but some checks are only possible/unverified - see data gaps.",
    "NO_CONCERNS_FOUND": "No concerns found by the rules in the knowledge base.",
    "INSUFFICIENT_DATA": "Not enough information to assess this product.",
}


def verdict(findings: list[Finding], gaps, confidence: str, n_items: int) -> tuple[str, str]:
    confirmed = [f for f in findings if f.confirmed]
    if n_items == 0:
        v = "INSUFFICIENT_DATA"
    elif any(f.severity == "critical" for f in confirmed):
        v = "ALLERGY_ALERT"
    elif any(f.reportable for f in confirmed):
        v = "REGULATORY_CONCERN"
    elif confirmed:
        v = "CAUTION"
    elif any(not f.confirmed for f in findings) or confidence in ("low", "very low"):
        v = "UNCERTAIN"
    else:
        v = "NO_CONCERNS_FOUND"
    return v, VERDICTS[v]
