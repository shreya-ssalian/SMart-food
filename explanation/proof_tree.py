"""Proof trees: the explainable trace behind every conclusion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ProofNode:
    statement: str                 # ground literal text
    kind: str                      # fact | rule | naf | builtin
    rule_id: Optional[str] = None
    description: str = ""
    pred: Optional[str] = None
    args: tuple = ()
    children: list = field(default_factory=list)

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)

    def size(self) -> int:
        return 1 + sum(c.size() for c in self.children)

    def to_dict(self) -> dict:
        return {"statement": self.statement, "kind": self.kind, "rule": self.rule_id,
                "description": self.description,
                "children": [c.to_dict() for c in self.children]}


_ICON = {"fact": "FACT", "rule": "RULE", "naf": "NOT ", "builtin": "TEST"}


def render_text(node: ProofNode, describe: Optional[Callable] = None, max_depth: int = 12) -> str:
    """ASCII tree.  `describe(pred,args)` may supply a plain-English phrase."""
    lines: list[str] = []

    def rec(n: ProofNode, prefix: str, last: bool, depth: int):
        branch = "" if depth == 0 else ("└─ " if last else "├─ ")
        label = n.statement
        if describe and n.pred and n.kind in ("fact", "rule"):
            try:
                nl = describe(n.pred, n.args)
                if nl: label = f"{nl}   [{n.statement}]"
            except Exception:
                pass
        tag = f"[{_ICON.get(n.kind, n.kind)}"
        if n.kind == "rule" and n.rule_id: tag += f" {n.rule_id}"
        tag += "]"
        lines.append(f"{prefix}{branch}{tag} {label}")
        if depth >= max_depth:
            if n.children: lines.append(f"{prefix}   … ({len(n.children)} deeper steps)")
            return
        ext = "" if depth == 0 else ("   " if last else "│  ")
        for i, c in enumerate(n.children):
            rec(c, prefix + ext, i == len(n.children) - 1, depth + 1)

    rec(node, "", True, 0)
    return "\n".join(lines)


def leaves(node: ProofNode):
    if not node.children:
        yield node
    for c in node.children:
        yield from leaves(c)
