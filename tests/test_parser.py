from parser.ingredient_parser import parse_ingredients
from parser.nutrition_parser import parse_nutrition
from parser.normalizer import Normalizer, parse_ins_code


def test_ins_codes():
    assert parse_ins_code("INS 102") == "102" and parse_ins_code("E150d") == "150d"
    assert parse_ins_code("sugar") is None


def test_functional_class_and_codes(analyzer):
    r = parse_ingredients("Preservative (INS 211, 202), Colour (E102)", Normalizer(analyzer.kb))
    ids = [(i.canonical, i.function) for i in r.items]
    assert ("ins_211", "preservative") in ids and ("ins_202", "preservative") in ids and ("ins_102", "colour") in ids


def test_nested_percent_and_statements(analyzer):
    r = parse_ingredients("Wheat flour (45%), Chocolate (sugar, milk solids). Contains: milk. May contain traces of nuts",
                          Normalizer(analyzer.kb))
    names = {i.canonical: i for i in r.items}
    assert names["wheat_flour"].percent == 45.0
    assert names["sugar"].parent == "chocolate" and names["sugar"].depth == 1
    assert r.declared_allergens == {"milk"} and r.advisory_allergens == {"tree_nut"}


def test_quantity_attached_to_additive(analyzer):
    r = parse_ingredients("Preservative (INS 250 - 200 mg/kg)", Normalizer(analyzer.kb))
    assert r.items[0].quantity_mg_kg == 200.0


def test_nutrition_per_serving_conversion_and_salt():
    n = parse_nutrition("Per serving (50 g): Sodium 400 mg, Fat 10 g")
    assert round(n.values["sodium"].value) == 800 and round(n.values["fat"].value) == 20
    assert n.values["salt"].derived
    k = parse_nutrition("Energy 1500 kJ / 360 kcal; of which saturates 3 g; Salt 1.5 g")
    assert k.values["energy"].value == 360 and k.values["saturated_fat"].value == 3
    assert k.values["sodium"].value == 600 and k.basis == "assumed_per_100"


def test_empty_inputs():
    assert parse_nutrition("").values == {}
    assert parse_ingredients("", None).items == []
