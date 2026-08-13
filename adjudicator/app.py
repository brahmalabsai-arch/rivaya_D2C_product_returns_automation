"""FastAPI surface for the Rivaya returns adjudicator.

    POST /adjudicate     the one endpoint n8n calls
    GET  /health         liveness + policy/clause counts
    GET  /clauses/{id}   clause lookup (handy when writing the admin email)
    GET  /decisions      tail of the decision log (Clause 15.1)

Run it with:  uvicorn adjudicator.app:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config, decision_log, metrics, retrieval, service
from .models import (
    AdjudicationResponse,
    DraftRequest,
    DraftResponse,
    HumanOutcomeRequest,
    ReturnRequest,
)
from .verdicts import Verdict, lane_for

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Rivaya Returns Adjudicator",
    version="1.0.0",
    description=(
        "Deterministic rules + clause-level retrieval over RHL-POL-RET-3.2. "
        "The LLM perceives; the rules decide; every verdict cites clauses."
    ),
)

# n8n posts server-side, but the demo storefront can call this directly during
# development, so keep CORS permissive for the demo host.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    retriever = retrieval.get_retriever()
    return {
        "status": "ok",
        "policyVersion": config.POLICY_VERSION,
        "policyPath": str(config.POLICY_PATH),
        "clausesIndexed": len(retriever.clauses),
        "llmEnabled": config.LLM_ENABLED,
        "llmModel": config.LLM_MODEL if config.LLM_ENABLED else None,
        "decisionLog": str(config.DECISION_LOG_PATH),
    }


@app.post("/adjudicate", response_model=AdjudicationResponse)
def adjudicate(payload: dict = Body(...)) -> AdjudicationResponse:
    try:
        req = ReturnRequest.model_validate(payload)
    except Exception as exc:  # malformed request, not an adjudication outcome
        raise HTTPException(status_code=422, detail=f"Malformed return payload: {exc}") from exc
    return service.adjudicate(req, payload)


@app.post("/draft", response_model=DraftResponse)
def draft(body: DraftRequest) -> DraftResponse:
    """Verdict email for a decision an adjudicator has just confirmed or amended.

    Clause 1.7 is enforced at the boundary: a verdict outside the controlled list
    is rejected rather than drafted.
    """
    try:
        verdict = Verdict(body.verdict)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{body.verdict}' is not in the controlled verdict list (Clause 17). "
                f"Allowed: {', '.join(v.value for v in Verdict)}"
            ),
        ) from exc

    cited, email = service.draft_for_verdict(
        body.payload,
        verdict,
        body.citedClauses,
        [d.model_dump() for d in body.deductions],
        body.note,
    )
    return DraftResponse(
        requestId=body.payload.requestId,
        verdict=verdict.value,
        lane=lane_for(verdict).value,
        citedClauses=cited,
        customerEmailDraft=email,
    )


@app.post("/decisions/{case_id}/outcome")
def record_outcome(case_id: str, body: HumanOutcomeRequest) -> dict:
    """Append an adjudicator's confirm/amend to the log (Clauses 15.1, 15.2)."""
    try:
        Verdict(body.finalVerdict)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"'{body.finalVerdict}' is not in the controlled verdict list (Clause 17).",
        ) from exc
    row = decision_log.write_human_outcome(
        case_id=case_id,
        outcome=body.outcome,
        final_verdict=body.finalVerdict,
        adjudicator=body.adjudicator,
        note=body.note,
    )
    return {
        "recorded": True,
        "caseId": case_id,
        "outcome": row["humanOutcome"],
        "proposedVerdict": row["proposedVerdict"],
        "finalVerdict": row["verdict"],
    }


@app.get("/metrics")
def operating_metrics(windowDays: int = 30) -> dict:
    """Straight-through rate, amendment rate (Clause 15.2), verdict mix."""
    return metrics.summary(windowDays)


@app.get("/clauses/{clause_id}")
def clause(clause_id: str) -> dict:
    found = retrieval.get_retriever().get(clause_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No clause {clause_id} in {config.POLICY_VERSION}")
    return {**found.as_dict(), "internal": found.internal, "letters": sorted(found.letters)}


@app.get("/decisions")
def decisions(limit: int = 20) -> dict:
    return {"count": limit, "decisions": decision_log.tail(limit)}
