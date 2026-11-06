from inference.backward_chaining import BackwardChainer
from inference.forward_chaining import ForwardChainer, stratify
from inference.terms import FactBase, Literal, Var, parse_goal, parse_program, split_program

PROGRAM = """
%% [R-A] ancestor base
anc(X, Y) :- parent(X, Y).
anc(X, Z) :- parent(X, Y), anc(Y, Z).
%% [R-B] orphan: person with no parent record
orphan(X) :- person(X), \\+ parent(_, X).
%% [R-C] tall
tall(X) :- height(X, H), H > 180.
"""


def _base():
    fb = FactBase()
    for a, b in [("a", "b"), ("b", "c"), ("c", "d")]:
        fb.add("parent", (a, b))
    for p in "abcd":
        fb.add("person", (p,))
    fb.add("height", ("a", 190)); fb.add("height", ("b", 170.5))
    return fb


def test_parser_roundtrip():
    rules, facts = split_program(parse_program(PROGRAM))
    assert len(rules) == 4 and not facts
    assert rules[0].id == "R-A" and rules[1].id == "R-A"      # continuation clause shares id
    g = parse_goal("anc(a, X).")
    assert g.pred == "anc" and isinstance(g.args[1], Var)


def test_forward_chaining_transitive_closure_and_negation():
    rules, _ = split_program(parse_program(PROGRAM))
    fc = ForwardChainer(rules, _base()); fc.run()
    assert ("a", "d") in fc.facts.by_pred["anc"]
    assert fc.facts.by_pred["orphan"] == {("a",)}              # NAF: only 'a' has no parent
    assert fc.facts.by_pred["tall"] == {("a",)}                # numeric comparison
    assert stratify(rules)["orphan"] > stratify(rules)["parent"]


def test_forward_proof_tree_is_grounded():
    rules, _ = split_program(parse_program(PROGRAM))
    fc = ForwardChainer(rules, _base()); fc.run()
    node = fc.proof("anc", ("a", "c"))
    assert node.kind == "rule" and node.children and node.depth() >= 2


def test_backward_chaining_matches_forward():
    rules, _ = split_program(parse_program(PROGRAM))
    fc = ForwardChainer(rules, _base()); fc.run()
    bc = BackwardChainer(rules, _base())
    sols = {s.goal.args for s in bc.prove(Literal("anc", ("a", Var("Y"))))}
    assert sols == {a for a in fc.facts.by_pred["anc"] if a[0] == "a"}
    assert bc.holds(parse_goal("orphan(a)")) and not bc.holds(parse_goal("orphan(b)"))
    assert bc.prove(parse_goal("tall(X)"))[0].bindings == {"X": "a"}


def test_backward_depth_limit_terminates_on_cycles():
    rules, _ = split_program(parse_program("anc(X,Y) :- parent(X,Y).\nanc(X,Z) :- parent(X,Y), anc(Y,Z)."))
    fb = FactBase(); fb.add("parent", ("a", "b")); fb.add("parent", ("b", "a"))
    bc = BackwardChainer(rules, fb, max_depth=15)
    assert bc.holds(parse_goal("anc(a, b)"))
    assert not bc.holds(parse_goal("anc(a, zzz)"))


def test_unstratifiable_program_rejected():
    import pytest
    rules, _ = split_program(parse_program("p(X) :- q(X), \\+ r(X).\nr(X) :- p(X)."))
    with pytest.raises(ValueError):
        stratify(rules)
