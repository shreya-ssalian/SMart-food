"""Terms, unification and a small Prolog-style clause parser (Horn clauses with
negation-as-failure and numeric comparison).  Shared by forward and backward chaining."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from itertools import count
from typing import Any, Iterable, Optional


class Var:
    __slots__ = ("name",)
    def __init__(self, name: str): self.name = name
    def __repr__(self): return self.name
    def __eq__(self, o): return isinstance(o, Var) and o.name == self.name
    def __hash__(self): return hash(("Var", self.name))


@dataclass(frozen=True)
class Literal:
    pred: str
    args: tuple = ()
    def __str__(self):
        return f"{self.pred}({', '.join(fmt_term(a) for a in self.args)})" if self.args else self.pred


@dataclass
class Goal:                      # one item of a rule body
    kind: str                    # 'pos' | 'neg' | 'cmp'
    lit: Optional[Literal] = None
    op: str = ""
    left: Any = None
    right: Any = None


@dataclass
class Rule:
    id: str
    description: str
    head: Literal
    body: list
    text: str = ""


def fmt_term(t) -> str:
    if isinstance(t, float):
        return str(int(t)) if t == int(t) else f"{t:g}"
    return str(t)


def walk(t, s):
    while isinstance(t, Var) and t in s:
        t = s[t]
    return t


def unify(a, b, s):
    a, b = walk(a, s), walk(b, s)
    if isinstance(a, Var) and isinstance(b, Var) and a == b:
        return s
    if isinstance(a, Var):
        s2 = dict(s); s2[a] = b; return s2
    if isinstance(b, Var):
        s2 = dict(s); s2[b] = a; return s2
    return s if a == b else None


def unify_args(xs, ys, s):
    if len(xs) != len(ys):
        return None
    for x, y in zip(xs, ys):
        s = unify(x, y, s)
        if s is None:
            return None
    return s


def resolve_literal(lit: Literal, s) -> Literal:
    return Literal(lit.pred, tuple(walk(a, s) for a in lit.args))


def is_ground(lit: Literal) -> bool:
    return not any(isinstance(a, Var) for a in lit.args)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def eval_cmp(op, l, r, s) -> bool:
    l, r = walk(l, s), walk(r, s)
    if isinstance(l, Var) or isinstance(r, Var):
        return False
    if op == "==":  return l == r
    if op == "\\=": return l != r
    if not (_num(l) and _num(r)):
        return False
    return {">": l > r, "<": l < r, ">=": l >= r, "=<": l <= r,
            "=:=": l == r, "=\\=": l != r}[op]


def rename_rule(rule: Rule, n: int) -> Rule:
    m: dict = {}
    def rn(t):
        if isinstance(t, Var):
            return m.setdefault(t.name, Var(f"{t.name}#{n}"))
        return t
    def rl(l): return Literal(l.pred, tuple(rn(a) for a in l.args))
    body = []
    for g in rule.body:
        if g.kind == "cmp":
            body.append(Goal("cmp", None, g.op, rn(g.left), rn(g.right)))
        else:
            body.append(Goal(g.kind, rl(g.lit)))
    return Rule(rule.id, rule.description, rl(rule.head), body, rule.text)


# ---------------------------------------------------------------- parser ----
_TOKEN = re.compile(
    r"""\s*(?:(?P<meta>@META\d+@)|(?P<naf>\\\+)|(?P<neck>:-)"""
    r"""|(?P<cmp>=:=|=\\=|>=|=<|\\=|==|>|<)|(?P<num>-?\d+(?:\.\d+)?)"""
    r"""|(?P<q>'(?:[^'\\]|\\.)*')|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<p>[(),.]))""")
_META = re.compile(r"^\s*%%\s*(?:\[([^\]]+)\])?\s*(.*)$")


def _tokenise(text: str):
    metas, lines = [], []
    for line in text.splitlines():
        m = _META.match(line)
        if m:
            metas.append((m.group(1), m.group(2).strip()))
            lines.append(f" @META{len(metas)-1}@ ")
        else:
            lines.append(line.split("%", 1)[0])
    src, pos, toks = "\n".join(lines), 0, []
    while pos < len(src):
        if not src[pos:].strip():
            break
        m = _TOKEN.match(src, pos)
        if not m:
            raise ValueError(f"Syntax error near: {src[pos:pos+30]!r}")
        pos = m.end()
        kind = m.lastgroup
        toks.append((kind, m.group(kind)))
    return toks, metas


class _Parser:
    def __init__(self, toks, metas):
        self.t, self.i, self.metas, self.anon = toks, 0, metas, count()
    def peek(self): return self.t[self.i] if self.i < len(self.t) else (None, None)
    def next(self): tok = self.peek(); self.i += 1; return tok
    def expect(self, val):
        k, v = self.next()
        if v != val: raise ValueError(f"Expected {val!r} but found {v!r}")

    def term(self):
        k, v = self.next()
        if k == "num": return float(v) if "." in v else int(v)
        if k == "q": return v[1:-1].replace("\\'", "'")
        if k == "id":
            if v == "_": return Var(f"_G{next(self.anon)}")
            return Var(v) if (v[0].isupper() or v[0] == "_") else v
        raise ValueError(f"Unexpected token {v!r}")

    def literal(self):
        k, name = self.next()
        if k != "id" or name[0].isupper():
            raise ValueError(f"Expected predicate name, found {name!r}")
        args = []
        if self.peek()[1] == "(":
            self.next()
            while True:
                args.append(self.term())
                _, v = self.next()
                if v == ")": break
                if v != ",": raise ValueError("Expected , or )")
        return Literal(name, tuple(args))

    def goal(self):
        k, v = self.peek()
        if k == "naf":
            self.next(); return Goal("neg", self.literal())
        # try comparison:  Term op Term
        save = self.i
        if k in ("num", "q") or (k == "id" and (v[0].isupper() or v[0] == "_")):
            left = self.term()
            ck, cv = self.next()
            if ck != "cmp": raise ValueError(f"Expected comparison operator, found {cv!r}")
            return Goal("cmp", None, cv, left, self.term())
        self.i = save
        return Goal("pos", self.literal())

    def clauses(self):
        out, n, pending = [], 0, None
        while self.i < len(self.t):
            if self.peek()[0] == "meta":
                pending = self.metas[int(self.next()[1][5:-1])]
                continue
            start = self.i
            head = self.literal()
            body = []
            if self.peek()[0] == "neck":
                self.next()
                while True:
                    body.append(self.goal())
                    _, v = self.next()
                    if v == ".": break
                    if v != ",": raise ValueError("Expected , or . in rule body")
            else:
                self.expect(".")
            n += 1
            rid, desc = (pending if pending else (None, ""))
            if not rid and body and out and out[-1].body and out[-1].head.pred == head.pred:
                rid, desc = out[-1].id, out[-1].description      # continuation clause of the same rule
            out.append(Rule(rid or f"clause{n}", desc, head, body))
            pending = None
        return out


def parse_program(text: str) -> list:
    toks, metas = _tokenise(text)
    return _Parser(toks, metas).clauses()


def parse_goal(text: str) -> Literal:
    text = text.strip().rstrip(".")
    toks, metas = _tokenise(text + ".")
    p = _Parser(toks, metas)
    return p.literal()


def split_program(clauses: Iterable[Rule]):
    rules, facts = [], []
    for c in clauses:
        if c.body or not is_ground(c.head):
            rules.append(c)
        else:
            facts.append(c.head)
    return rules, facts


def prolog_atom(x) -> str:
    if isinstance(x, (int, float)): return fmt_term(x)
    s = str(x)
    return s if re.fullmatch(r"[a-z][A-Za-z0-9_]*", s) else "'" + s.replace("'", "\\'") + "'"


# ------------------------------------------------------------- fact store ----
class FactBase:
    def __init__(self):
        self.by_pred: dict[str, set] = {}
        self._index: dict[str, dict] = {}

    def add(self, pred: str, args: tuple) -> bool:
        s = self.by_pred.setdefault(pred, set())
        if args in s: return False
        s.add(args)
        idx = self._index.get(pred)
        if idx is not None and args:
            idx.setdefault(args[0], []).append(args)
        return True

    def has(self, pred, args) -> bool:
        return args in self.by_pred.get(pred, ())

    def candidates(self, pred: str, first=None, bound=False):
        if pred not in self.by_pred: return ()
        if bound:
            idx = self._index.get(pred)
            if idx is None:
                idx = {}
                for a in self.by_pred[pred]:
                    if a: idx.setdefault(a[0], []).append(a)
                self._index[pred] = idx
            return idx.get(first, ())
        return self.by_pred[pred]

    def copy(self) -> "FactBase":
        fb = FactBase()
        fb.by_pred = {p: set(s) for p, s in self.by_pred.items()}
        return fb

    def count(self) -> int:
        return sum(len(s) for s in self.by_pred.values())
