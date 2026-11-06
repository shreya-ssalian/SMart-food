"""Shared plumbing for the domain checkers: turns derived facts into Findings."""
from __future__ import annotations
from inference.terms import Literal, Var
from models import Finding


def severity_of(ctx, kind: str) -> str:
    rows = ctx.forward.query("severity", kind, None)
    return rows[0][1] if rows else "low"


def collect(ctx, kinds, module: str, pred: str = "concern") -> list[Finding]:
    """Read pred(pid, Kind, Subject, Detail, Source) from the forward-chained closure and
    group by (kind, subject).  Each row is then re-proved by BACKWARD chaining."""
    rows = [r for r in ctx.forward.query(pred, ctx.pid) if r[1] in kinds]
    grouped: dict[tuple, Finding] = {}
    for row in rows:
        _, kind, subj, detail, src = row
        f = grouped.setdefault((kind, subj), Finding(kind, subj, severity=severity_of(ctx, kind),
                                                      confirmed=(pred == "concern"), module=module))
        if detail not in f.details: f.details.append(detail)
        if src not in f.sources: f.sources.append(src)
        f.forward_proofs.append(ctx.forward.proof(pred, row))
        sols = ctx.backward.prove(Literal(pred, tuple(row)), 1)
        if sols:
            f.proofs.append(sols[0].proof)
    for f in grouped.values():
        f.verified_backward = len(f.proofs) >= len(f.forward_proofs) > 0
    return sorted(grouped.values(), key=lambda f: (f.kind, str(f.subject)))
