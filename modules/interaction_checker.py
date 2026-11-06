"""Ingredient-relationship reasoning: problematic combinations and claim contradictions."""
from models import Finding
from modules._base import collect

KINDS = {"ingredient_interaction", "claim_contradiction"}


def check(ctx) -> list[Finding]:
    return collect(ctx, KINDS, "interaction", "concern")
