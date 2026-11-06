"""Regulation verification: label-completeness rules and linking concerns to regulations.

A confirmed concern is *reportable* when it is of a regulatory kind and its source is a
clause of a regulation in regulations.csv.  Each such link is proved by backward chaining
(goal: reportable(P, Reg, Kind, Subject))."""
from __future__ import annotations
from inference.terms import Literal, Var
from models import Finding
from modules._base import collect

KINDS = {"missing_label_info"}


def check(ctx) -> list[Finding]:
    return (collect(ctx, KINDS, "regulation", "concern") +
            collect(ctx, KINDS, "regulation", "possible_concern"))


def link_regulations(ctx, findings: list[Finding]) -> None:
    rows = ctx.forward.query("reportable", ctx.pid)
    for f in findings:
        if not f.confirmed: continue
        for _, reg, kind, sub in rows:
            if kind == f.kind and sub == f.subject:
                f.reportable = True
                if reg not in f.regulations:
                    f.regulations.append(reg)
                    sols = ctx.backward.prove(Literal("reportable", (ctx.pid, reg, kind, sub)), 1)
                    if sols: f.regulation_proofs.append(sols[0].proof)


def regulation_details(ctx, reg_id: str) -> dict:
    r = ctx.kb.regulations.get(reg_id, {})
    src = ctx.kb.sources.get(r.get("source_id", ""), {})
    return {"id": reg_id, "title": r.get("title", reg_id), "clause": r.get("clause", ""),
            "jurisdiction": r.get("jurisdiction", ""), "effective_date": r.get("effective_date", ""),
            "authority": src.get("authority", ""), "document": src.get("document_title", ""),
            "url": src.get("url", ""), "source_id": r.get("source_id", "")}
