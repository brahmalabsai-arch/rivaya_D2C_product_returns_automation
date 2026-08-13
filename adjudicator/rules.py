"""Deterministic adjudication. This module decides; nothing else does.

Hard gates run in this order, and the first hit short-circuits:

    1. identity            Clause 3.2
    2. marketplace         Clause 3.3
    3. non-returnable      Clause 4.1
    4. safety / conduct    Clauses 5.4.2, 12.3(h)   [see note]
    5. window              Clauses 2, 11.1, 5.1.2, 5.2.1
    6. evidence            Clauses 5.1.1, 5.5.1, 8.2
    7. human-review        Clause 12.3 (a)-(i), 6.3, 6.4, 13
    8. auto lane           Clauses 12.2, 7.1, 7.4

Note on step 4: IMPLEMENTATION_PLAN.md lists the window check before the
mandatory human-review triggers, and that ordering is preserved for every
trigger except the safety one. Clause 5.4.2 says adverse-reaction claims are
"not adjudicated under this policy" at all, and Clause 18.1 makes the more
specific clause prevail, so a rash/allergy narrative is pulled ahead of the
window arithmetic. Conduct allegations (12.3(h)) ride along for the same
reason: the claim is not about product condition, so the category window is
not the right first question.

The narrative scans in step 4 are keyword matches, not model calls — the
deterministic layer never depends on an LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config
from .models import ReturnRequest
from .verdicts import Confidence, Lane, Verdict, lane_for

# --------------------------------------------------------------------------- #
# Policy tables (mirrors of the doc; the doc remains the source of truth)
# --------------------------------------------------------------------------- #

CONTROLLED_REASON_CODES = {
    "DEFECT",
    "DAMAGE_TRANSIT",
    "WRONG_ITEM",
    "MISSING_PARTS",
    "NOT_AS_DESCRIBED",
    "SIZE_FIT",
    "CHANGE_OF_MIND",
    "LATE_DELIVERY_REFUSED",
}

# Clause 2 — category windows in calendar days from the POD scan (Clause 1.1/1.2)
CATEGORY_WINDOWS: dict[str, dict[str, object]] = {
    "appliance": {"defect": 10, "other": 7, "clause": "2.1"},
    "decor": {"defect": 7, "other": 7, "clause": "2.2"},
    "apparel": {"defect": 15, "other": 15, "clause": "2.3"},
    "personal_care": {"defect": 7, "other": 7, "clause": "2.4"},
}

# Clause 12.3(a) — reason codes that rely on photo/video evidence
EVIDENCE_REQUIRED = {
    "DEFECT",
    "DAMAGE_TRANSIT",
    "WRONG_ITEM",
    "MISSING_PARTS",
    "NOT_AS_DESCRIBED",
}

# Clause 4.1 — non-returnable items are still returnable for these two reasons
NON_RETURNABLE_EXEMPT = {"DAMAGE_TRANSIT", "WRONG_ITEM"}

# Clause 5.4.2 — adverse reaction, priority flag SAFETY
_SAFETY_RE = re.compile(
    r"\b(rash|rashes|allerg\w*|itch\w*|burn(?:ing|t|s)? (?:skin|scalp)|"
    r"skin (?:reaction|irritation)|hives|swelling|anaphyla\w*|hospital|"
    r"reaction to the (?:oil|soap|cream)|breakout)\b",
    re.I,
)
# Clause 12.3(h) — narrative alleges conduct rather than product condition
_CONDUCT_RE = re.compile(
    r"\b(delivery (?:boy|guy|agent|executive|person)|courier (?:was|behaved)|"
    r"rude|abusive|threaten\w*|tamper\w*|opened the (?:box|package) before|"
    r"stole|theft|swapped|fraud|misbehav\w*)\b",
    re.I,
)


@dataclass
class Decision:
    """The deterministic layer's output. Lane follows from the verdict."""

    verdict: Verdict
    clauses: list[str]
    reasoning: str
    confidence: Confidence = Confidence.CLEAR
    deductions: list[dict] = field(default_factory=list)
    window_days: int | None = None
    priority: str | None = None  # e.g. "SAFETY" (Clause 5.4.2)
    # Which gate escalated, so the admin email can offer the right controls.
    kind: str | None = None

    @property
    def lane(self) -> Lane:
        return lane_for(self.verdict)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def adjudicate(req: ReturnRequest) -> Decision:
    order = req.order
    ret = req.return_
    cust = req.customer
    reason = (ret.reasonCode or "").strip().upper()
    category = (order.category or "").strip().lower()
    payment = (order.paymentMode or "PREPAID").strip().upper()
    days = int(order.daysSinceDelivery or 0)
    flags = order.flags

    # ---- 0. the case must be adjudicable at all (Clause 18.2) -------------- #
    if reason not in CONTROLLED_REASON_CODES:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 5.0", "Clause 18.2"],
            reasoning=(
                f"The request carries reason code '{ret.reasonCode or '(none)'}', which is not one "
                "of the controlled reason codes in Clause 5.0. Policy forbids guessing an outcome "
                "for a case that matches no clause, so this goes to a human adjudicator."
            ),
            confidence=Confidence.AMBIGUOUS,
            kind="gap"
        )

    if category not in CATEGORY_WINDOWS:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 2", "Clause 18.2"],
            reasoning=(
                f"No return window is defined for category '{order.category or '(none)'}' in "
                "Clause 2, so the deterministic checks cannot be applied. Routed to a human "
                "adjudicator and logged as a policy gap."
            ),
            confidence=Confidence.AMBIGUOUS,
            kind="gap"
        )

    if reason == "SIZE_FIT" and category != "apparel":
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 5.0", "Clause 18.2"],
            reasoning=(
                "SIZE_FIT is defined for Apparel & Soft Furnishings only (Clause 5.0), but this "
                f"order is in the {category} category. The combination matches no clause, so it "
                "is routed to a human adjudicator rather than guessed."
            ),
            confidence=Confidence.AMBIGUOUS,
            kind="gap"
        )

    # ---- 1. identity (Clause 3.2) ----------------------------------------- #
    registered = (order.registeredEmail or "").strip().lower()
    requester = (cust.email or "").strip().lower()
    if registered and requester and registered != requester:
        return Decision(
            verdict=Verdict.REJECT_IDENTITY,
            clauses=["Clause 3.2"],
            reasoning=(
                "The request did not originate from the registered account email associated with "
                "the order. Clause 3.2 auto-rejects third-party requests and notifies the "
                "registered account."
            ),
        )

    # ---- 2. marketplace (Clause 3.3) -------------------------------------- #
    channel = (order.salesChannel or "").strip().lower()
    if channel and channel not in {"rivaya.in", "rivaya", "web", "direct"}:
        return Decision(
            verdict=Verdict.REDIRECT_MARKETPLACE,
            clauses=["Clause 3.3"],
            reasoning=(
                f"This order was placed through {order.salesChannel}. Clause 3.3 puts marketplace "
                "orders outside this policy — they follow the marketplace's own returns process "
                "and must not be adjudicated here."
            ),
        )

    # ---- 3. non-returnable items (Clause 4.1) ----------------------------- #
    if reason not in NON_RETURNABLE_EXEMPT:
        if flags.clearance:
            return Decision(
                verdict=Verdict.REJECT_POLICY,
                clauses=["Clause 4.1(e)", "Clause 4.2"],
                reasoning=(
                    "The item was bought at a clearance discount of 60% or more and carries the "
                    "'No Returns — Clearance' badge. Clause 4.1(e) makes it non-returnable for "
                    "every reason except transit damage or a wrong item shipped, and this request "
                    f"is a {reason} claim."
                ),
            )
        if category == "personal_care" and flags.hygieneSealBroken:
            return Decision(
                verdict=Verdict.REJECT_POLICY,
                clauses=["Clause 4.1(c)", "Clause 2.4", "Clause 4.2"],
                reasoning=(
                    "Personal Care items are not returnable once the hygiene seal is broken "
                    "(Clauses 2.4 and 4.1(c)), and this unit is recorded as seal-broken."
                ),
            )

    # ---- 4. safety and conduct narratives (Clauses 5.4.2, 12.3(h)) -------- #
    description = ret.description or ""
    if category == "personal_care" and _SAFETY_RE.search(description):
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 5.4.2", "Clause 12.3(c)"],
            reasoning=(
                "The description reports an adverse physical reaction. Clause 5.4.2 removes such "
                "claims from this policy entirely: the case is flagged SAFETY and must reach the "
                "Quality & Compliance cell within 4 business hours regardless of order value."
            ),
            priority="SAFETY",
            kind="safety"
        )
    if _CONDUCT_RE.search(description):
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 12.3(h)"],
            reasoning=(
                "The description alleges conduct — delivery-executive behaviour or tampering — "
                "rather than a product condition. Clause 12.3(h) always routes these to a person."
            ),
            kind="conduct"
        )

    # ---- 5. return window (Clauses 2, 11.1, 5.1.2, 5.2.1) ----------------- #
    window_clauses: list[str] = []
    spec = CATEGORY_WINDOWS[category]
    window = int(spec["defect"] if reason in EVIDENCE_REQUIRED else spec["other"])
    window_clause = f"Clause {spec['clause']}"

    if flags.festivalSale and reason == "CHANGE_OF_MIND":
        window = window // 2
        window_clauses.append("Clause 11.1(a)")

    # Clause 5.2.1 overrides the category window for fragile transit damage.
    fragile_48h = flags.fragile and reason == "DAMAGE_TRANSIT"
    if fragile_48h and days > 2:
        return Decision(
            verdict=Verdict.REJECT_WINDOW,
            clauses=["Clause 5.2.1", "Clause 8.1"],
            reasoning=(
                "Transit-damage claims on fragile-flagged SKUs must be raised with photos within "
                "48 hours of the proof-of-delivery scan (Clauses 5.2.1 and 8.1), which is "
                f"stricter than the {spec['clause']} window. This claim was raised {days} days "
                "after delivery."
            ),
            window_days=2,
        )

    if days > window:
        # Clause 5.1.2 — an out-of-window appliance defect is a warranty claim,
        # not a return. This is a redirect, not a rejection.
        if category == "appliance" and reason == "DEFECT":
            warranty_months = order.warrantyMonths if order.warrantyMonths is not None else 12
            if days <= warranty_months * 30:
                return Decision(
                    verdict=Verdict.REDIRECT_WARRANTY,
                    clauses=["Clause 5.1.2", "Clause 14.1"],
                    reasoning=(
                        f"The defect was reported {days} days after delivery, outside the "
                        f"{window}-day return window for appliances but inside the "
                        f"{warranty_months}-month manufacturer warranty. Clause 5.1.2 makes this "
                        "a warranty claim rather than a return, handled by the brand service "
                        "centre."
                    ),
                    window_days=window,
                )
        return Decision(
            verdict=Verdict.REJECT_WINDOW,
            clauses=[window_clause, *window_clauses],
            reasoning=(
                f"{_window_sentence(category, reason, window, window_clauses)} Delivery was "
                f"recorded {days} days ago, so the request falls outside the window."
            ),
            window_days=window,
        )

    # ---- 6. evidence (Clauses 5.1.1, 5.5.1, 8.2) -------------------------- #
    has_photo = bool(ret.photoAttached or (ret.photo and ret.photo.base64))
    if reason in EVIDENCE_REQUIRED and not has_photo:
        return Decision(
            verdict=Verdict.HOLD_EVIDENCE,
            clauses=_evidence_clauses(category, reason),
            reasoning=(
                f"A {reason} claim requires photographic or video evidence before it can be "
                "adjudicated. One evidence-request email is sent and the case is held for 72 "
                "hours; if nothing arrives it is auto-rejected as REJECT_NO_EVIDENCE."
            ),
            window_days=window,
        )

    # ---- 7. mandatory human review (Clause 12.3) -------------------------- #
    if reason in EVIDENCE_REQUIRED:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=[*_evidence_clauses(category, reason), "Clause 12.3(a)"],
            reasoning=(
                f"This is a {reason} claim inside the {window}-day window with photo evidence "
                "attached. Clause 12.3(a) always routes evidence-backed claims to a person — "
                "automated systems must not adjudicate on image content."
            ),
            window_days=window,
            kind="evidence"
        )

    if flags.highValue or float(order.invoiceValue or 0) >= config.HIGH_VALUE_THRESHOLD:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 1.6", "Clause 12.3(b)"],
            reasoning=(
                f"The invoice value of ₹{order.invoiceValue:,.0f} makes this a High-Value Item "
                f"(Clause 1.6, threshold ₹{config.HIGH_VALUE_THRESHOLD:,}). Clause 12.3(b) sends "
                "High-Value Items to a person for every reason code."
            ),
            window_days=window,
            kind="high_value"
        )

    if (
        payment == "COD"
        and reason == "CHANGE_OF_MIND"
        and float(order.invoiceValue or 0) >= config.COD_CHANGE_OF_MIND_THRESHOLD
    ):
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 6.3", "Clause 12.3(e)"],
            reasoning=(
                f"This is a change-of-mind return on a cash-on-delivery order of "
                f"₹{order.invoiceValue:,.0f}. Clause 6.3 requires human review for COD orders of "
                f"₹{config.COD_CHANGE_OF_MIND_THRESHOLD:,} or more regardless of any other factor."
            ),
            window_days=window,
            kind="cod"
        )

    if cust.rtoEvents180d:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 6.4", "Clause 12.3(e)"],
            reasoning=(
                f"The account has {cust.rtoEvents180d} unpaid or refused delivery event(s) in the "
                "trailing 180 days. Clause 6.4 routes all return requests from such accounts to a "
                "person."
            ),
            window_days=window,
            kind="rto"
        )

    rate_decision = _return_rate_gate(cust, payment, window)
    if rate_decision:
        return rate_decision

    if cust.returnsLast90Days is not None and cust.returnsLast90Days >= 5:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=["Clause 13.5", "Clause 12.3(d)"],
            reasoning=(
                f"The account has {cust.returnsLast90Days} returns in the last 90 days. Clause "
                "13.5 flags serial returners for the monthly abuse review irrespective of return "
                "rate, so the case is not auto-decided."
            ),
            window_days=window,
            kind="serial"
        )

    # ---- 8. auto lane (Clauses 12.2, 7.1, 7.4) ---------------------------- #
    return _auto_approval(order, reason, payment, window, window_clauses, cust)


# --------------------------------------------------------------------------- #
# Human-review controls (Clause 12.5)
# --------------------------------------------------------------------------- #

# The admin email carries "the system-proposed verdict with cited clauses" and
# one-click approve/amend controls. For most escalations the engine knows
# everything except the judgement call, so it can propose an outcome that the
# adjudicator confirms or amends — which is what the Clause 15.2 amendment-rate
# KPI counts.
#
# It deliberately proposes NOTHING for evidence, safety, conduct and policy-gap
# escalations. Proposing an outcome for a DEFECT claim would mean adjudicating
# on image content, which Clause 12.3(a) forbids outright; safety cases belong
# to Quality & Compliance (5.4.2); and a gap has no clause to reason from
# (18.2). In those cases the adjudicator picks from the options with no default.
_PROPOSES_A_VERDICT = {"high_value", "cod", "rate_band", "rto", "serial"}

# Plausible outcomes offered as one-click controls, per escalation kind.
_OPTIONS_BY_KIND: dict[str, list[Verdict]] = {
    "evidence": [
        Verdict.APPROVE_ON_QC,
        Verdict.APPROVE_ON_PICKUP,
        Verdict.APPROVE_REPLACEMENT,
        Verdict.APPROVE_PARTIAL,
        Verdict.REJECT_NO_EVIDENCE,
        Verdict.REJECT_POLICY,
        Verdict.HOLD_QC_DISPUTE,
    ],
    "safety": [Verdict.HOLD_INVESTIGATION, Verdict.APPROVE_INSTANT, Verdict.REJECT_POLICY],
    "conduct": [Verdict.HOLD_INVESTIGATION, Verdict.APPROVE_ON_PICKUP, Verdict.REJECT_POLICY],
    "gap": [
        Verdict.APPROVE_ON_PICKUP,
        Verdict.REJECT_POLICY,
        Verdict.REDIRECT_MARKETPLACE,
        Verdict.REDIRECT_WARRANTY,
    ],
    "rate_band": [Verdict.APPROVE_PARTIAL, Verdict.REJECT_POLICY, Verdict.HOLD_INVESTIGATION],
    "rto": [Verdict.REJECT_POLICY, Verdict.HOLD_INVESTIGATION],
    "serial": [Verdict.REJECT_POLICY, Verdict.HOLD_INVESTIGATION],
    "high_value": [Verdict.APPROVE_ON_QC, Verdict.APPROVE_PARTIAL, Verdict.REJECT_POLICY],
    "cod": [Verdict.APPROVE_PARTIAL, Verdict.REJECT_POLICY],
}


def human_review_controls(req: ReturnRequest, decision: Decision) -> dict:
    """What the admin case email should offer for a HUMAN_REVIEW case."""
    kind = decision.kind or "gap"
    proposed: Verdict | None = None
    deductions: list[dict] = []
    basis = ""

    if kind in _PROPOSES_A_VERDICT:
        provisional = _provisional_auto(req, decision.window_days)
        if provisional is not None:
            proposed = provisional.verdict
            deductions = provisional.deductions
            basis = (
                "Every check other than the one that escalated this case points to "
                f"{proposed.value}: {provisional.reasoning}"
            )
    else:
        basis = {
            "evidence": (
                "No verdict is proposed: Clause 12.3(a) forbids an automated system from "
                "adjudicating on image content, so the call on the photo is yours."
            ),
            "safety": (
                "No verdict is proposed: Clause 5.4.2 removes adverse-reaction claims from this "
                "policy and routes them to Quality & Compliance."
            ),
            "conduct": (
                "No verdict is proposed: the claim alleges conduct rather than product condition "
                "(Clause 12.3(h)), which this policy does not adjudicate."
            ),
            "gap": (
                "No verdict is proposed: the case matches no clause, and Clause 18.2 requires a "
                "human decision rather than a guess. Please log the gap for the quarterly review."
            ),
        }.get(kind, "")

    options: list[Verdict] = []
    if proposed:
        options.append(proposed)
    for verdict in _OPTIONS_BY_KIND.get(kind, _OPTIONS_BY_KIND["gap"]):
        if verdict not in options:
            options.append(verdict)

    return {
        "escalationKind": kind,
        "proposedFinalVerdict": proposed.value if proposed else None,
        "proposalBasis": basis,
        "proposedDeductions": deductions,
        "options": [v.value for v in options],
        "priority": decision.priority,
    }


def _provisional_auto(req: ReturnRequest, window: int | None) -> Decision | None:
    """What the auto lane would have returned had no 12.3 trigger fired."""
    order = req.order
    category = (order.category or "").lower()
    reason = (req.return_.reasonCode or "").upper()
    if category not in CATEGORY_WINDOWS or reason not in CONTROLLED_REASON_CODES:
        return None
    extra = ["Clause 11.1(a)"] if (order.flags.festivalSale and reason == "CHANGE_OF_MIND") else []
    return _auto_approval(
        order,
        reason,
        (order.paymentMode or "PREPAID").upper(),
        window or 0,
        extra,
        req.customer,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _window_sentence(category: str, reason: str, window: int, extra: list[str]) -> str:
    spec = CATEGORY_WINDOWS[category]
    base = (
        f"Clause {spec['clause']} allows {window} day(s) from the delivery date for a {reason} "
        f"request in this category"
    )
    if "Clause 11.1(a)" in extra:
        base += ", already halved because the order was placed during a declared festival sale"
    return base + "."


def _evidence_clauses(category: str, reason: str) -> list[str]:
    if reason in {"WRONG_ITEM", "MISSING_PARTS"}:
        return ["Clause 5.5.1"]
    if reason == "DAMAGE_TRANSIT":
        return ["Clause 8.2"] + (["Clause 5.2.1"] if category == "decor" else [])
    if reason == "DEFECT":
        return {
            "appliance": ["Clause 5.1.1"],
            "apparel": ["Clause 5.3.3"],
            "decor": ["Clause 5.2.2"],
        }.get(category, ["Clause 5.1.1"])
    return ["Clause 5.2.3"] if category == "decor" else ["Clause 5.0"]


def _return_rate_gate(cust, payment: str, window: int) -> Decision | None:
    """Clause 13.1 / 13.3 bands. Absent data is not an adverse signal (13.2)."""
    if cust.returnRate is None:
        return None
    review_at, restrict_at = (20.0, 40.0) if payment == "COD" else (30.0, 50.0)
    band_clause = "Clause 13.3" if payment == "COD" else "Clause 13.1"
    if cust.returnRate > restrict_at:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=[band_clause, "Clause 13.4", "Clause 12.3(d)"],
            reasoning=(
                f"The account's return rate is {cust.returnRate:.0f}%, above the "
                f"{restrict_at:.0f}% band in {band_clause}. Human review plus a store-credit-only "
                "refund restriction applies (Clause 13.4), communicated with the neutral wording "
                "in Clause 16.3."
            ),
            window_days=window,
            kind="rate_band"
        )
    if cust.returnRate >= review_at:
        return Decision(
            verdict=Verdict.ESCALATE_HUMAN,
            clauses=[band_clause, "Clause 12.3(d)"],
            reasoning=(
                f"The account's return rate is {cust.returnRate:.0f}%, inside the "
                f"{review_at:.0f}–{restrict_at:.0f}% band in {band_clause}, which requires human "
                "review on all requests."
            ),
            window_days=window,
            kind="rate_band"
        )
    return None


def _auto_approval(order, reason: str, payment: str, window: int, extra: list[str], cust) -> Decision:
    category = order.category.lower()
    clauses: list[str] = [f"Clause {CATEGORY_WINDOWS[category]['clause']}", *extra]

    # Clause 7.1 — the refund initiation point selects the approval verdict.
    if category == "appliance":
        verdict = Verdict.APPROVE_ON_QC
        clauses.append("Clause 7.1(c)")
        step = "refund initiated once warehouse QC confirms the unit's condition"
    elif reason == "LATE_DELIVERY_REFUSED":
        verdict = Verdict.APPROVE_INSTANT
        clauses.append("Clause 7.1(a)")
        step = "refund initiated immediately"
    else:
        verdict = Verdict.APPROVE_ON_PICKUP
        clauses.append("Clause 7.1(b)")
        step = "refund initiated once the pickup scan confirms the item's condition"

    # Condition clauses that the field executive verifies at pickup (Clause 9.3)
    if category == "apparel" and reason in {"SIZE_FIT", "CHANGE_OF_MIND"}:
        clauses.append("Clause 5.3.1")
    elif category == "personal_care":
        clauses.append("Clause 5.4.1")
    elif category == "appliance" and reason == "CHANGE_OF_MIND":
        clauses.append("Clause 5.1.3")
    clauses.append("Clause 9.3")

    # Clause 7.4 — fee schedule, with the loyalty waiver.
    deductions: list[dict] = []
    waived = (
        cust.lifetimeOrderValue is not None
        and cust.lifetimeOrderValue > config.LOYALTY_FEE_WAIVER_LTV
    )
    if reason == "CHANGE_OF_MIND" and category == "appliance":
        deductions.append({"label": "Reverse-logistics fee (Clause 5.1.3)", "amount": 149})
    elif reason == "SIZE_FIT" and category == "apparel" and payment == "COD":
        deductions.append({"label": "COD size-return fee (Clause 5.3.2)", "amount": 99})
    if deductions:
        clauses.append("Clause 7.4")
    if waived and deductions:
        deductions = []
        clauses.append("Clause 7.4 (loyalty waiver)")

    fee_text = ""
    if deductions:
        fee_text = (
            f" A ₹{deductions[0]['amount']:.0f} fee applies under Clause 7.4 and is itemised in "
            "the refund."
        )
    elif waived:
        fee_text = " The usual fee is waived under the Clause 7.4 loyalty waiver."

    clauses.append("Clause 12.2")
    return Decision(
        verdict=verdict,
        clauses=clauses,
        reasoning=(
            f"The request is inside the {window}-day window for this category, the reason code "
            "needs no photo evidence, the item is not high-value, and no clause routes this "
            f"combination to a person — so all Clause 12.2 auto-lane conditions hold. Approved "
            f"with {step}.{fee_text}"
        ),
        deductions=deductions,
        window_days=window,
    )
