"""HTTP surface — the contract n8n's Webhook A will bind to (stage 4)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from adjudicator.app import app

from .conftest import load_fixture

client = TestClient(app)


def test_health_reports_the_indexed_policy():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["policyVersion"] == "RHL-POL-RET-3.2"
    assert body["clausesIndexed"] > 60


def test_adjudicate_returns_the_stage_3_contract():
    payload = load_fixture("ord-1043-size-fit.json")
    response = client.post("/adjudicate", json=payload)
    assert response.status_code == 200
    body = response.json()
    for key in (
        "requestId", "verdict", "lane", "citedClauses", "reasoning",
        "customerEmailDraft", "deductions", "confidence",
    ):
        assert key in body, f"missing contract key: {key}"
    assert body["requestId"] == payload["requestId"]
    assert body["lane"] in {"AUTO", "HUMAN_REVIEW"}
    assert body["confidence"] in {"CLEAR", "AMBIGUOUS"}
    assert body["customerEmailDraft"]["subject"] and body["customerEmailDraft"]["body"]
    assert body["caseFile"]["windowDays"] == 15


def test_verdict_is_always_from_the_controlled_list():
    from adjudicator.verdicts import Verdict

    allowed = {v.value for v in Verdict}
    for name in (
        "ord-1043-size-fit.json", "ord-1044-defect-photo.json", "ord-1045-outside-window.json",
        "ord-1046-clearance.json", "ord-1047-cod-change-of-mind.json",
        "ord-1048-festival-window.json", "nonsense-no-matching-clause.json",
    ):
        body = client.post("/adjudicate", json=load_fixture(name)).json()
        assert body["verdict"] in allowed


def test_malformed_payload_is_a_422_not_a_verdict():
    response = client.post("/adjudicate", json={"order": "not-an-object"})
    assert response.status_code == 422


def test_clause_lookup():
    assert client.get("/clauses/5.1.1").json()["clause"] == "Clause 5.1.1"
    assert client.get("/clauses/99.9").status_code == 404


def test_decisions_endpoint_tails_the_log():
    client.post("/adjudicate", json=load_fixture("ord-1045-outside-window.json"))
    body = client.get("/decisions?limit=5").json()
    assert body["decisions"][0]["verdict"] == "REJECT_WINDOW"
