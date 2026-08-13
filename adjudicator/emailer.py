"""Customer email drafting.

Communication standards enforced here (Clause 16):
  16.1  state the decision, the clause(s) in plain language, the refund method
        and timeline, and the next physical step
  16.2  a rejection offers exactly ONE recourse path
  16.3  restricted-refund cases use the neutral wording verbatim
  16.4  plain language in the body; clause numbers in a footer line
  15.3  customer-facing copy cites public clauses (1-11) only

Drafts are built from templates first; the LLM only ever rewrites an already
complete draft (see llm.py), so a missing API key changes tone, not substance.
"""
from __future__ import annotations

import re

from . import llm
from .models import EmailDraft, ReturnRequest
from .rules import Decision
from .verdicts import APPROVALS, RECOURSE_BY_VERDICT, Verdict

GRIEVANCE_EMAIL = "grievance@rivaya.in"
SUPPORT_EMAIL = "returns@rivaya.in"

_PUBLIC_CLAUSE_RE = re.compile(r"Clause\s+(\d+)")

# Clause 7.2 — the figures to quote, keyed by payment mode.
_REFUND_TIMELINE = {
    "PREPAID": (
        "The refund goes back to your original payment method: 1–3 business days for "
        "UPI or wallet, 5–7 business days for cards."
    ),
    "COD": (
        "Because this was a cash-on-delivery order, we will send you a payout link. Refunds "
        "reach your bank 2–4 business days after you submit your account details, or you can "
        "choose Rivaya store credit at 105% of the refund value, credited instantly."
    ),
}


def public_clauses(clauses: list[str]) -> list[str]:
    """Clause 15.3 — internal SOP clauses (12-18) never appear in customer copy."""
    out: list[str] = []
    for c in clauses:
        m = _PUBLIC_CLAUSE_RE.search(c)
        if m and int(m.group(1)) <= 11 and c not in out:
            out.append(c)
    return out


def build_email(req: ReturnRequest, decision: Decision, clause_texts: list[dict]) -> EmailDraft:
    order = req.order
    item = order.itemName or order.sku or "your item"
    request_id = req.requestId or "your request"
    payment = (order.paymentMode or "PREPAID").upper()
    verdict = decision.verdict

    cited = public_clauses(decision.clauses)
    footer = (
        "This decision applied: " + ", ".join(cited)
        if cited
        else "Our returns policy is published at rivaya.in/returns."
    )

    subject, body = _template(verdict, item, request_id, payment, decision)
    body = f"{body}\n\n{footer}"

    context = (
        f"Decision: {verdict.value} (already final).\n"
        f"Item: {item} (order {order.orderId}, ₹{order.invoiceValue:,.0f}, {payment}).\n"
        f"Why: {decision.reasoning}\n"
        f"Deductions: {decision.deductions or 'none'}\n"
        f"Recourse allowed: {RECOURSE_BY_VERDICT.get(verdict, 'none')}\n"
        f"Exact footer line to end with: {footer}\n"
        "Clause texts you may paraphrase (do not quote clause numbers in the body):\n"
        + "\n".join(f"- {c['clause']}: {c['text'][:400]}" for c in clause_texts[:6])
    )
    subject, body = llm.polish_email(subject=subject, body=body, context=context)
    if footer not in body:
        body = f"{body.rstrip()}\n\n{footer}"
    return EmailDraft(subject=subject, body=body)


# --------------------------------------------------------------------------- #

def _template(
    verdict: Verdict, item: str, request_id: str, payment: str, decision: Decision
) -> tuple[str, str]:
    timeline = _REFUND_TIMELINE.get(payment, _REFUND_TIMELINE["PREPAID"])
    fee_line = ""
    if decision.deductions:
        parts = ", ".join(f"₹{d['amount']:,.0f} {d['label']}" for d in decision.deductions)
        fee_line = f" We will deduct {parts} from the refund and show it on the credit note."

    if verdict is Verdict.APPROVE_INSTANT:
        return (
            f"Your return for {item} is approved",
            f"We have approved your return request {request_id} for {item}, and the refund is "
            f"already on its way.{fee_line} {timeline} There is nothing further you need to do.",
        )

    if verdict is Verdict.APPROVE_ON_PICKUP:
        return (
            f"Your return for {item} is approved — pickup scheduled",
            f"We have approved your return request {request_id} for {item}. Our pickup partner "
            "will collect the item within the next 2–3 working days; please keep it with its "
            "tags, accessories and original packaging where you still have them. The refund is "
            f"initiated as soon as the pickup is scanned.{fee_line} {timeline}",
        )

    if verdict is Verdict.APPROVE_ON_QC:
        return (
            f"Your return for {item} is approved — pickup scheduled",
            f"We have approved your return request {request_id} for {item}. Our pickup partner "
            "will collect the item within the next 2–3 working days — please pack it back into "
            "its original carton and inner moulds, which we need for safe transit. Once our "
            "warehouse team checks the unit, we start the refund the same day."
            f"{fee_line} {timeline}",
        )

    if verdict is Verdict.APPROVE_REPLACEMENT:
        return (
            f"We are shipping a replacement for {item}",
            f"Thank you for flagging this. We have confirmed the mix-up on request {request_id} "
            f"and a replacement for {item} is being dispatched now. You do not need to wait for "
            "the pickup — our partner will collect the item you received when the replacement "
            "arrives.",
        )

    if verdict is Verdict.HOLD_EVIDENCE:
        return (
            f"We need one photo to process your return for {item}",
            f"We have received your return request {request_id} for {item}. To take it forward "
            "we need a photo showing the issue — for a damaged or faulty item, a clear picture "
            "of the item itself and of the outer packaging helps us most. Just reply to this "
            "email with the photo attached and we will pick the case straight back up. We will "
            "hold the request open for 72 hours.",
        )

    if verdict is Verdict.REJECT_NO_EVIDENCE:
        return (
            f"We could not process your return for {item}",
            f"We held your return request {request_id} for {item} for 72 hours while we waited "
            "for a photo of the issue, and none reached us, so we have had to close it. If you "
            "still have the item and can send us a photo, reply to this email with it attached "
            "and we will reopen the request.",
        )

    if verdict is Verdict.REJECT_WINDOW:
        return (
            f"We could not accept your return for {item}",
            f"Thank you for writing in about {item} (request {request_id}). Returns for this "
            "category have to be raised within a set number of days from delivery, and this "
            "request came in after that period closed, so we are not able to accept it. If you "
            f"believe this is a mistake, please write to {GRIEVANCE_EMAIL} and our grievance "
            "team will look at it independently.",
        )

    if verdict is Verdict.REJECT_POLICY:
        return (
            f"We could not accept your return for {item}",
            f"Thank you for writing in about {item} (request {request_id}). This item is marked "
            "non-returnable on its product page, so we are not able to accept it back for this "
            "reason. Items bought at a clearance discount, personalised items and opened "
            "personal-care products fall into this group. If you believe this is a mistake, "
            f"please write to {GRIEVANCE_EMAIL} and our grievance team will look at it "
            "independently.",
        )

    if verdict is Verdict.REJECT_IDENTITY:
        return (
            "We could not verify this return request",
            f"We received return request {request_id}, but it did not come from the email "
            "address registered against the order, so we are not able to act on it. The account "
            "holder has been notified separately. If this order is yours, please raise the "
            f"request from your registered email or write to {GRIEVANCE_EMAIL}.",
        )

    if verdict is Verdict.REDIRECT_WARRANTY:
        return (
            f"Your {item} is covered by warranty, not returns",
            f"Thank you for telling us about the problem with {item} (request {request_id}). The "
            "return window for this category has closed, but the unit is still inside the "
            "manufacturer's warranty, so this is handled as a service claim rather than a "
            "return. We have attached your warranty reference and the service-centre locator; "
            "the brand's engineer will repair or replace the unit at no cost to you.",
        )

    if verdict is Verdict.REDIRECT_MARKETPLACE:
        return (
            "Please raise this return where you bought the item",
            f"We found your order for {item}, but it was placed through a marketplace rather "
            "than rivaya.in. Returns for those orders are handled under the marketplace's own "
            "policy, so please raise the request from your order history there — they can action "
            "it much faster than we can.",
        )

    if verdict is Verdict.CLOSE_PICKUP_FAILED:
        return (
            f"We closed your return for {item} after three pickup attempts",
            f"Our partner tried three times over seven days to collect {item} for request "
            f"{request_id} and could not complete the pickup, so we have closed the request. If "
            "you are still within the return window for this item, you can raise a fresh request "
            "and we will schedule a new pickup.",
        )

    # ESCALATE_HUMAN / HOLD_QC_DISPUTE / HOLD_INVESTIGATION / APPROVE_PARTIAL:
    # Clause 12.4 — a holding email only. The verdict email is sent after the
    # human adjudicator confirms or amends the proposal.
    return (
        f"We have received your return request for {item}",
        f"Thank you — your return request {request_id} for {item} is with our returns team now. "
        "One of our specialists reviews requests like this one personally, and you will have a "
        "decision within 24 business hours. There is nothing you need to do in the meantime; if "
        f"anything is unclear you can reply to this email or write to {SUPPORT_EMAIL}.",
    )
