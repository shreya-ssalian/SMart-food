"""Forward chaining (data-driven) with stratified negation-as-failure.

Starting from known facts (knowledge base + the product's parsed label) the engine
repeatedly fires every rule whose premises match, adding new facts until a fixpoint.
Every derived fact stores its derivation, so a proof tree can be reconstructed."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from explanation.proof_tree import ProofNode
from inference.terms import (FactBase, Literal, Rule, Var, eval_cmp, fmt_term,
                             resolve_literal, unify_args, walk)


@dataclass
class Derivation:
    rule_id: str
    description: str
    premises: list            # [(pred, args)]
    checks: list              # [('neg', Literal) | ('cmp', text)]


@dataclass
class TraceStep:
    step: int
    stratum: int
    rule_id: str
    fact: str


def stratify(rules: list[Rule]) -> dict[str, int]:
    preds = {r.head.pred for r in rules}
    for r in rules:
        for g in r.body:
            if g.lit: preds.add(g.lit.pred)
    st = {p: 0 for p in preds}
    for _ in range(len(preds) + 2):
        changed = False
        for r in rules:
            h = r.head.pred
            for g in r.body:
                if g.kind == "cmp": continue
                need = st[g.lit.pred] + (1 if g.kind == "neg" else 0)
                if need > st[h]:
                    st[h] = need; changed = True
        if not changed:
            return st
    raise ValueError("Rule set is not stratifiable (negation inside a recursive cycle).")


class ForwardChainer:
    def __init__(self, rules: list[Rule], base: FactBase):
        self.rules = rules
        self.facts = base
        self.base_keys = {(p, a) for p, s in base.by_pred.items() for a in s}
        self.derivations: dict[tuple, Derivation] = {}
        self.trace: list[TraceStep] = []
        self.iterations = 0
        self.strata = stratify(rules)

    # -- body matching -------------------------------------------------------
    def _body(self, body, i, s, prem, checks):
        if i == len(body):
            yield s, prem, checks
            return
        g = body[i]
        if g.kind == "pos":
            lit = g.lit
            a0 = walk(lit.args[0], s) if lit.args else None
            bound = bool(lit.args) and not isinstance(a0, Var)
            for args in self.facts.candidates(lit.pred, a0, bound):
                s2 = unify_args(lit.args, args, s)
                if s2 is not None:
                    yield from self._body(body, i + 1, s2, prem + [(lit.pred, args)], checks)
        elif g.kind == "neg":
            lit = g.lit
            a0 = walk(lit.args[0], s) if lit.args else None
            bound = bool(lit.args) and not isinstance(a0, Var)
            if not any(unify_args(lit.args, a, s) is not None
                       for a in self.facts.candidates(lit.pred, a0, bound)):
                yield from self._body(body, i + 1, s, prem,
                                      checks + [("neg", resolve_literal(lit, s))])
        else:
            if eval_cmp(g.op, g.left, g.right, s):
                txt = f"{fmt_term(walk(g.left, s))} {g.op} {fmt_term(walk(g.right, s))}"
                yield from self._body(body, i + 1, s, prem, checks + [("cmp", txt)])

    def run(self) -> dict:
        by_stratum: dict[int, list[Rule]] = {}
        for r in self.rules:
            by_stratum.setdefault(self.strata[r.head.pred], []).append(r)
        step = 0
        for st in sorted(by_stratum):
            while True:
                self.iterations += 1
                new = []
                for r in by_stratum[st]:
                    for s, prem, checks in self._body(r.body, 0, {}, [], []):
                        h = resolve_literal(r.head, s)
                        if any(isinstance(a, Var) for a in h.args):
                            continue
                        key = (h.pred, h.args)
                        if self.facts.has(h.pred, h.args) or any(k == key for k, _ in new):
                            continue
                        new.append((key, Derivation(r.id, r.description, prem, checks)))
                if not new: break
                for (pred, args), d in new:
                    self.facts.add(pred, args)
                    self.derivations[(pred, args)] = d
                    step += 1
                    self.trace.append(TraceStep(step, st, d.rule_id, str(Literal(pred, args))))
        return {"derived": len(self.derivations), "iterations": self.iterations,
                "total_facts": self.facts.count()}

    # -- queries -------------------------------------------------------------
    def query(self, pred: str, *pattern):
        """Return all fact tuples of `pred` whose leading arguments match `pattern`
        (None/Var = wildcard; a shorter pattern matches as a prefix)."""
        out = []
        for args in self.facts.by_pred.get(pred, ()):
            if len(pattern) > len(args): continue
            if all(p is None or isinstance(p, Var) or p == a for p, a in zip(pattern, args)):
                out.append(args)
        return sorted(out, key=lambda t: tuple(str(x) for x in t))

    def proof(self, pred: str, args: tuple, _seen=None) -> ProofNode:
        text = str(Literal(pred, args))
        d = self.derivations.get((pred, args))
        if d is None:
            return ProofNode(text, "fact", pred=pred, args=args)
        node = ProofNode(text, "rule", d.rule_id, d.description, pred, args)
        for p, a in d.premises:
            node.children.append(self.proof(p, a))
        for kind, item in d.checks:
            if kind == "neg":
                node.children.append(ProofNode(f"no fact matches {item}", "naf"))
            else:
                node.children.append(ProofNode(item, "builtin"))
        return node
