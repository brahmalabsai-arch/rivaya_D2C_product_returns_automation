"""Controlled verdict list (policy Clause 17) and lane mapping (Clause 12).

No adjudicator — human or automated — may issue an outcome outside this list
(Clause 1.7). The rules engine picks a member of `Verdict`; the lane follows
mechanically from `LANE_BY_VERDICT`.
"""
from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    APPROVE_INSTANT = "APPROVE_INSTANT"
    APPROVE_ON_PICKUP = "APPROVE_ON_PICKUP"
    APPROVE_ON_QC = "APPROVE_ON_QC"
    APPROVE_REPLACEMENT = "APPROVE_REPLACEMENT"
    APPROVE_PARTIAL = "APPROVE_PARTIAL"
    REJECT_POLICY = "REJECT_POLICY"
    REJECT_WINDOW = "REJECT_WINDOW"
    REJECT_NO_EVIDENCE = "REJECT_NO_EVIDENCE"
    REJECT_IDENTITY = "REJECT_IDENTITY"
    REDIRECT_WARRANTY = "REDIRECT_WARRANTY"
    REDIRECT_MARKETPLACE = "REDIRECT_MARKETPLACE"
    HOLD_EVIDENCE = "HOLD_EVIDENCE"
    HOLD_QC_DISPUTE = "HOLD_QC_DISPUTE"
    HOLD_INVESTIGATION = "HOLD_INVESTIGATION"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    CLOSE_PICKUP_FAILED = "CLOSE_PICKUP_FAILED"


class Lane(str, Enum):
    AUTO = "AUTO"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Confidence(str, Enum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"


# Clause 12.2 lists the conditions under which a verdict may be *communicated*
# automatically; 12.3 lists what always goes to a person. HOLD_EVIDENCE sits on
# the auto side deliberately: Clause 5.1.1 prescribes a single templated
# evidence-request email and a 72-hour hold, and 12.3(a)'s rationale
# ("automated systems must not adjudicate on image content") does not bite when
# there is no image to adjudicate. The human sees the case when the photo lands.
LANE_BY_VERDICT: dict[Verdict, Lane] = {
    Verdict.APPROVE_INSTANT: Lane.AUTO,
    Verdict.APPROVE_ON_PICKUP: Lane.AUTO,
    Verdict.APPROVE_ON_QC: Lane.AUTO,
    Verdict.APPROVE_REPLACEMENT: Lane.AUTO,
    Verdict.APPROVE_PARTIAL: Lane.HUMAN_REVIEW,   # Clause 7.5 / 12.3(i)
    Verdict.REJECT_POLICY: Lane.AUTO,
    Verdict.REJECT_WINDOW: Lane.AUTO,
    Verdict.REJECT_NO_EVIDENCE: Lane.AUTO,
    Verdict.REJECT_IDENTITY: Lane.AUTO,
    Verdict.REDIRECT_WARRANTY: Lane.AUTO,
    Verdict.REDIRECT_MARKETPLACE: Lane.AUTO,
    Verdict.HOLD_EVIDENCE: Lane.AUTO,
    Verdict.HOLD_QC_DISPUTE: Lane.HUMAN_REVIEW,
    Verdict.HOLD_INVESTIGATION: Lane.HUMAN_REVIEW,
    Verdict.ESCALATE_HUMAN: Lane.HUMAN_REVIEW,
    Verdict.CLOSE_PICKUP_FAILED: Lane.AUTO,
}

# Whether the verdict is an approval (drives refund-timeline copy in emails).
APPROVALS = {
    Verdict.APPROVE_INSTANT,
    Verdict.APPROVE_ON_PICKUP,
    Verdict.APPROVE_ON_QC,
    Verdict.APPROVE_REPLACEMENT,
    Verdict.APPROVE_PARTIAL,
}

REJECTIONS = {
    Verdict.REJECT_POLICY,
    Verdict.REJECT_WINDOW,
    Verdict.REJECT_NO_EVIDENCE,
    Verdict.REJECT_IDENTITY,
}

# Clause 16.2: a rejection email offers exactly ONE recourse path.
#   "evidence"  -> reply-to-reopen with new evidence
#   "policy"    -> grievance email
RECOURSE_BY_VERDICT: dict[Verdict, str] = {
    Verdict.REJECT_NO_EVIDENCE: "evidence",
    Verdict.HOLD_EVIDENCE: "evidence",
    Verdict.REJECT_POLICY: "policy",
    Verdict.REJECT_WINDOW: "policy",
    Verdict.REJECT_IDENTITY: "policy",
}


def lane_for(verdict: Verdict) -> Lane:
    return LANE_BY_VERDICT[verdict]
