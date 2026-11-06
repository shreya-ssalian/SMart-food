"""Allergen reasoning: derivative/ontology closure, profile alerts, declaration checks."""
from models import Finding
from modules._base import collect

KINDS = {"allergy_alert", "allergy_possible", "undeclared_allergen"}


def check(ctx) -> list[Finding]:
    return (collect(ctx, KINDS, "allergen", "concern") +
            collect(ctx, KINDS, "allergen", "possible_concern"))


def inventory(ctx) -> dict:
    """allergen -> {'contains': [ingredients], 'may_contain': [...], 'declared': bool}"""
    inv: dict = {}
    for _, a, i, _s in ctx.forward.query("allergen_present", ctx.pid):
        inv.setdefault(a, {"contains": [], "may_contain": []})["contains"].append(i)
    for _, a, i, _s in ctx.forward.query("allergen_possible", ctx.pid):
        inv.setdefault(a, {"contains": [], "may_contain": []})["may_contain"].append(i)
    declared = {r[1] for r in ctx.forward.query("declared_allergen", ctx.pid)}
    for a, d in inv.items():
        d["contains"], d["may_contain"] = sorted(set(d["contains"])), sorted(set(d["may_contain"]))
        d["declared"] = a in declared
    return inv
