"""Loads the CSV knowledge base into first-order facts and validates it.

Every CSV row becomes one or more ground facts (see ontology.pl).  If the real
knowledge base in data/knowledge_base/ is still empty, the clearly-labelled
illustrative demo data in data/demo/ is used instead, so the prototype always runs."""
from __future__ import annotations
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config
from inference.terms import (FactBase, Literal, parse_program, prolog_atom,
                             split_program)
from parser.normalizer import normalize_phrase, slug

TABLES = ["sources", "regulations", "food_categories", "allergens", "additives",
          "additive_limits", "allergen_derivatives", "synonyms",
          "ingredient_relations", "nutrition_rules", "label_rules"]

_OPS = {">": "gt", "gt": "gt", ">=": "gte", "gte": "gte", "ge": "gte",
        "<": "lt", "lt": "lt", "<=": "lte", "lte": "lte", "le": "lte"}
_YES = {"yes", "y", "true", "1", "permitted", "allowed"}
_NO = {"no", "n", "false", "0", "prohibited", "banned", "not permitted"}
_TO_MGKG = {"mg/kg": 1.0, "ppm": 1.0, "mg/l": 1.0, "g/kg": 1000.0, "%": 10000.0}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = []
        for r in csv.DictReader(f):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            if any(r.values()):
                rows.append(r)
        return rows


def kb_row_count(directory: Path) -> int:
    return sum(len(read_csv(directory / f"{t}.csv")) for t in config.CORE_TABLES)


def num(x) -> Optional[float]:
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


@dataclass
class Issue:
    level: str       # error | warning | info
    message: str


class KnowledgeBase:
    def __init__(self, directory: Path, is_demo: bool = False):
        self.dir, self.is_demo = Path(directory), is_demo
        self.tables = {t: read_csv(self.dir / f"{t}.csv") for t in TABLES}
        self.issues: list[Issue] = []
        self.facts = FactBase()
        self.alias_map: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.ins_to_additive: dict[str, str] = {}
        self.allergens: dict[str, str] = {}
        self.additive_info: dict[str, dict] = {}
        self.categories: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
        self.regulations: dict[str, dict] = {}
        self.interaction_notes: dict[tuple, str] = {}
        self.known_ingredients: set[str] = set()
        self.nutrition_rules: dict[str, dict] = {}
        self.label_rules: dict[str, dict] = {}
        self.limits: list[dict] = []
        self._build()

    # ------------------------------------------------------------------ build
    def _add(self, pred, *args):
        self.facts.add(pred, tuple(args))

    def _warn(self, msg, level="warning"):
        self.issues.append(Issue(level, msg))

    def display(self, ident: str) -> str:
        if ident in self.names: return self.names[ident]
        ident = str(ident)
        if ident.startswith("ins_"): return "INS " + ident[4:]
        return ident.replace("_", " ")

    def _build(self):
        T = self.tables
        for r in T["sources"]:
            sid = r.get("source_id", "")
            if sid:
                self.sources[sid] = r
        for r in T["regulations"]:
            rid = slug(r.get("regulation_id", ""))
            if rid:
                self.regulations[rid] = r
                self._add("regulation_source", rid, r.get("source_id", ""))
        for r in T["food_categories"]:
            cid = slug(r.get("category_id", ""))
            if not cid: continue
            parent = slug(r.get("parent_category_id", "")) or "all"
            self.categories[cid] = {"name": r.get("name") or cid, "parent": parent}
            self.names[cid] = r.get("name") or cid
            self._add("cat_parent", cid, parent)
        for r in T["allergens"]:
            aid = slug(r.get("allergen_id", ""))
            if not aid: continue
            self.allergens[aid] = r.get("name") or aid
            self.names[aid] = r.get("name") or aid
            self._add("allergen", aid)
            self.known_ingredients.add(aid)
            self.alias_map[normalize_phrase(aid)] = aid
            self.alias_map[normalize_phrase(self.allergens[aid])] = aid
        for r in T["additives"]:
            aid = slug(r.get("additive_id", ""))
            if not aid: continue
            self.additive_info[aid] = r
            self.names[aid] = r.get("canonical_name") or aid
            self._add("additive", aid)
            self.known_ingredients.add(aid)
            code = (r.get("ins_code") or "").lower().replace(" ", "")
            if code:
                self.ins_to_additive[code] = aid
            self.alias_map[normalize_phrase(r.get("canonical_name", ""))] = aid
            fn = slug(r.get("function", ""))
            if fn:
                self._add("is_a", aid, fn)
                self.known_ingredients.add(fn)
        for r in T["synonyms"]:
            a, c = normalize_phrase(r.get("alias", "")), slug(r.get("canonical_id", ""))
            if a and c:
                self.alias_map[a] = c
                self.known_ingredients.add(c)
        for r in T["additive_limits"]:
            aid = slug(r.get("additive_id", ""))
            cat = slug(r.get("category_id", "")) or "all"
            p = r.get("permitted", "").lower()
            perm = "yes" if p in _YES else "no" if p in _NO else None
            if not aid or perm is None:
                self._warn(f"additive_limits: row for '{aid}' has unreadable 'permitted' value '{p}' (skipped)")
                continue
            mx, unit = num(r.get("max_value")), r.get("unit", "").lower()
            mxv = "none"
            if mx is not None:
                if unit in _TO_MGKG: mxv = mx * _TO_MGKG[unit]
                else: self._warn(f"additive_limits: unit '{unit}' for {aid} is not convertible to mg/kg; maximum ignored")
            src = r.get("source_id", "")
            if r.get("condition"):
                self._warn(f"additive_limits: condition '{r['condition']}' for {aid}/{cat} is not evaluated by the engine")
            self.limits.append({"additive": aid, "category": cat, "permitted": perm,
                                "max": mxv, "source": src})
            self._add("additive_limit", aid, cat, perm, mxv, src)
        for r in T["allergen_derivatives"]:
            i, a = slug(r.get("ingredient_id", "")), slug(r.get("allergen_id", ""))
            rel = r.get("relation", "contains").lower()
            rel = "may_contain" if rel in ("may_contain", "may contain", "possible") else "contains"
            if i and a:
                self._add("allergen_source", i, a, rel, r.get("source_id", ""))
                self.known_ingredients.add(i)
        for r in T["ingredient_relations"]:
            i, rel_to = slug(r.get("ingredient_id", "")), slug(r.get("related_id", ""))
            typ, src = r.get("relation_type", "").lower(), r.get("source_id", "")
            if not (i and rel_to): continue
            self.known_ingredients.update({i, rel_to} if typ == "is_a" else {i})
            if typ == "is_a":
                self._add("is_a", i, rel_to)
            elif typ == "interacts_with":
                a, b = sorted([i, rel_to])
                self._add("interacts_with", a, b, src)
                self.interaction_notes[(a, b)] = r.get("note", "")
                self.known_ingredients.update({i, rel_to})
            elif typ == "contradicts_claim":
                self._add("contradicts_claim", i, rel_to, src)
            else:
                self._warn(f"ingredient_relations: unsupported relation_type '{typ}' (row {r.get('relation_id')}) ignored")
        for r in T["nutrition_rules"]:
            rid, n = slug(r.get("rule_id", "")), slug(r.get("nutrient", ""))
            op, t = _OPS.get(r.get("operator", "").lower()), num(r.get("threshold"))
            basis = r.get("basis", "").lower().replace(" ", "_")
            if not rid or op is None or t is None or not n:
                self._warn(f"nutrition_rules: row '{rid}' is incomplete (skipped)"); continue
            if basis not in ("per_100g", "per_100ml", "100g", "100ml", ""):
                self._warn(f"nutrition_rules: basis '{basis}' of {rid} not supported (only per 100 g/ml); skipped"); continue
            unit = r.get("unit", "").lower() or config.CANONICAL_UNITS.get(n, config.DEFAULT_UNIT)
            canon = config.CANONICAL_UNITS.get(n, config.DEFAULT_UNIT)
            if unit != canon:
                if unit in config.UNIT_TO_G and canon in config.UNIT_TO_G:
                    t = t * config.UNIT_TO_G[unit] / config.UNIT_TO_G[canon]
                else:
                    self._warn(f"nutrition_rules: unit '{unit}' of {rid} cannot be converted to {canon}; skipped"); continue
            cond = r.get("condition", "").strip().lower().replace(" ", "")
            if cond == "": scope = ("category", "all")
            elif cond.startswith("category="): scope = ("category", slug(cond.split("=", 1)[1]))
            elif cond.startswith("claim="): scope = ("claim", slug(cond.split("=", 1)[1]))
            else:
                self._warn(f"nutrition_rules: condition '{cond}' of {rid} unsupported (use category=… or claim=…); skipped"); continue
            self.nutrition_rules[rid] = {"nutrient": n, "op": op, "threshold": t, "unit": canon,
                                         "scope": scope, "source": r.get("source_id", "")}
            self._add("nutrition_rule", rid, n, op, t, r.get("source_id", ""))
            self._add("nutrition_scope", rid, scope[0], scope[1])
        for r in T["label_rules"]:
            rid, req = slug(r.get("rule_id", "")), slug(r.get("requirement", ""))
            if not rid: continue
            if req not in config.SUPPORTED_LABEL_REQUIREMENTS:
                self._warn(f"label_rules: requirement '{req}' of {rid} is not supported by the engine "
                           f"(supported: {', '.join(sorted(config.SUPPORTED_LABEL_REQUIREMENTS))})"); continue
            self.label_rules[rid] = {"requirement": req, "source": r.get("source_id", "")}
            self._add("label_rule", rid, req, r.get("source_id", ""))
            self._add("label_scope", rid, slug(r.get("category_id", "")) or "all")
        for i in self.known_ingredients:
            self._add("known_ingredient", i)
            self.alias_map.setdefault(normalize_phrase(i), i)
        for k, v in self.names.items():
            self.alias_map.setdefault(normalize_phrase(v), k)

    # ------------------------------------------------------------- validation
    def validate(self) -> list[Issue]:
        out = list(self.issues)
        if self.is_demo:
            out.insert(0, Issue("warning", "Using ILLUSTRATIVE DEMO DATA - not verified regulatory content. "
                                "Fill data/knowledge_base/*.csv with official, versioned data to replace it."))
        for t in config.CORE_TABLES:
            if not self.tables.get(t):
                out.append(Issue("info", f"Table '{t}' has no rows."))
        for t, key in [("additive_limits", "source_id"), ("allergen_derivatives", "source_id"),
                       ("nutrition_rules", "source_id"), ("label_rules", "source_id"),
                       ("ingredient_relations", "source_id"), ("regulations", "source_id")]:
            for r in self.tables[t]:
                s = r.get(key, "")
                if not s:
                    out.append(Issue("warning", f"{t}: a row has no source_id (no provenance)"))
                elif s not in self.sources:
                    out.append(Issue("warning", f"{t}: source_id '{s}' not found in sources.csv"))
        for cid, c in self.categories.items():
            if c["parent"] != "all" and c["parent"] not in self.categories:
                out.append(Issue("warning", f"food_categories: parent '{c['parent']}' of '{cid}' is undefined"))
        seen = {}
        for l in self.limits:
            k = (l["additive"], l["category"])
            if k in seen and seen[k] != l["permitted"]:
                out.append(Issue("error", f"additive_limits: conflicting permission for {k[0]} in {k[1]}"))
            seen[k] = l["permitted"]
            if l["category"] not in self.categories and l["category"] != "all":
                out.append(Issue("warning", f"additive_limits: unknown category '{l['category']}'"))
            if l["additive"] not in self.additive_info:
                out.append(Issue("warning", f"additive_limits: additive '{l['additive']}' not in additives.csv"))
        edges: dict = {}
        for a, b in self.facts.by_pred.get("is_a", ()):
            edges.setdefault(a, set()).add(b)
        for start in edges:
            stack, seen_n = [start], set()
            while stack:
                n = stack.pop()
                for m in edges.get(n, ()):
                    if m == start:
                        out.append(Issue("error", f"is_a cycle detected through '{start}'")); stack = []; break
                    if m not in seen_n: seen_n.add(m); stack.append(m)
        for r in self.regulations.values():
            if r.get("source_id") and r["source_id"] not in self.sources:
                out.append(Issue("warning", f"regulation {r['regulation_id']} references unknown source"))
        return out

    def summary(self) -> dict:
        return {"directory": str(self.dir), "demo": self.is_demo,
                "rows": {t: len(v) for t, v in self.tables.items()},
                "facts": self.facts.count()}

    def export_prolog(self, path: Path = None):
        path = Path(path or config.FACTS_FILE)
        lines = ["% AUTO-GENERATED knowledge-base facts (do not edit by hand).",
                 f"% Source directory: {self.dir}" + ("   [ILLUSTRATIVE DEMO DATA]" if self.is_demo else ""), ""]
        for pred in sorted(self.facts.by_pred):
            lines.append(f"% --- {pred}")
            for args in sorted(self.facts.by_pred[pred], key=lambda a: tuple(map(str, a))):
                lines.append(f"{pred}({', '.join(prolog_atom(a) for a in args)}).")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


def load_rules(path: Path = None):
    """Parse rules.pl -> (rules, static_facts)."""
    text = Path(path or config.RULES_FILE).read_text(encoding="utf-8")
    return split_program(parse_program(text))


def load_kb(prefer: str = "auto") -> KnowledgeBase:
    """prefer: 'auto' (real KB if populated else demo), 'real', or 'demo'."""
    if prefer == "demo":
        return KnowledgeBase(config.DEMO_KB_DIR, True)
    if prefer == "real" or kb_row_count(config.KB_DIR) > 0:
        return KnowledgeBase(config.KB_DIR, False)
    return KnowledgeBase(config.DEMO_KB_DIR, True)
