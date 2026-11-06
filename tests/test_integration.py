"""Runs every demo test product and compares with expected_results.csv.
Statuses: reportable | confirmed | possible | absent."""
import pytest
import config
from knowledge.kb_loader import read_csv

EXPECTED = read_csv(config.DEMO_TEST_DIR / "expected_results.csv")


@pytest.mark.parametrize("row", EXPECTED, ids=lambda r: f"{r['test_id']}-{r['expected_conclusion']}-{r['expected_status']}")
def test_expected_conclusion(results, row):
    res = results[row["test_id"]]
    found = {f.key: f for f in res.findings}
    key = row["expected_conclusion"]
    if row["expected_status"] == "absent":
        assert key not in found, f"{key} should NOT have been concluded"
        return
    assert key in found, f"{key} missing; got {sorted(found)}"
    assert found[key].status == row["expected_status"]


def test_every_finding_is_proved_both_ways(results):
    for res in results.values():
        for f in res.findings:
            assert f.proofs and f.forward_proofs, f.key
            assert f.verified_backward, f"{res.pid}: {f.key} not re-proved by backward chaining"


def test_specificity_conflict_resolution(results):
    ov = results["T03"].overrides
    assert any(o["additive"] == "ins_102" and o["winning_category"] == "infant_food" for o in ov)
    # same additive in a soft drink: general rule applies, no violation
    assert "additive_not_permitted:ins_102" not in {f.key for f in results["T01"].findings}


def test_incomplete_information_is_not_treated_as_safe(results):
    r = results["T07"]
    assert r.verdict == "UNCERTAIN" and r.confidence in ("low", "very low")
    kinds = {g.kind for g in r.gaps}
    assert {"category_unknown", "unknown_ingredient", "additive_no_limit_data"} <= kinds


def test_verdicts(results):
    assert results["T02"].verdict == "ALLERGY_ALERT"
    assert results["T03"].verdict == "REGULATORY_CONCERN"
    assert results["T05"].verdict in ("NO_CONCERNS_FOUND", "UNCERTAIN")


def test_complaint_generated_only_for_reportable(analyzer, results):
    from reports.complaint_generator import generate_text
    txt = generate_text(results["T03"], analyzer, {"name": "Test User"})
    assert "Tartrazine" in txt and "Test User" in txt and "DEMO" in txt and "ANNEX A" in txt
    assert "No reportable" in generate_text(results["T07"], analyzer)


def test_free_form_backward_query(analyzer, results):
    r = results["T02"]
    sols = analyzer.ask(r, f"allergen_present({r.pid}, A, I, S)")
    assert {s.bindings["A"] for s in sols} == {"milk", "gluten", "soy"}


def test_allergy_profile_only_alerts_for_profile(results):
    assert "allergy_alert:milk" in {f.key for f in results["T02"].findings}
    assert not any(f.kind == "allergy_alert" for f in results["T03"].findings)
