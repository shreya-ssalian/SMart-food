"""Central configuration for SmartFood AI."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "knowledge_base"          # <-- YOUR verified data goes here
TEST_DIR = DATA_DIR / "test_data"
DEMO_DIR = DATA_DIR / "demo"                  # illustrative seed data (NOT verified)
DEMO_KB_DIR = DEMO_DIR / "knowledge_base"
DEMO_TEST_DIR = DEMO_DIR / "test_data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
RULES_FILE = KNOWLEDGE_DIR / "rules.pl"
FACTS_FILE = KNOWLEDGE_DIR / "facts.pl"
ONTOLOGY_FILE = KNOWLEDGE_DIR / "ontology.pl"
TEMPLATE_DIR = BASE_DIR / "reports" / "templates"

# Tables that must contain rows before the real KB is considered "populated".
CORE_TABLES = ["additives", "allergens", "allergen_derivatives", "synonyms",
               "additive_limits", "nutrition_rules", "label_rules",
               "food_categories", "ingredient_relations"]

# ---- nutrition ------------------------------------------------------------
CANONICAL_UNITS = {"energy": "kcal", "sodium": "mg", "cholesterol": "mg"}
DEFAULT_UNIT = "g"
UNIT_TO_G = {"g": 1.0, "mg": 1e-3, "mcg": 1e-6, "µg": 1e-6, "ug": 1e-6, "kg": 1e3}
SALT_TO_SODIUM_MG_PER_G = 400.0   # 1 g salt ~ 400 mg sodium

# ---- label parsing --------------------------------------------------------
FUNCTION_CLASSES = {
    "preservative", "colour", "color", "emulsifier", "antioxidant",
    "acidity regulator", "flavour enhancer", "flavor enhancer", "sweetener",
    "stabiliser", "stabilizer", "thickener", "raising agent", "anticaking agent",
    "anti caking agent", "humectant", "firming agent", "gelling agent",
    "glazing agent", "bulking agent", "foaming agent", "sequestrant",
    "colouring", "coloring", "acid", "flour treatment agent", "carrier",
}
FUNCTION_NORMALISE = {"color": "colour", "coloring": "colour", "colouring": "colour",
                      "flavor enhancer": "flavour_enhancer", "flavour enhancer": "flavour_enhancer",
                      "stabilizer": "stabiliser", "anti caking agent": "anticaking_agent"}
SUPPORTED_LABEL_REQUIREMENTS = {"declare_allergens", "nutrition_info_present",
                                "declare_additive_function"}
SUPPORTED_RELATION_TYPES = {"is_a", "interacts_with", "contradicts_claim"}

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
MAX_PROOF_DEPTH = 80
