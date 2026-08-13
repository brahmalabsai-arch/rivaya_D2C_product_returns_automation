"""Stage 3 acceptance criteria, straight from IMPLEMENTATION_PLAN.md §4."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from adjudicator import decision_log, retrieval, service
from adjudicator.models import ReturnRequest

from .conftest import load_fixture

# fixture file -> (verdict, lane)
ACCEPTANCE = {
    "ord-1043-size-fit.json": ("APPROVE_ON_PICKUP", "AUTO"),
    "ord-1044-defect-photo.json": ("ESCALATE_HUMAN", "HUMAN_REVIEW"),
    "ord-1045-outside-window.json": ("REJECT_WINDOW", "AUTO"),
    "ord-1046-clearance.json": ("REJECT_POLICY", "AUTO"),
    "ord-1047-cod-change-of-mind.json": ("ESCALATE_HUMAN", "HUMAN_REVIEW"),
    "ord-1048-festival-window.json": ("REJECT_WINDOW", "AUTO"),
}


def adjudicate(payload: dict):
    return service.adjudicate(ReturnRequest.model_validate(payload), payload)


@pytest.mark.parametrize("filename,expected", ACCEPTANCE.items(), ids=list(ACCEPTANCE))
def test_six_storefront_fixtures(filename, expected):
    """The six engineered storefront orders return exactly the planned outcome."""
    result = adjudicate(load_fixture(filename))
    assert (result.verdict, result.lane) == expected, result.reasoning


@pytest.mark.parametrize("filename", list(ACCEPTANCE))
def test_every_response_cites_a_real_clause(filename):
    """Every response cites >=1 clause, and every cited number exists in the doc."""
    result = adjudicate(load_fixture(filename))
    retriever = retrieval.get_retriever()
    assert result.citedClauses, "a verdict with no citation is not a verdict (Clause 1.7)"
    for citation in result.citedClauses:
        assert retriever.exists(citation), f"{citation} is not in RHL-POL-RET-3.2"


def test_defect_without_photo_holds_for_evidence():
    """DEFECT with no photo -> HOLD_EVIDENCE, citing the appliance evidence rule."""
    result = adjudicate(load_fixture("ord-1044-defect-no-photo.json"))
    assert result.verdict == "HOLD_EVIDENCE"
    assert "Clause 5.1.1" in result.citedClauses


def test_nonsense_case_escalates_and_never_guesses():
    """A case matching no clause -> ESCALATE_HUMAN (Clause 18.2), never a guess."""
    result = adjudicate(load_fixture("nonsense-no-matching-clause.json"))
    assert result.verdict == "ESCALATE_HUMAN"
    assert result.lane == "HUMAN_REVIEW"
    assert result.confidence == "AMBIGUOUS"
    assert "Clause 18.2" in result.citedClauses


def test_decision_log_line_per_request():
    """Clause 15.1 — one logged row per adjudication, with the Case File snapshot."""
    payload = load_fixture("ord-1043-size-fit.json")
    adjudicate(payload)
    adjudicate(load_fixture("ord-1045-outside-window.json"))

    path = Path(os.environ["RIVAYA_DECISION_LOG"])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 2
    first = rows[0]
    assert first["caseId"] == payload["requestId"]
    assert first["verdict"] == "APPROVE_ON_PICKUP"
    assert first["lane"] == "AUTO"
    assert first["citedClauses"]
    assert first["caseFile"]["order"]["orderId"] == "ORD-1043"
    assert first["policyVersion"] == "RHL-POL-RET-3.2"
    assert decision_log.tail(1)[0]["caseId"] == "RET-FIXTURE1045"


def test_photo_bytes_never_reach_the_decision_log():
    """Image payloads are scrubbed to a byte count before the row is written."""
    payload = load_fixture("ord-1044-defect-photo.json")
    adjudicate(payload)
    raw = Path(os.environ["RIVAYA_DECISION_LOG"]).read_text(encoding="utf-8")
    assert payload["return"]["photo"]["base64"] not in raw
    assert json.loads(raw.splitlines()[0])["caseFile"]["return"]["photo"]["base64Bytes"] > 0


def test_fee_is_itemised_for_cod_size_return():
    """Clause 5.3.2 / 7.4 — ₹99 fee on a COD apparel size return."""
    payload = load_fixture("ord-1043-size-fit.json")
    payload["order"]["paymentMode"] = "COD"
    result = adjudicate(payload)
    assert result.verdict == "APPROVE_ON_PICKUP"
    assert [d.amount for d in result.deductions] == [99]


def test_festival_halving_is_cited_and_resolvable():
    """Clause 11.1(a) must survive citation validation, not be silently dropped."""
    result = adjudicate(load_fixture("ord-1048-festival-window.json"))
    assert "Clause 11.1(a)" in result.citedClauses


def test_email_footer_only_quotes_verified_citations():
    """A citation that failed to resolve must never reach the customer."""
    retriever = retrieval.get_retriever()
    for filename in [*ACCEPTANCE, "nonsense-no-matching-clause.json"]:
        result = adjudicate(load_fixture(filename))
        footer = result.customerEmailDraft.body.rsplit("\n", 1)[-1]
        if not footer.startswith("This decision applied:"):
            continue
        for citation in footer.removeprefix("This decision applied:").split(","):
            citation = citation.strip()
            assert citation in result.citedClauses, f"{filename}: {citation} was not verified"
            assert retriever.exists(citation)


def test_customer_email_never_cites_internal_clauses():
    """Clause 15.3 — customer-facing copy cites public clauses (1-11) only."""
    for filename in ACCEPTANCE:
        result = adjudicate(load_fixture(filename))
        body = result.customerEmailDraft.body
        for internal in ("Clause 12", "Clause 13", "Clause 14", "Clause 15", "Clause 16",
                         "Clause 17", "Clause 18"):
            assert internal not in body, f"{filename} leaked {internal} into the customer email"


def test_human_review_email_is_a_holding_email():
    """Clause 12.4 — no final verdict is communicated while a case awaits review."""
    result = adjudicate(load_fixture("ord-1044-defect-photo.json"))
    body = result.customerEmailDraft.body.lower()
    assert "24 business hours" in body
    assert "approved" not in body and "rejected" not in body
