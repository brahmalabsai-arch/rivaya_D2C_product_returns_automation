"""The endpoints stage 4's n8n workflow depends on."""
from __future__ import annotations

from fastapi.testclient import TestClient

from adjudicator.app import app

from .conftest import load_fixture

client = TestClient(app)


def _adjudicate(name: str) -> dict:
    return client.post("/adjudicate", json=load_fixture(name)).json()


# --- POST /draft ------------------------------------------------------------ #

def test_draft_produces_a_verdict_email_for_an_amended_case():
    """After a human amends ESCALATE_HUMAN to a real verdict, n8n needs copy."""
    payload = load_fixture("ord-1047-cod-change-of-mind.json")
    proposal = client.post("/adjudicate", json=payload).json()
    assert proposal["verdict"] == "ESCALATE_HUMAN"

    response = client.post("/draft", json={
        "payload": payload,
        "verdict": "APPROVE_ON_PICKUP",
        "citedClauses": proposal["citedClauses"] + ["Clause 2.3", "Clause 5.3.1"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "APPROVE_ON_PICKUP"
    assert body["lane"] == "AUTO"
    assert "approved" in body["customerEmailDraft"]["body"].lower()
    # COD refund wording (Clause 6.1 / 7.2), not the prepaid one
    assert "payout link" in body["customerEmailDraft"]["body"]


def test_draft_rejects_a_verdict_outside_the_controlled_list():
    """Clause 1.7 enforced at the API boundary, not just inside the engine."""
    response = client.post("/draft", json={
        "payload": load_fixture("ord-1043-size-fit.json"),
        "verdict": "REFUND_BECAUSE_NICE_CUSTOMER",
    })
    assert response.status_code == 422
    assert "controlled verdict list" in response.json()["detail"]


def test_draft_drops_clauses_an_adjudicator_invented():
    response = client.post("/draft", json={
        "payload": load_fixture("ord-1043-size-fit.json"),
        "verdict": "REJECT_POLICY",
        "citedClauses": ["Clause 2.3", "Clause 99.9", "Clause 4.1(z)"],
    })
    assert response.json()["citedClauses"] == ["Clause 2.3"]


def test_draft_email_still_filters_internal_clauses():
    """Clause 15.3 holds on the human path too."""
    body = client.post("/draft", json={
        "payload": load_fixture("ord-1044-defect-photo.json"),
        "verdict": "APPROVE_ON_QC",
        "citedClauses": ["Clause 2.1", "Clause 12.3(a)", "Clause 7.1(c)"],
    }).json()["customerEmailDraft"]["body"]
    assert "Clause 12.3" not in body
    assert "Clause 2.1" in body


# --- POST /decisions/{caseId}/outcome --------------------------------------- #

def test_outcome_is_appended_not_overwritten():
    payload = load_fixture("ord-1044-defect-photo.json")
    client.post("/adjudicate", json=payload)
    case_id = payload["requestId"]

    result = client.post(f"/decisions/{case_id}/outcome", json={
        "outcome": "amended",
        "finalVerdict": "APPROVE_ON_QC",
        "adjudicator": "rakesh@rivaya.in",
        "note": "Photo clearly shows a burnt motor coil.",
    }).json()
    assert result["proposedVerdict"] == "ESCALATE_HUMAN"
    assert result["finalVerdict"] == "APPROVE_ON_QC"

    rows = client.get("/decisions?limit=10").json()["decisions"]
    assert [r["decidedBy"] for r in rows[:2]] == ["human", "engine"]
    assert rows[1]["verdict"] == "ESCALATE_HUMAN"   # original proposal untouched


def test_outcome_rejects_an_uncontrolled_verdict():
    response = client.post("/decisions/RET-X/outcome", json={
        "outcome": "confirmed", "finalVerdict": "MAYBE_LATER"})
    assert response.status_code == 422


# --- GET /metrics ----------------------------------------------------------- #

def test_metrics_report_straight_through_and_amendment_rates():
    for name in ("ord-1043-size-fit.json", "ord-1045-outside-window.json",
                 "ord-1046-clearance.json", "ord-1044-defect-photo.json"):
        client.post("/adjudicate", json=load_fixture(name))

    client.post("/decisions/RET-FIXTURE1044/outcome",
                json={"outcome": "confirmed", "finalVerdict": "APPROVE_ON_QC"})

    m = client.get("/metrics").json()
    assert m["decisions"] == 4
    assert m["straightThrough"] == {"auto": 3, "humanReview": 1, "autoRatePct": 75.0}
    assert m["humanAdjudication"]["confirmed"] == 1
    assert m["humanAdjudication"]["amendmentRatePct"] == 0.0
    assert m["humanAdjudication"]["breachesClause15_2"] is False
    assert m["verdicts"]["REJECT_WINDOW"] == 1
    assert m["latency"]["avgMs"] is not None


def test_metrics_flag_a_clause_15_2_breach():
    client.post("/adjudicate", json=load_fixture("ord-1044-defect-photo.json"))
    client.post("/decisions/RET-FIXTURE1044/outcome",
                json={"outcome": "amended", "finalVerdict": "REJECT_NO_EVIDENCE"})
    human = client.get("/metrics").json()["humanAdjudication"]
    assert human["amendmentRatePct"] == 100.0
    assert human["breachesClause15_2"] is True
