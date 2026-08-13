"""Clause 12.5 — the system proposal and one-click controls in the admin email."""
from __future__ import annotations

import copy

from adjudicator import service
from adjudicator.models import ReturnRequest
from adjudicator.verdicts import Verdict

from .conftest import load_fixture


def run(payload: dict):
    return service.adjudicate(ReturnRequest.model_validate(payload), payload)


def test_auto_lane_cases_carry_no_review_controls():
    assert run(load_fixture("ord-1043-size-fit.json")).humanReview is None


def test_cod_escalation_proposes_what_it_would_have_decided():
    """Clause 6.3 is the only thing stopping this case, so the engine proposes."""
    result = run(load_fixture("ord-1047-cod-change-of-mind.json"))
    hr = result.humanReview
    assert hr.escalationKind == "cod"
    assert hr.proposedFinalVerdict == "APPROVE_ON_PICKUP"
    assert "APPROVE_ON_PICKUP" in hr.proposalBasis
    assert hr.options[0] == "APPROVE_ON_PICKUP"     # the proposal leads
    assert "REJECT_POLICY" in hr.options


def test_high_value_escalation_proposes_the_qc_route():
    payload = copy.deepcopy(load_fixture("ord-1043-size-fit.json"))
    payload["order"]["invoiceValue"] = 9200
    hr = run(payload).humanReview
    assert hr.escalationKind == "high_value"
    assert hr.proposedFinalVerdict == "APPROVE_ON_PICKUP"


def test_evidence_cases_deliberately_propose_nothing():
    """Proposing here would mean adjudicating on image content (Clause 12.3(a))."""
    hr = run(load_fixture("ord-1044-defect-photo.json")).humanReview
    assert hr.escalationKind == "evidence"
    assert hr.proposedFinalVerdict is None
    assert "12.3(a)" in hr.proposalBasis
    assert "APPROVE_ON_QC" in hr.options and "REJECT_NO_EVIDENCE" in hr.options


def test_safety_case_proposes_nothing_and_keeps_its_priority_flag():
    payload = copy.deepcopy(load_fixture("ord-1046-clearance.json"))
    payload["order"]["flags"]["clearance"] = False
    payload["return"]["description"] = "I used the neem oil and got an itchy rash on my arm."
    hr = run(payload).humanReview
    assert hr.escalationKind == "safety"
    assert hr.proposedFinalVerdict is None
    assert hr.priority == "SAFETY"
    assert "HOLD_INVESTIGATION" in hr.options


def test_policy_gap_proposes_nothing():
    hr = run(load_fixture("nonsense-no-matching-clause.json")).humanReview
    assert hr.escalationKind == "gap"
    assert hr.proposedFinalVerdict is None
    assert "18.2" in hr.proposalBasis


def test_every_offered_option_is_a_controlled_verdict():
    allowed = {v.value for v in Verdict}
    for name in ("ord-1044-defect-photo.json", "ord-1047-cod-change-of-mind.json",
                 "nonsense-no-matching-clause.json"):
        hr = run(load_fixture(name)).humanReview
        assert hr.options
        assert set(hr.options) <= allowed
        assert len(hr.options) == len(set(hr.options))   # no duplicates in the email
