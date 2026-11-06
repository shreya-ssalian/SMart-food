import pytest
from knowledge.kb_loader import load_rules, load_kb, KnowledgeBase
from inference.forward_chaining import stratify
import config


def test_rules_file_parses_and_is_stratifiable():
    rules, facts = load_rules()
    assert len(rules) > 30 and facts
    assert all(r.id and r.description for r in rules)           # every rule is documented
    stratify(rules)


def test_every_reportable_kind_has_severity():
    rules, facts = load_rules()
    sev = {f.args[0] for f in facts if f.pred == "severity"}
    rep = {f.args[0] for f in facts if f.pred == "reportable_kind"}
    assert rep <= sev


def test_demo_kb_is_consistent():
    kb = load_kb("demo")
    issues = [i for i in kb.validate() if i.level == "error"]
    assert not issues, issues
    for l in kb.limits:
        assert l["source"] in kb.sources


def test_empty_real_kb_falls_back_to_demo():
    kb = load_kb("auto")
    assert kb.is_demo or kb.summary()["facts"] > 0


def test_export_prolog(tmp_path):
    kb = load_kb("demo")
    p = kb.export_prolog(tmp_path / "facts.pl")
    text = p.read_text()
    assert "additive_limit(ins_102, infant_food, no, none," in text
