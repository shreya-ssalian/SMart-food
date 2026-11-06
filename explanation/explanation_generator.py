"""Turns logical conclusions and proof trees into plain-English explanations."""
from __future__ import annotations
from typing import Optional

from explanation.proof_tree import ProofNode, render_text
from models import Finding


class Explainer:
    def __init__(self, kb):
        self.kb = kb

    def name(self, x) -> str:
        return self.kb.display(x) if isinstance(x, str) else str(x)

    def names(self, xs) -> str:
        return ", ".join(sorted({self.name(x) for x in xs if x not in ("label_advisory",)})) or "-"

    # --- single facts -------------------------------------------------------
    def describe_fact(self, pred: str, args: tuple) -> Optional[str]:
        n = self.name
        T = {
            "ingredient": lambda p, i: f"the label lists {n(i)}",
            "has": lambda p, i: f"the product has {n(i)} (directly or as a type of one of its ingredients)",
            "is_a": lambda x, y: f"{n(x)} is a kind of {n(y)}",
            "ancestor": lambda x, y: f"{n(x)} is (transitively) a kind of {n(y)}",
            "allergen_source": lambda i, a, rel, s: f"{n(i)} {'contains' if rel == 'contains' else 'may contain'} {n(a)} [{s}]",
            "allergen_present": lambda p, a, i, s: f"{n(a)} is present (via {n(i)})",
            "allergy_profile": lambda p, a: f"you listed {n(a)} in your allergy profile",
            "declared_allergen": lambda p, a: f"the label declares {n(a)}",
            "product_category": lambda p, c: f"the product category is {n(c)}",
            "in_category": lambda p, c: f"the product falls under category {n(c)}",
            "cat_parent": lambda c, par: f"{n(c)} is a sub-category of {n(par)}",
            "cat_ancestor": lambda c, a: f"{n(c)} falls under {n(a)}",
            "additive_in": lambda p, a: f"{n(a)} is an additive in the product",
            "additive_limit": lambda a, c, perm, mx, s: f"{n(a)} is {'permitted' if perm == 'yes' else 'NOT permitted'} in {n(c)}"
                                                         + (f" (max {mx:g} mg/kg)" if isinstance(mx, (int, float)) else "") + f" [{s}]",
            "effective_limit": lambda p, a, c, perm, mx, s: f"the most specific rule for {n(a)} is the one for {n(c)} ({'permitted' if perm == 'yes' else 'not permitted'})",
            "more_specific_limit": lambda p, a, c: f"a more specific rule than the one for {n(c)} exists for {n(a)}",
            "additive_amount": lambda p, a, v: f"the label declares {n(a)} at {v:g} mg/kg",
            "has_claim": lambda p, c: f"the label claims '{n(c)}'",
            "contradicts_claim": lambda i, c, s: f"{n(i)} contradicts the claim '{n(c)}' [{s}]",
            "interacts_with": lambda a, b, s: f"{n(a)} and {n(b)} are a known problematic combination [{s}]",
            "nutrient": lambda p, nu, v: f"{nu.replace('_', ' ')} is {v:g} per 100 g/ml",
            "nutrition_rule": lambda r, nu, op, t, s: f"rule {r}: {nu.replace('_', ' ')} {dict(gt='>', gte='>=', lt='<', lte='<=')[op]} {t:g} [{s}]",
            "nutrition_applies": lambda p, r: f"nutrition rule {r} applies to this product",
            "label_rule": lambda r, req, s: f"labelling rule {r} requires '{req}' [{s}]",
            "label_applies": lambda p, r: f"labelling rule {r} applies to this product",
            "regulation_source": lambda reg, s: f"regulation {reg} is based on source {s}",
            "reportable_kind": lambda k: f"'{k}' findings are of a regulatory kind",
            "known_ingredient": lambda i: f"{n(i)} is in the knowledge base",
            "function_declared": lambda p, a: f"the label states the functional class of {n(a)}",
        }
        try:
            f = T.get(pred)
            return f(*args) if f else None
        except Exception:
            return None

    def proof_text(self, node: ProofNode, max_depth: int = 10) -> str:
        return render_text(node, self.describe_fact, max_depth)

    # --- findings -----------------------------------------------------------
    def explain(self, f: Finding, ctx) -> None:
        n, kb = self.name, self.kb
        regs = ", ".join(f"{kb.regulations.get(r, {}).get('regulation_id', r)} (clause {kb.regulations.get(r, {}).get('clause', '')})" for r in f.regulations)
        reg_txt = f" This is covered by {regs}." if regs else ""
        det = self.names(f.details)
        k, s = f.kind, f.subject
        if k == "allergy_alert":
            f.headline = f"Contains {n(s)} - an allergen in your profile"
            f.explanation = f"{n(s)} is present through: {det}. You listed {n(s)} in your allergy profile."
        elif k == "allergy_possible":
            via = "a 'may contain' statement on the label" if "label_advisory" in f.details else det
            f.headline = f"May contain {n(s)} (unconfirmed)"
            f.explanation = (f"{n(s)} is in your allergy profile and could be present via {via}. "
                             "The knowledge base cannot confirm it - check with the manufacturer.")
        elif k == "undeclared_allergen":
            f.headline = f"{n(s)} present but not declared on the label"
            f.explanation = (f"The ingredient list implies {n(s)} (via {det}) but there is no allergen "
                             f"declaration for it.{reg_txt}")
        elif k == "additive_not_permitted":
            f.headline = f"{n(s)} is not permitted in this category"
            f.explanation = f"The most specific rule for {n(s)} in {det} says it is not permitted.{reg_txt}"
        elif k == "additive_exceeds_limit":
            amt = next((i.quantity_mg_kg for i in ctx.label.items if i.canonical == s and i.quantity_mg_kg), None)
            lim = next((r[4] for r in ctx.forward.query("effective_limit", ctx.pid, s)), None)
            f.headline = f"{n(s)} exceeds its maximum level"
            f.explanation = (f"Declared {amt:g} mg/kg but the maximum for {det} is "
                             f"{lim:g} mg/kg.{reg_txt}") if amt and isinstance(lim, (int, float)) else f"Declared amount exceeds the limit.{reg_txt}"
        elif k == "ingredient_interaction":
            note = kb.interaction_notes.get((s, f.details[0]), "") if f.details else ""
            f.headline = f"{n(s)} + {n(f.details[0])}: problematic combination"
            f.explanation = note or "This ingredient combination is flagged in the knowledge base."
        elif k == "claim_contradiction":
            f.headline = f"Claim '{n(s)}' contradicted by ingredients"
            f.explanation = (f"The label claims '{n(s)}' but lists {det}, which contradicts it "
                             f"(derived through the ingredient taxonomy).{reg_txt}")
        elif k == "claim_unsupported":
            nut = f.details[0] if f.details else ""
            val = ctx.nutrition.values.get(nut)
            rule = next((rid for rid, r in kb.nutrition_rules.items()
                         if r["scope"] == ("claim", s) and r["nutrient"] == nut), None)
            r = kb.nutrition_rules.get(rule, {})
            sym = {"gt": "must not exceed", "gte": "must be below", "lt": "must be at least", "lte": "must exceed"}.get(r.get("op"), "vs")
            f.headline = f"Claim '{n(s)}' not supported by nutrition values"
            f.explanation = (f"{nut.replace('_', ' ').title()} is {val.value:g} {val.unit} per 100 g/ml, but for this claim it "
                             f"{sym} {r.get('threshold', 0):g} {r.get('unit', '')}.{reg_txt}") if val and r else f"Nutrition values do not support the claim.{reg_txt}"
        elif k == "nutrient_threshold":
            val = ctx.nutrition.values.get(s)
            r = kb.nutrition_rules.get(f.details[0], {}) if f.details else {}
            op = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}.get(r.get("op"), "?")
            f.headline = f"{s.replace('_', ' ').title()} is high"
            f.explanation = (f"{val.value:g} {val.unit} per 100 g/ml ({op} {r['threshold']:g}) - rule {f.details[0]}. "
                             "This is dietary guidance, not a regulatory limit.") if val and r else "Nutrient above threshold."
        elif k == "missing_label_info":
            if s == "nutrition_information":
                f.headline = "No nutrition information supplied"
                f.explanation = ("A labelling rule requires nutrition information but none was provided. "
                                 "If the label has a nutrition table, paste it to complete the check.")
            else:
                f.headline = f"{n(det)}: functional class not stated"
                f.explanation = f"The additive {det} is listed without its functional class name.{reg_txt}"
        else:
            f.headline, f.explanation = f"{k}: {s}", det

    def finding_proof(self, f: Finding, max_depth=10) -> str:
        return "\n\n".join(self.proof_text(p, max_depth) for p in f.proofs[:3])
