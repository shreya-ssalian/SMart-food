"""Generates a structured, explainable food-safety complaint draft (text and optional PDF)."""
from __future__ import annotations
import datetime
from string import Template
from typing import Optional

import config
from modules.regulation_checker import regulation_details


def _concern_block(i, f, ctx, an) -> str:
    lines = [f"   [{i}] {f.headline}", f"       Finding   : {f.explanation}"]
    for r in f.regulations:
        d = regulation_details(ctx, r)
        lines.append(f"       Regulation: {d['title']} - clause {d['clause'] or 'n/a'}"
                     f" ({d['jurisdiction'] or 'jurisdiction n/a'}); authority: {d['authority'] or 'n/a'}")
    lines.append(f"       Logic     : rule chain verified by backward chaining = "
                 f"{'yes' if f.verified_backward else 'no'}")
    return "\n".join(lines)


def generate_text(result, analyzer, complainant: Optional[dict] = None) -> str:
    c = complainant or {}
    ctx, kb = result.ctx, result.ctx.kb
    findings = result.reportable
    if not findings:
        return "No reportable regulatory concerns were found, so no complaint draft was generated."
    auth = sorted({regulation_details(ctx, r)["authority"] for f in findings for r in f.regulations if regulation_details(ctx, r)["authority"]})
    lim = ["   - Draft generated automatically; verify every finding against the physical label before submitting.",
           "   - Conclusions are only as complete and accurate as the knowledge base."]
    if kb.is_demo:
        lim.append("   - !! THE KNOWLEDGE BASE WAS ILLUSTRATIVE DEMO DATA. THIS DRAFT HAS NO REGULATORY VALUE. !!")
    for g in result.gaps:
        if g.kind not in ("parse_note", "demo_kb"):
            lim.append(f"   - Unverified: {g.message}")
    annex = []
    for i, f in enumerate(findings, 1):
        annex.append(f"[{i}] {f.headline}\n{analyzer.explainer.finding_proof(f)}")
        for p in f.regulation_proofs[:1]:
            annex.append("   Regulation link:\n" + analyzer.explainer.proof_text(p))
    p = result.product
    vals = dict(
        date=datetime.date.today().isoformat(),
        authority=", ".join(auth) or "[food safety authority - fill in]",
        reference=c.get("reference", f"SFAI-{result.pid}-{datetime.date.today():%Y%m%d}"),
        complainant_name=c.get("name", "[your name]"), complainant_contact=c.get("contact", "[phone / email]"),
        product_name=p.get("product_id") or p.get("name", ""), category=kb.display(result.category) if result.category else "unknown",
        brand=c.get("brand", "[brand / manufacturer]"), batch=c.get("batch", "[batch / lot]"),
        best_before=c.get("best_before", "[date]"), purchase_info=c.get("purchase_info", "[shop, date]"),
        ingredients=p.get("ingredients_text", ""), nutrition=p.get("nutrition_text", "") or "not provided",
        claims=p.get("claims", "") or "none",
        concerns="\n\n".join(_concern_block(i, f, ctx, analyzer) for i, f in enumerate(findings, 1)),
        kb_description=("DEMO DATA" if kb.is_demo else str(kb.dir.name)), limitations="\n".join(lim),
        annex="\n\n".join(annex))
    tpl = Template((config.TEMPLATE_DIR / "complaint_template.txt").read_text(encoding="utf-8"))
    return tpl.safe_substitute(vals)


def generate_pdf(text: str, path) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return False
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y, c_font = h - 40, ("Courier", 8)
    c.setFont(*c_font)
    for line in text.splitlines():
        for chunk in [line[i:i + 105] for i in range(0, max(len(line), 1), 105)]:
            if y < 40:
                c.showPage(); c.setFont(*c_font); y = h - 40
            c.drawString(36, y, chunk.encode("latin-1", "replace").decode("latin-1")); y -= 10
    c.save()
    return True
