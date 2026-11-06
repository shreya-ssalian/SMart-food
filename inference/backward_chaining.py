"""Backward chaining (goal-driven, SLD-resolution with negation-as-failure).

Given a goal such as  concern(p1, allergy_alert, milk, D, S)  the engine searches for
rules whose head unifies with it and recursively proves each premise from the facts."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import count
from typing import Optional

from config import MAX_PROOF_DEPTH
from explanation.proof_tree import ProofNode
from inference.terms import (FactBase, Literal, Rule, Var, eval_cmp, fmt_term,
                             rename_rule, resolve_literal, unify_args, walk)


@dataclass
class Solution:
    goal: Literal                 # fully instantiated goal
    bindings: dict                # variable name -> value (for variables in the query)
    proof: ProofNode


class SearchLimit(Exception):
    pass


class BackwardChainer:
    def __init__(self, rules: list[Rule], base: FactBase,
                 max_depth: int = MAX_PROOF_DEPTH, step_limit: int = 400000):
        self.base = base
        self.by_head: dict[str, list[Rule]] = {}
        for r in rules:
            self.by_head.setdefault(r.head.pred, []).append(r)
        self.max_depth, self.step_limit = max_depth, step_limit
        self._ids, self.steps = count(), 0

    # -- core search ---------------------------------------------------------
    def _lit(self, lit: Literal, s, depth):
        if depth > self.max_depth:
            return
        self.steps += 1
        if self.steps > self.step_limit:
            raise SearchLimit("backward-chaining step limit exceeded")
        a0 = walk(lit.args[0], s) if lit.args else None
        bound = bool(lit.args) and not isinstance(a0, Var)
        for args in self.base.candidates(lit.pred, a0, bound):
            s2 = unify_args(lit.args, args, s)
            if s2 is not None:
                yield s2, ("fact", lit, None, [])
        for rule in self.by_head.get(lit.pred, ()):
            r = rename_rule(rule, next(self._ids))
            s2 = unify_args(r.head.args, lit.args, s)
            if s2 is None:
                continue
            for s3, kids in self._body(r.body, 0, s2, depth + 1):
                yield s3, ("rule", lit, rule, kids)

    def _body(self, body, i, s, depth):
        if i == len(body):
            yield s, []
            return
        g = body[i]
        if g.kind == "pos":
            for s2, node in self._lit(g.lit, s, depth):
                for s3, rest in self._body(body, i + 1, s2, depth):
                    yield s3, [node] + rest
        elif g.kind == "neg":
            if next(self._lit(g.lit, s, depth), None) is None:
                for s3, rest in self._body(body, i + 1, s, depth):
                    yield s3, [("naf", g.lit, None, [])] + rest
        else:
            if eval_cmp(g.op, g.left, g.right, s):
                for s3, rest in self._body(body, i + 1, s, depth):
                    yield s3, [("builtin", (g.op, g.left, g.right), None, [])] + rest

    # -- public API ----------------------------------------------------------
    def _convert(self, node, s) -> ProofNode:
        kind, payload, rule, kids = node
        if kind == "builtin":
            op, l, r = payload
            return ProofNode(f"{fmt_term(walk(l, s))} {op} {fmt_term(walk(r, s))}", "builtin")
        lit = resolve_literal(payload, s)
        if kind == "naf":
            return ProofNode(f"no proof exists for {lit}", "naf", pred=lit.pred, args=lit.args)
        n = ProofNode(str(lit), kind, rule.id if rule else None,
                      rule.description if rule else "", lit.pred, lit.args)
        n.children = [self._convert(k, s) for k in kids]
        return n

    def prove(self, goal: Literal, max_solutions: Optional[int] = None) -> list[Solution]:
        out, seen = [], set()
        qvars = [a for a in goal.args if isinstance(a, Var)]
        for s, node in self._lit(goal, {}, 0):
            g = resolve_literal(goal, s)
            key = (g.pred, g.args)
            if key in seen:
                continue
            seen.add(key)
            out.append(Solution(g, {v.name: walk(v, s) for v in qvars}, self._convert(node, s)))
            if max_solutions and len(out) >= max_solutions:
                break
        return out

    def holds(self, goal: Literal) -> bool:
        return bool(self.prove(goal, 1))
