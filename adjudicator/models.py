"""Payload / response schemas — the contracts from IMPLEMENTATION_PLAN.md §3.1 and §3.3.

Note on strictness: `reasonCode`, `category` and `paymentMode` are plain strings,
not enums. An unknown value must produce ESCALATE_HUMAN with a cited clause
(18.2 — no guessed outcomes), not an HTTP 422. Validation errors are for
malformed requests; unrecognised business values are an adjudication outcome.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(extra="allow")

    email: str = ""
    # Optional enrichment (Clause 13 / 6.4). Absent = unknown, treated as
    # "no adverse signal" per Clause 13.2 rather than assumed bad.
    returnRate: float | None = None            # percent, trailing 365 days (1.5)
    rtoEvents180d: int | None = None           # Clause 6.4
    lifetimeOrderValue: float | None = None    # Clause 7.4 loyalty waiver
    returnsLast90Days: int | None = None       # Clause 13.5
    accountAgeDays: int | None = None          # Clause 13.2


class OrderFlags(BaseModel):
    model_config = ConfigDict(extra="allow")

    clearance: bool = False
    festivalSale: bool = False
    fragile: bool = False
    highValue: bool = False
    handcrafted: bool = False       # Clause 5.2.3
    hygieneSealBroken: bool = False  # Clause 4.1(c)


class Order(BaseModel):
    model_config = ConfigDict(extra="allow")

    orderId: str = ""
    sku: str = ""
    itemName: str = ""
    category: str = ""
    invoiceValue: float = 0
    paymentMode: str = "PREPAID"
    deliveryDate: str | None = None
    daysSinceDelivery: int = 0
    flags: OrderFlags = Field(default_factory=OrderFlags)
    # Optional provenance fields (Clauses 3.2 / 3.3)
    registeredEmail: str | None = None
    salesChannel: str | None = None   # "rivaya.in" | "amazon" | "flipkart" | "nykaa"
    warrantyMonths: int | None = None  # Clause 5.1.2, default 12 for appliances


class Photo(BaseModel):
    model_config = ConfigDict(extra="allow")

    fileName: str = ""
    mimeType: str = ""
    base64: str = ""


class ReturnDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    reasonCode: str = ""
    description: str = ""
    photoAttached: bool = False
    photo: Photo | None = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = "rivaya-demo-store"
    intakeChannel: str = "form"
    policyVersion: str = "RHL-POL-RET-3.2"


class ReturnRequest(BaseModel):
    """§3.1 — both intake channels (form and chat) emit exactly this."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    requestId: str = ""
    submittedAt: str = ""
    customer: Customer = Field(default_factory=Customer)
    order: Order = Field(default_factory=Order)
    return_: ReturnDetails = Field(default_factory=ReturnDetails, alias="return")
    meta: Meta = Field(default_factory=Meta)


# --------------------------------------------------------------------------- #
# Response (§3.3)
# --------------------------------------------------------------------------- #

class Deduction(BaseModel):
    label: str
    amount: float


class EmailDraft(BaseModel):
    subject: str
    body: str


class CaseFileSummary(BaseModel):
    """Clause 12.1 Case File snapshot — what the admin email renders."""

    orderId: str
    sku: str
    itemName: str
    category: str
    invoiceValue: float
    paymentMode: str
    deliveryDate: str | None
    daysSinceDelivery: int
    windowDays: int | None
    reasonCode: str
    evidenceRequired: bool
    photoAttached: bool
    flags: dict[str, Any]
    intakeChannel: str


class DraftRequest(BaseModel):
    """POST /draft — the verdict email for a decision a human has just made.

    n8n needs this after an adjudicator confirms or amends a HUMAN_REVIEW case:
    the original response carried only a holding email (Clause 12.4). Drafting
    stays in the service so clause filtering (15.3) and the one-recourse rule
    (16.2) are applied in exactly one place.
    """

    payload: ReturnRequest
    verdict: str
    citedClauses: list[str] = Field(default_factory=list)
    deductions: list[Deduction] = Field(default_factory=list)
    note: str = ""


class DraftResponse(BaseModel):
    requestId: str
    verdict: str
    lane: str
    citedClauses: list[str]
    customerEmailDraft: EmailDraft


class HumanOutcomeRequest(BaseModel):
    """POST /decisions/{caseId}/outcome — Clause 15.1 / 15.2 audit trail."""

    outcome: Literal["confirmed", "amended"]
    finalVerdict: str
    adjudicator: str = ""
    note: str = ""


class HumanReviewControls(BaseModel):
    """Clause 12.5 — what the admin case email renders as one-click controls."""

    escalationKind: str
    proposedFinalVerdict: str | None = None
    proposalBasis: str = ""
    proposedDeductions: list[Deduction] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    priority: str | None = None


class AdjudicationResponse(BaseModel):
    requestId: str
    verdict: str
    lane: str
    citedClauses: list[str]
    reasoning: str
    customerEmailDraft: EmailDraft
    deductions: list[Deduction] = Field(default_factory=list)
    confidence: str
    # Beyond the §3.3 contract — extra keys are additive and n8n can ignore them.
    policyVersion: str = "RHL-POL-RET-3.2"
    caseFile: CaseFileSummary | None = None
    supportingClauses: list[dict[str, str]] = Field(default_factory=list)
    humanReview: HumanReviewControls | None = None
    adjudicatedAt: str = ""
