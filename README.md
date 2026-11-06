# SmartFood AI — Intelligent Food Safety Assessment (Classical AI, no ML/DL)

Reads a packaged-food label (ingredients, nutrition, claims), reasons over a **knowledge base**
with **first-order-logic Horn rules**, **forward chaining** and **backward chaining**, and returns
explainable findings, a verdict, and — if regulatory concerns exist — a structured complaint draft.

```
pip install -r requirements.txt
streamlit run app.py              # web UI
python cli.py --list              # sample products
python cli.py --all -v            # analyse all samples with proof trees
python cli.py --ingredients "Water, Sugar, Preservative (INS 211)" --category soft_drinks --claims "no added sugar"
python -m pytest -q               # 45 tests
```
No external Prolog install is needed: the engine is pure Python. `knowledge/rules.pl` is plain
Prolog-style text that the engine parses itself.

## ⚠ About the data
* `data/knowledge_base/*.csv` are **your** files (headers only). Nothing is invented there.
* While they are empty, the app loads `data/demo/` — a small **illustrative, unverified** dataset
  (every row's source is `SRC-DEMO-*`) so the prototype runs. The UI, CLI and complaint draft all say so.
* As soon as any core table in `data/knowledge_base/` has rows, your data is used instead
  (sidebar: *auto / demo / real*). Don't mix: partially filled = partially reasoned (unknown ≠ safe; gaps are reported).

## Architecture
| Stage | File(s) | What it does |
|---|---|---|
| Parse | `parser/` | splits nested ingredient lists, %, INS/E numbers, functional classes ("Preservative (211)"), `Contains:`/`May contain`, mg/kg amounts; nutrition per 100 g or per serving, kJ→kcal, salt↔sodium |
| Knowledge representation | `knowledge/kb_loader.py`, `ontology.pl` | CSV rows → ground facts; taxonomy via `is_a`, category tree, provenance (`source_id`) on every rule |
| Rules (FOL → Horn) | `knowledge/rules.pl` | 47 documented rules, each with an id (`R-ALG-3` …) |
| Forward chaining | `inference/forward_chaining.py` | data-driven to fixpoint, **stratified negation-as-failure**, stores derivations |
| Backward chaining | `inference/backward_chaining.py` | goal-driven SLD resolution; re-proves every finding independently; powers *Ask the system* |
| Incomplete info | `inference/uncertainty_handler.py` | `gap/3` facts, `possible` vs `confirmed`, confidence level — unknown is never treated as safe |
| Conflicts | `inference/conflict_resolver.py` + rules R-ADD-3/4 | most specific category rule wins (e.g. tartrazine OK in drinks, banned in infant food) |
| Checkers | `modules/` | allergen, additive, interaction/claims, nutrition, regulation linking |
| Explanation | `explanation/` | proof trees → plain English |
| Reports | `reports/` | complaint draft (txt/pdf) only for *reportable* findings |

### Reasoning examples (all in the demo set)
* *Multi-hop*: `skimmed milk powder → milk powder → milk product → contains milk` ⇒ allergy alert / undeclared allergen.
* *Claim vs ingredients*: claim "no added sugar" + `sugar is_a added_sugar` ⇒ contradiction.
* *Reportable* = concern of a regulatory kind **and** its `source_id` matches a row in `regulations.csv`.
  Advisory items (e.g. high sodium) are never turned into complaints.

## Filling in your dataset
Use stable lowercase ids (`milk`, `ins_211`, `soft_drinks`). Every row needs a `source_id` that exists in `sources.csv`.

| File | Notes |
|---|---|
| `sources.csv` | authority, document, clause, url, version/accessed date — fill first |
| `regulations.csv` | one row per regulation clause; `source_id` links findings to it (needed for "reportable") |
| `food_categories.csv` | blank parent = top level |
| `allergens.csv`, `allergen_derivatives.csv` | `relation`: `contains` / `derived_from` / `may_contain`; ingredient may be a *class* (`milk_product`) |
| `additives.csv` | `function` becomes an `is_a` class (`preservative`, `colour`…) used by claims such as "no preservatives" |
| `additive_limits.csv` | `permitted` yes/no; blank category = all; `max_value` + unit (`mg/kg`, `ppm`, `g/kg`, `%`) |
| `synonyms.csv` | alias → canonical id (also claims: "sugar free" → `sugar_free`, allergens: "wheat" → `gluten`) |
| `ingredient_relations.csv` | `relation_type`: `is_a`, `interacts_with`, `contradicts_claim`. Optional extra column `note` explains an interaction |
| `nutrition_rules.csv` | operator `>,>=,<,<=`; basis `per_100g`; condition blank / `category=x` / `claim=x` (claim rules verify claims) |
| `label_rules.csv` | requirement ∈ `declare_allergens`, `nutrition_info_present`, `declare_additive_function` |

The **Knowledge base** tab validates your files (missing sources, unknown categories, conflicting
permissions, `is_a` cycles, unsupported values). Candidate official sources to start from — verify
current clause numbers yourself — for India: FSS (Labelling & Display) Regulations 2020 and FSS (Food
Products Standards & Food Additives) Regulations 2011; internationally: Codex GSFA / CXG 23 and the
WHO sodium/sugar guidance.

Adding a new kind of check = add rules to `rules.pl` (+ a `reportable_kind`/`severity` line). No Python change needed
except a template line in `explanation_generator.py` for friendly text.

## Known limitations (be upfront about these in your report)
* Negation is negation-as-failure (closed world); "unknown" is handled separately via gaps.
* Parser is rule/regex-based: unusual label phrasing may need more `synonyms.csv` rows. Partial matches
  (e.g. "cocoa butter" → "butter") are flagged in parsing notes; add exact synonyms to avoid them.
* No condition evaluation inside `additive_limits.condition`; nutrition rules support only per-100 g/ml.
* Not legal or medical advice; complaint text is a draft to be checked against the physical label.
