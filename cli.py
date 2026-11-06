"""Command-line interface:  python cli.py --list | --product T01 | --all | --export-facts"""
import argparse
import csv
import sys

import config
from analyzer import SmartFoodAnalyzer
from knowledge.kb_loader import load_kb, read_csv
from reports.complaint_generator import generate_text


def test_rows(kb):
    d = config.TEST_DIR if read_csv(config.TEST_DIR / "test_products.csv") else config.DEMO_TEST_DIR
    return read_csv(d / "test_products.csv")


def show(res, an, verbose=False):
    print(f"\n=== {res.product.get('product_id')}  -> {res.verdict}  (confidence: {res.confidence})")
    print("    " + res.verdict_text)
    for f in res.findings:
        tag = "REPORTABLE" if f.status == "reportable" else f.status.upper()
        print(f"  [{f.severity:8}] [{tag:10}] {f.headline}\n      {f.explanation}")
        if verbose:
            print("      proof:\n" + "\n".join("        " + l for l in an.explainer.finding_proof(f).splitlines()))
    for g in res.gaps:
        if g.kind != "parse_note":
            print(f"  (gap) {g.message}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", choices=["auto", "real", "demo"], default="auto")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--product"); ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--complaint", action="store_true")
    ap.add_argument("--export-facts", action="store_true")
    ap.add_argument("--ingredients"); ap.add_argument("--nutrition", default="")
    ap.add_argument("--category", default=""); ap.add_argument("--claims", default="")
    ap.add_argument("--allergies", default="")
    a = ap.parse_args()
    kb = load_kb(a.kb); an = SmartFoodAnalyzer(kb)
    print(f"Knowledge base: {kb.dir}  {'[DEMO DATA]' if kb.is_demo else ''}")
    if a.export_facts:
        print("wrote", kb.export_prolog()); return
    rows = test_rows(kb)
    if a.list:
        for r in rows: print(r["test_id"], "-", r["product_id"]); return
    targets = []
    if a.ingredients:
        targets = [{"product_id": "custom", "ingredients_text": a.ingredients, "nutrition_text": a.nutrition,
                    "category_id": a.category, "claims": a.claims, "allergy_profile": a.allergies}]
    elif a.all: targets = rows
    elif a.product: targets = [r for r in rows if r["test_id"] == a.product]
    else: ap.print_help(); return
    for t in targets:
        res = an.analyze(t); show(res, an, a.verbose)
        if a.complaint and res.reportable: print("\n" + generate_text(res, an))


if __name__ == "__main__":
    main()
