"""SmartFood AI pipeline:  parse -> assert facts -> forward chaining -> domain checkers
-> backward-chaining verification -> uncertainty + conflict resolution -> explanation."""
from __future__ import annotations
import re
from typing import Optional

import config
from explanation.explanation_generator import Explainer
from inference import conflict_resolver, uncertainty_handler
from inference.backward_chaining import BackwardChainer
from inference.forward_chaining import ForwardChainer
from inference.terms import FactBase
from knowledge.kb_loader import KnowledgeBase, load_kb, load_rules
from models import AnalysisContext, AnalysisResult
from modules import (additive_checker, allergen_checker, interaction_checker,
                     nutrition_checker, regulation_checker)
from parser.ingredient_parser import parse_ingredients
from parser.normalizer import Normalizer, slug
from parser.nutrition_parser import parse_nutrition


def _split_list(text) -> list[str]:
    if isinstance(text, (list, tuple, set)):
        return [str(t).strip() for t in text if str(t).strip()]
    return [t.strip() for t in re.split(r"[;,\n]", str(text or "")) if t.strip()]


class SmartFoodAnalyzer:
    def __init__(self, kb: Optional[KnowledgeBase] = None):
        self.kb = kb or load_kb()
        self.rules, self.static_facts = load_rules()
        self.nz = Normalizer(self.kb)
        self.explainer = Explainer(self.kb)

    # ------------------------------------------------------------------ facts
    def _assert_product(self, base: FactBase, pid, product, label, nutrition, claims, profile, category):
        A = lambda p, *a: base.add(p, tuple(a))
        A("product", pid)
        if category: A("product_category", pid, category)
        for it in label.items:
            A("ingredient", pid, it.canonical)
            if it.function: A("function_declared", pid, it.canonical)
            if it.quantity_mg_kg is not None: A("additive_amount", pid, it.canonical, float(it.quantity_mg_kg))
        for a in label.declared_allergens: A("declared_allergen", pid, a)
        for a in label.advisory_allergens: A("advisory_allergen", pid, a)
        for c in claims: A("has_claim", pid, c)
        for a in profile: A("allergy_profile", pid, a)
        for n, v in nutrition.values.items(): A("nutrient", pid, n, float(v.value))

    # ---------------------------------------------------------------- analyse
    def analyze(self, product: dict) -> AnalysisResult:
        kb = self.kb
        pid = "p_" + (slug(product.get("product_id") or product.get("name") or "product") or "product")
        notes: list[str] = []
        label = parse_ingredients(product.get("ingredients_text", ""), self.nz)
        nutrition = parse_nutrition(product.get("nutrition_text", ""))
        claims = [self.nz.resolve_claim(c) for c in _split_list(product.get("claims", ""))]
        profile = []
        for a in _split_list(product.get("allergy_profile", "")):
            aid = self.nz.resolve_allergen(a)
            if aid: profile.append(aid)
            else: notes.append(f"Allergy '{a}' is not in the knowledge base - it cannot be checked")
        cat_raw = (product.get("category_id") or "").strip()
        category = slug(cat_raw) if cat_raw else None
        if category and category not in kb.categories:
            notes.append(f"Category '{cat_raw}' is not in the knowledge base")
            category = None
        for c in claims:
            if not any(f[0] == c for f in kb.facts.by_pred.get("contradicts_claim", ()) ) and \
               not any(r["scope"] == ("claim", c) for r in kb.nutrition_rules.values()):
                notes.append(f"Claim '{c}' has no rules in the knowledge base - it was not verified")

        base = kb.facts.copy()
        for f in self.static_facts:
            base.add(f.pred, f.args)
        self._assert_product(base, pid, product, label, nutrition, claims, profile, category)
        backward = BackwardChainer(self.rules, base.copy())
        forward = ForwardChainer(self.rules, base)
        stats = forward.run()

        ctx = AnalysisContext(kb, product, pid, label, nutrition, claims, profile, category,
                              forward, backward, notes)
        findings = []
        for mod in (allergen_checker, additive_checker, interaction_checker,
                    nutrition_checker, regulation_checker):
            findings += mod.check(ctx)
        regulation_checker.link_regulations(ctx, findings)
        findings = conflict_resolver.resolve(findings)
        for f in findings:
            self.explainer.explain(f, ctx)
        gaps = uncertainty_handler.collect_gaps(ctx)
        confidence = uncertainty_handler.assess_confidence(ctx, gaps)
        verdict, text = conflict_resolver.verdict(findings, gaps, confidence, len(label.items))
        return AnalysisResult(
            product=product, pid=pid, verdict=verdict, verdict_text=text, findings=findings,
            gaps=gaps, confidence=confidence, label=label, nutrition=nutrition, claims=claims,
            allergy_profile=profile, category=category, forward_trace=forward.trace,
            forward_stats=stats, overrides=conflict_resolver.explain_overrides(ctx),
            kb_summary=kb.summary(), kb_issues=kb.validate(), ctx=ctx)

    # ----------------------------------------------------------------- queries
    def ask(self, result: AnalysisResult, goal_text: str, limit: int = 20):
        """Free-form backward-chaining query against the analysed product, e.g.
        allergen_present(p_x, A, I, S)."""
        from inference.terms import parse_goal
        goal = parse_goal(goal_text)
        return result.ctx.backward.prove(goal, limit)
