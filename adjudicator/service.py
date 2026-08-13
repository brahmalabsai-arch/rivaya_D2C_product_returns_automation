"""Pipeline wiring: perceive → decide → ground → draft → log.

The invariant from the plan holds here literally: the LLM perceives, the
deterministic layer decides, and every verdict cites clauses that were resolved
out of the policy document rather than generated.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from . import config, decision_log, emailer, llm, retrieval, rules
from .models import (
    AdjudicationResponse,
    CaseFileSummary,
    Deduction,
    HumanReviewControls,
    ReturnRequest,
)
from .rules import Decision
from .verdicts import Confidence, Lane, Verdict

log = logging.getLogger(__name__)

# A mismatch between the narrative and the reason code cannot change these two
# verdicts: neither depends on what the customer wrote.
_NARRATIVE_INDEPENDENT = {Verdict.REJECT_IDENTITY, Verdict.REDIRECT_MARKETPLACE}


def adjudicate(req: ReturnRequest, raw_payload: dict) -> AdjudicationResponse:
    started = time.perf_counter()
    ret = req.return_
    order = req.order
    reason = (ret.reasonCode or "").strip().upper()
    category = (order.category or "").strip().lower()

    # --- 1. perception (LLM or keyword fallback; never decides) ------------- #
    aligned, align_note = llm.check_alignment(ret.description, reason)

    # --- 2. deterministic decision ----------------------------------------- #
    decision = rules.adjudicate(req)

    # --- 3. confidence rule ------------------------------------------------- #
    if not aligned and decision.verdict not in _NARRATIVE_INDEPENDENT:
        if decision.verdict is Verdict.ESCALATE_HUMAN:
            # Already heading to a person — keep the sharper citation and reason,
            # and just record the narrative doubt against the case.
            decision = Decision(
                verdict=decision.verdict,
                clauses=decision.clauses,
                reasoning=f"{decision.reasoning} {align_note}",
                confidence=Confidence.AMBIGUOUS,
                deductions=decision.deductions,
                window_days=decision.window_days,
                priority=decision.priority,
            )
        else:
            decision = Decision(
                verdict=Verdict.ESCALATE_HUMAN,
                clauses=["Clause 5.0", "Clause 12.3", "Clause 18.2"],
                reasoning=(
                    f"{align_note} The reason code drives both the window arithmetic and the "
                    "evidence rules, so a case whose narrative disagrees with it is not "
                    f"adjudicated automatically. The proposed outcome before this check was "
                    f"{decision.verdict.value}."
                ),
                confidence=Confidence.AMBIGUOUS,
                window_days=decision.window_days,
            )

    # --- 4. grounding: resolve every citation against the document ---------- #
    retriever = retrieval.get_retriever()
    verified: list[str] = []
    for citation in decision.clauses:
        if retriever.exists(citation):
            if citation not in verified:
                verified.append(citation)
        else:
            log.warning("dropping citation not present in %s: %s", config.POLICY_VERSION, citation)

    if not verified:
        # A verdict with no resolvable clause is not a verdict (Clause 1.7/18.2).
        decision = Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 18.2"],
            reasoning=(
                "The deterministic checks produced an outcome that could not be grounded in any "
                "clause of this policy version. Clause 18.2 requires ESCALATE_HUMAN rather than a "
                "guessed outcome; the gap is logged for the quarterly policy review."
            ),
            confidence=Confidence.AMBIGUOUS,
            window_days=decision.window_days,
        )
        verified = ["Clause 18.2"]

    # The draft's footer must quote what was actually verified, never a citation
    # that failed to resolve against this policy version.
    decision.clauses = verified

    confidence = decision.confidence
    if decision.verdict is Verdict.ESCALATE_HUMAN and confidence is Confidence.CLEAR:
        # A mandatory 12.3 trigger is an unambiguous route to a person; a gap is not.
        confidence = Confidence.CLEAR

    # --- 5. retrieval for grounding the draft ------------------------------- #
    cited_clauses = [c.as_dict() for c in retriever.resolve_all(verified)]
    supporting = _supporting_clauses(req, reason, category, exclude={c["clause"] for c in cited_clauses})

    # --- 6. customer email --------------------------------------------------- #
    email = emailer.build_email(req, decision, cited_clauses + supporting)

    # --- 7. response + decision log ----------------------------------------- #
    latency_ms = (time.perf_counter() - started) * 1000
    response = AdjudicationResponse(
        requestId=req.requestId,
        verdict=decision.verdict.value,
        lane=decision.lane.value,
        citedClauses=verified,
        reasoning=decision.reasoning.strip(),
        customerEmailDraft=email,
        deductions=[Deduction(**d) for d in decision.deductions],
        confidence=confidence.value,
        policyVersion=config.POLICY_VERSION,
        caseFile=_case_file(req, decision),
        supportingClauses=cited_clauses + supporting,
        humanReview=(
            HumanReviewControls(**rules.human_review_controls(req, decision))
            if decision.lane is Lane.HUMAN_REVIEW
            else None
        ),
        adjudicatedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    decision_log.write(
        request_id=req.requestId,
        payload=raw_payload,
        verdict=response.verdict,
        lane=response.lane,
        cited_clauses=verified,
        confidence=response.confidence,
        reasoning=response.reasoning,
        deductions=decision.deductions,
        latency_ms=latency_ms,
    )
    return response


def draft_for_verdict(
    req: ReturnRequest,
    verdict: Verdict,
    cited: list[str],
    deductions: list[dict],
    note: str,
) -> tuple[list[str], object]:
    """Draft the customer email for a verdict a human has settled on.

    Citations are still validated against the policy document — an adjudicator
    can amend the verdict, but not invent a clause.
    """
    retriever = retrieval.get_retriever()
    verified = [c for c in dict.fromkeys(cited) if retriever.exists(c)]
    decision = Decision(
        verdict=verdict,
        clauses=verified,
        reasoning=note,
        deductions=deductions,
    )
    clause_texts = [c.as_dict() for c in retriever.resolve_all(verified)]
    return verified, emailer.build_email(req, decision, clause_texts)


def _supporting_clauses(
    req: ReturnRequest, reason: str, category: str, exclude: set[str]
) -> list[dict[str, str]]:
    """Top-k retrieval from the structured-field query, filtered and de-duped.

    These clauses ground the email draft; they are *not* added to citedClauses,
    because a citation must come from the deterministic decision, not from a
    similarity score.
    """
    retriever = retrieval.get_retriever()
    flags = req.order.flags.model_dump()
    query = retrieval.build_query(
        category=category,
        reason_code=reason,
        payment_mode=(req.order.paymentMode or "PREPAID").upper(),
        days_since_delivery=int(req.order.daysSinceDelivery or 0),
        flags={k: bool(v) for k, v in flags.items()},
    )
    hits = retriever.search(query, top_k=config.TOP_K * 2)

    # Secondary query from the free-text description — used only to widen the
    # candidate pool, never as the primary signal.
    if (req.return_.description or "").strip():
        hits += retriever.search(req.return_.description, top_k=config.TOP_K)

    out: list[dict[str, str]] = []
    seen: set[str] = set(exclude)
    for clause, _score in hits:
        if clause.citation in seen:
            continue
        if not retrieval.keep(clause, category=category, reason_code=reason):
            continue
        seen.add(clause.citation)
        out.append(clause.as_dict())
        if len(out) >= config.TOP_K:
            break
    return out


def _case_file(req: ReturnRequest, decision: Decision) -> CaseFileSummary:
    """Clause 12.1 Case File snapshot for the admin email and the log."""
    order = req.order
    reason = (req.return_.reasonCode or "").upper()
    return CaseFileSummary(
        orderId=order.orderId,
        sku=order.sku,
        itemName=order.itemName,
        category=order.category,
        invoiceValue=order.invoiceValue,
        paymentMode=order.paymentMode,
        deliveryDate=order.deliveryDate,
        daysSinceDelivery=order.daysSinceDelivery,
        windowDays=decision.window_days,
        reasonCode=reason,
        evidenceRequired=reason in rules.EVIDENCE_REQUIRED,
        photoAttached=bool(req.return_.photoAttached or (req.return_.photo and req.return_.photo.base64)),
        flags=order.flags.model_dump(),
        intakeChannel=req.meta.intakeChannel,
    )
