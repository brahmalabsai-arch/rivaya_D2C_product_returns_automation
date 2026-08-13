"""Gate-by-gate coverage of the deterministic layer."""
from __future__ import annotations

import copy

import pytest

from adjudicator import service
from adjudicator.models import ReturnRequest

from .conftest import load_fixture


def run(payload: dict):
    return service.adjudicate(ReturnRequest.model_validate(payload), payload)


@pytest.fixture
def apparel():
    return copy.deepcopy(load_fixture("ord-1043-size-fit.json"))


@pytest.fixture
def appliance():
    return copy.deepcopy(load_fixture("ord-1044-defect-photo.json"))


@pytest.fixture
def decor():
    return copy.deepcopy(load_fixture("ord-1045-outside-window.json"))


# --- gate 1: identity (Clause 3.2) ----------------------------------------- #

def test_third_party_request_is_rejected(apparel):
    apparel["order"]["registeredEmail"] = "someone.else@example.com"
    result = run(apparel)
    assert result.verdict == "REJECT_IDENTITY"
    assert result.citedClauses == ["Clause 3.2"]


# --- gate 2: marketplace (Clause 3.3) -------------------------------------- #

def test_marketplace_order_is_redirected(apparel):
    apparel["order"]["salesChannel"] = "amazon"
    result = run(apparel)
    assert result.verdict == "REDIRECT_MARKETPLACE"
    assert "Clause 3.3" in result.citedClauses


# --- gate 3: non-returnable (Clause 4.1) ----------------------------------- #

def test_clearance_item_is_still_returnable_for_transit_damage(apparel):
    """Clause 4.1 exempts DAMAGE_TRANSIT and WRONG_ITEM from the badge."""
    apparel["order"]["flags"]["clearance"] = True
    apparel["return"]["reasonCode"] = "DAMAGE_TRANSIT"
    apparel["return"]["description"] = "The parcel arrived crushed and the fabric is torn."
    apparel["return"]["photoAttached"] = True
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"          # 12.3(a), not REJECT_POLICY
    assert "Clause 12.3(a)" in result.citedClauses


def test_broken_hygiene_seal_is_non_returnable():
    payload = copy.deepcopy(load_fixture("ord-1046-clearance.json"))
    payload["order"]["flags"]["clearance"] = False
    payload["order"]["flags"]["hygieneSealBroken"] = True
    result = run(payload)
    assert result.verdict == "REJECT_POLICY"
    assert "Clause 4.1(c)" in result.citedClauses


# --- gate 4: safety and conduct narratives --------------------------------- #

def test_adverse_reaction_is_pulled_out_of_this_policy():
    payload = copy.deepcopy(load_fixture("ord-1046-clearance.json"))
    payload["order"]["flags"]["clearance"] = False
    payload["return"]["description"] = "I used the neem oil and got an itchy rash on my arm."
    result = run(payload)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 5.4.2" in result.citedClauses


def test_conduct_allegation_routes_to_a_person(apparel):
    apparel["return"]["description"] = (
        "The delivery executive was rude and I think the package was tampered with before it "
        "reached me."
    )
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 12.3(h)" in result.citedClauses


# --- gate 5: window (Clauses 2, 11.1, 5.1.2, 5.2.1) ------------------------ #

def test_festival_halving_only_bites_change_of_mind():
    """Clause 11.1(a) halves change-of-mind windows; other reasons keep theirs."""
    payload = copy.deepcopy(load_fixture("ord-1048-festival-window.json"))
    assert run(payload).verdict == "REJECT_WINDOW"        # day 4 vs halved 3-day window

    payload["return"]["reasonCode"] = "LATE_DELIVERY_REFUSED"
    payload["return"]["description"] = "It arrived four days after the promised delivery date."
    assert run(payload).verdict == "APPROVE_INSTANT"      # day 4 vs full 7-day window


def test_appliance_defect_outside_window_is_a_warranty_claim(appliance):
    appliance["order"]["daysSinceDelivery"] = 45
    result = run(appliance)
    assert result.verdict == "REDIRECT_WARRANTY"
    assert "Clause 5.1.2" in result.citedClauses


def test_appliance_defect_outside_warranty_is_a_window_rejection(appliance):
    appliance["order"]["daysSinceDelivery"] = 500
    result = run(appliance)
    assert result.verdict == "REJECT_WINDOW"


def test_fragile_transit_damage_has_a_48_hour_window(decor):
    decor["return"]["reasonCode"] = "DAMAGE_TRANSIT"
    decor["return"]["description"] = "The vase arrived cracked down one side."
    decor["return"]["photoAttached"] = True
    decor["order"]["daysSinceDelivery"] = 4               # inside the 7-day category window
    result = run(decor)
    assert result.verdict == "REJECT_WINDOW"
    assert "Clause 5.2.1" in result.citedClauses

    decor["order"]["daysSinceDelivery"] = 1
    assert run(decor).verdict == "ESCALATE_HUMAN"          # 12.3(a) with evidence attached


# --- gate 7: mandatory human review (Clause 12.3) -------------------------- #

def test_high_value_item_always_goes_to_a_person(apparel):
    apparel["order"]["invoiceValue"] = 9200
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 12.3(b)" in result.citedClauses


def test_return_rate_band_routes_to_review(apparel):
    apparel["customer"]["returnRate"] = 34.0              # 30-50% band, prepaid
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 13.1" in result.citedClauses


def test_cod_return_rate_band_is_tighter(apparel):
    apparel["order"]["paymentMode"] = "COD"
    apparel["customer"]["returnRate"] = 24.0              # under 30% but over the COD 20%
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 13.3" in result.citedClauses


def test_rto_history_routes_to_review(apparel):
    apparel["customer"]["rtoEvents180d"] = 2
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 6.4" in result.citedClauses


def test_missing_customer_history_is_not_an_adverse_signal(apparel):
    """Clause 13.2 — absent return-rate data is treated as normal, not risky."""
    assert "returnRate" not in apparel["customer"]
    assert run(apparel).verdict == "APPROVE_ON_PICKUP"


# --- gate 8: auto lane (Clauses 12.2, 7.1, 7.4) ---------------------------- #

def test_appliance_change_of_mind_carries_the_reverse_logistics_fee(appliance):
    appliance["return"]["reasonCode"] = "CHANGE_OF_MIND"
    appliance["return"]["description"] = "I changed my mind and no longer need the mixer."
    appliance["return"]["photoAttached"] = False
    appliance["return"]["photo"] = None
    appliance["order"]["daysSinceDelivery"] = 5
    result = run(appliance)
    assert result.verdict == "APPROVE_ON_QC"              # Clause 7.1(c), all appliances
    assert [(d.label, d.amount) for d in result.deductions] == [
        ("Reverse-logistics fee (Clause 5.1.3)", 149)
    ]


def test_loyalty_waiver_removes_the_fee(appliance):
    appliance["return"]["reasonCode"] = "CHANGE_OF_MIND"
    appliance["return"]["description"] = "I changed my mind and no longer need the mixer."
    appliance["return"]["photoAttached"] = False
    appliance["return"]["photo"] = None
    appliance["order"]["daysSinceDelivery"] = 5
    appliance["customer"]["lifetimeOrderValue"] = 62000
    result = run(appliance)
    assert result.deductions == []


def test_size_fit_on_non_apparel_is_a_policy_gap(appliance):
    appliance["return"]["reasonCode"] = "SIZE_FIT"
    appliance["return"]["description"] = "The size of the jar does not fit my counter."
    result = run(appliance)
    assert result.verdict == "ESCALATE_HUMAN"
    assert "Clause 18.2" in result.citedClauses


# --- perception: reason/description mismatch ------------------------------- #

def test_narrative_that_contradicts_the_reason_code_escalates(apparel):
    apparel["return"]["description"] = (
        "The kurta arrived with the seam torn open and the fabric is damaged."
    )
    result = run(apparel)
    assert result.verdict == "ESCALATE_HUMAN"
    assert result.confidence == "AMBIGUOUS"


def test_vague_description_does_not_trigger_a_mismatch(apparel):
    apparel["return"]["description"] = "Please take it back."
    assert run(apparel).verdict == "APPROVE_ON_PICKUP"
