# RIVAYA HOME & LIVING PVT. LTD.
## Returns, Refunds & Exchange Policy — Combined Customer Policy and Internal Adjudication SOP
**Document ID:** RHL-POL-RET-3.2 | **Version:** 3.2 | **Effective:** 01 April 2026 | **Owner:** Customer Experience Operations | **Review cycle:** Quarterly

> **Note on document structure.** Sections 1–11 constitute the customer-facing policy as published on rivaya.in. Sections 12–18 are internal Standard Operating Procedure (SOP) for the Returns Adjudication Desk and are not published externally. All adjudication decisions — human or automated — must cite the specific clause number(s) relied upon.

---

## 1. Definitions

**1.1** "Delivery Date" means the date recorded by the logistics partner's proof-of-delivery (POD) scan, not the date the customer opens the package.

**1.2** "Return Window" means the number of calendar days from the Delivery Date within which a return request must be *raised* (not completed). A request raised at 23:59 IST on the final day is within window.

**1.3** "Prepaid Order" means an order paid in full at checkout via UPI, card, net banking, or wallet. "COD Order" means cash or UPI collected on delivery.

**1.4** "Defect" means a functional or material failure attributable to manufacturing, present at delivery or arising during normal use within the applicable window. "Damage" means physical harm arising in transit or handling. The distinction matters: transit damage claims follow Clause 8; defect claims follow the category rules in Clause 5.

**1.5** "Return Rate" means, for a given customer account (keyed on registered email), the ratio of delivered units returned to delivered units purchased over the trailing 365 days, expressed as a percentage. Orders cancelled before dispatch do not count in either numerator or denominator.

**1.6** "High-Value Item" means any single unit with an invoice value of ₹7,500 or more after discounts.

**1.7** "Verdict" means the final adjudication outcome, drawn exclusively from the controlled list in Clause 17. No adjudicator, human or automated, may issue an outcome outside this list.

---

## 2. Return Windows by Category

**2.1** Kitchen & Small Appliances (mixer-grinders, kettles, toasters, air fryers, hand blenders, OTGs): **10 days** for defect or damage claims; **7 days** for change-of-mind returns, subject to Clause 5.1.

**2.2** Home & Decor (ceramics, vases, wall art, lamps, glassware, planters): **7 days**, all reasons. Fragile-flagged SKUs follow the additional evidence rules in Clause 5.2.

**2.3** Apparel & Soft Furnishings (kurtas, loungewear, cushion covers, bedsheets, curtains, throws): **15 days**, all reasons, subject to the trial condition in Clause 5.3.

**2.4** Personal Care (soaps, essential oils, diffuser refills, haircare): **not returnable once the hygiene seal is broken**, per Clause 4.1(c). Unopened units: **7 days**.

**2.5** Where a single order contains items from multiple categories, each line item carries its own window. A return request against a line item is adjudicated independently of other items in the same order.

**2.6** If the final day of a window falls on a national holiday declared by the Government of India, the window extends to the next working day. (Sundays do not extend the window.)

---

## 3. General Eligibility Conditions

**3.1** All returns require the item to be unused beyond reasonable inspection, in original packaging where the packaging is integral (see Clause 3.4), with all accessories, manuals, warranty cards, and free gifts included.

**3.2** The return request must originate from the registered account email associated with the order. Requests from third-party emails are auto-rejected with verdict REJECT_IDENTITY (Clause 17), and the registered account is notified.

**3.3** Items purchased through Rivaya's own website (rivaya.in) are governed by this policy. Items purchased through marketplaces (Amazon, Flipkart, Nykaa) follow the respective marketplace's policy and must not be adjudicated under this document; such requests receive verdict REDIRECT_MARKETPLACE.

**3.4** "Packaging is integral" for: all appliances (thermocol moulds and inner cartons required for safe reverse transit) and fragile-flagged Home & Decor SKUs. Packaging is NOT integral for apparel and soft furnishings; absence of the polybag alone must not be grounds for rejection.

**3.5** Free gifts and combo items: if the qualifying item is returned, the free gift must be returned in the same pickup or its MRP is deducted from the refund. Combo packs are returnable only as complete combos.

---

## 4. Non-Returnable Items

**4.1** The following are not returnable under any reason code except transit damage (Clause 8) or wrong-item-shipped (Clause 5.5):
  (a) items marked "Final Sale" on the product page at time of order;
  (b) customised or personalised items (monogrammed, made-to-order upholstery);
  (c) Personal Care items with broken hygiene seals;
  (d) gift cards and store credit;
  (e) items purchased with a clearance discount of 60% or more (the product page displays a "No Returns — Clearance" badge).

**4.2** A request against a non-returnable item for a non-exempt reason receives verdict REJECT_POLICY with the applicable sub-clause cited.

---

## 5. Reason Codes, Evidence Requirements, and Category-Specific Rules

**5.0 Controlled reason codes.** Every return request must be mapped to exactly one primary reason code:
  DEFECT (functional/material failure), DAMAGE_TRANSIT (physical damage on arrival), WRONG_ITEM (item different from ordered), SIZE_FIT (apparel only), NOT_AS_DESCRIBED (colour/material/spec mismatch vs. product page), CHANGE_OF_MIND (no fault alleged), MISSING_PARTS (accessories or components absent), LATE_DELIVERY_REFUSED (delivered after promised date and customer no longer wants it).

**5.1 Kitchen & Small Appliances.**
  5.1.1 DEFECT claims within 10 days require: (a) a description of the failure; (b) photographic or video evidence showing the defect or the unit's condition. Claims with evidence proceed per Clause 12; claims without evidence receive one evidence-request email and are held for 72 hours (verdict HOLD_EVIDENCE), after which they are auto-rejected (REJECT_NO_EVIDENCE) if nothing is received.
  5.1.2 DEFECT claims raised after the 10-day window but within the manufacturer warranty period (12 months unless stated otherwise) are not returns; they are warranty claims. Verdict: REDIRECT_WARRANTY, with the brand service-centre process attached.
  5.1.3 CHANGE_OF_MIND within 7 days: eligible only if the unit is unused and factory-sealed or demonstrably unused; a reverse-logistics fee of ₹149 is deducted from the refund (Clause 7.4).
  5.1.4 Appliances returned for DEFECT that test "No Fault Found" at the warehouse QC bench are re-shipped to the customer once at Rivaya's cost; a repeat claim on the same unit routes to human review (ESCALATE_HUMAN).

**5.2 Home & Decor.**
  5.2.1 Fragile-flagged SKUs (ceramics, glassware): DAMAGE_TRANSIT claims require photos of (a) the damaged item and (b) the outer packaging, uploaded within 48 hours of the POD scan. This is stricter than the 7-day window and overrides it for this reason code.
  5.2.2 Non-fragile decor follows the standard 7-day window for all reason codes, with photo evidence required for DEFECT and DAMAGE_TRANSIT.
  5.2.3 Colour-variance claims under NOT_AS_DESCRIBED for handcrafted SKUs (product page carries a "Handcrafted — variations expected" note) are rejected (REJECT_POLICY citing this clause) unless the variance is gross (different colour family), in which case route to human review.

**5.3 Apparel & Soft Furnishings.**
  5.3.1 SIZE_FIT and CHANGE_OF_MIND within 15 days: eligible with tags attached and no signs of wash, wear, stain, or fragrance. No photo evidence is required at request time; condition is verified at pickup by the field executive's checklist (Clause 9.3).
  5.3.2 First exchange for SIZE_FIT is free (no reverse-logistics fee); refunds for SIZE_FIT carry a ₹99 fee for COD orders and no fee for prepaid orders.
  5.3.3 DEFECT claims (torn seams, broken zippers, colour bleed on first wash performed per care label) require photo evidence and follow Clause 12 routing.

**5.4 Personal Care.**
  5.4.1 Unopened, seal-intact units: returnable within 7 days for any reason code; no evidence needed beyond the seal check at pickup.
  5.4.2 Adverse-reaction claims (rash, allergy): do not adjudicate under this policy. Verdict ESCALATE_HUMAN with priority flag SAFETY; such cases go to the Quality & Compliance cell within 4 business hours regardless of order value.

**5.5 WRONG_ITEM and MISSING_PARTS (all categories).**
  5.5.1 Require a photo of what was received (WRONG_ITEM) or of the package contents laid out (MISSING_PARTS).
  5.5.2 Where the warehouse pick-list scan corroborates the claim (SKU mismatch logged at dispatch), auto-approve replacement dispatch (APPROVE_REPLACEMENT) without waiting for reverse pickup.
  5.5.3 Where warehouse records contradict the claim, route to human review — never auto-reject a WRONG_ITEM claim on system records alone.

---

## 6. COD vs. Prepaid Rules

**6.1** Refunds on Prepaid Orders are issued to the original payment instrument. Refunds on COD Orders are issued to (a) the customer's bank account via payout link, or (b) Rivaya store credit at 105% of refund value, at the customer's choice.

**6.2** COD orders carry elevated abuse risk and are subject to the tightened thresholds in Clause 13.3.

**6.3** For COD orders with invoice value ≥ ₹3,000, CHANGE_OF_MIND returns require human review regardless of other factors (ESCALATE_HUMAN citing this clause).

**6.4** Where a COD customer has one or more unpaid/refused deliveries (RTO events) in the trailing 180 days, all return requests from that account route to human review.

---

## 7. Refund Methods, Timelines, and Fees

**7.1** Refund initiation points by verdict:
  (a) APPROVE_INSTANT — refund initiated immediately on verdict; used only where Clause 12.2 conditions are met.
  (b) APPROVE_ON_PICKUP — refund initiated after the field executive's pickup scan confirms item condition.
  (c) APPROVE_ON_QC — refund initiated after warehouse QC confirms condition; mandatory for High-Value Items and all appliances.

**7.2** Refund processing time after initiation: UPI/wallet 1–3 business days; cards 5–7 business days; COD payout links 2–4 business days after bank details are submitted. These are the figures to quote in customer communication.

**7.3** Store-credit refunds are instant on initiation and carry the 105% incentive for COD orders only (Clause 6.1).

**7.4** Fee schedule (deducted from refund): CHANGE_OF_MIND on appliances ₹149 (Clause 5.1.3); SIZE_FIT refund on COD apparel ₹99 (Clause 5.3.2); all other approved reason codes carry no fee. Fees are waived automatically where the customer's lifetime order value exceeds ₹50,000 (loyalty waiver).

**7.5** Partial refunds. Where an item is returnable but a deduction applies (missing free gift per Clause 3.5, missing non-essential accessory), the adjudicator may issue APPROVE_PARTIAL with the deduction itemised. Partial refunds below 50% of invoice value may not be issued automatically; route to human review.

---

## 8. Transit Damage (DAMAGE_TRANSIT)

**8.1** Claims must be raised within 48 hours of the POD scan for fragile-flagged SKUs (Clause 5.2.1) and within the category window otherwise.

**8.2** Required evidence: photo of damaged item; photo of outer packaging showing (or not showing) external damage. Both photos are mandatory.

**8.3** Where the POD includes a delivery photo showing an intact package and the damage claim is raised more than 72 hours after delivery, route to human review with the delivery photo attached.

**8.4** Approved DAMAGE_TRANSIT claims are refunded or replaced at the customer's choice, with no fee, and the case is logged against the logistics partner for the monthly claims reconciliation.

---

## 9. Pickup and Reverse Logistics

**9.1** Reverse pickup is offered at no charge for all approved returns in serviceable pincodes. Non-serviceable pincodes: customer self-ships via any courier; ₹120 flat reimbursement added to the refund on submission of the courier receipt.

**9.2** Three pickup attempts are made over 7 calendar days. After the third failed attempt the return request is closed (verdict CLOSE_PICKUP_FAILED) and the customer must raise a fresh request if still within window.

**9.3** Field executive pickup checklist: item matches SKU; condition matches claim; tags/seals as required by category; packaging where integral (Clause 3.4). A failed checklist converts APPROVE_ON_PICKUP to HOLD_QC_DISPUTE and routes to human review with the executive's photos.

**9.4** For High-Value Items, an OTP shared with the registered email must be given to the pickup executive; pickups without OTP validation must not be completed.

---

## 10. Exchanges

**10.1** Exchanges are supported for Apparel & Soft Furnishings (size/colour) and for like-for-like replacement of defective appliances within window. Exchanges are not supported for Home & Decor or Personal Care; issue refunds instead.

**10.2** Exchange dispatch timing: replacement ships after pickup scan (standard) or simultaneously ("advance exchange") where the account's Return Rate is below 10% and the item is not High-Value.

**10.3** Price differences on exchanges: upward differences are collected via payment link before dispatch; downward differences are refunded per Clause 7.

---

## 11. Sale, Festival, and Promotional Exceptions

**11.1** Items bought during declared festival sale events (the event banner on the order confirmation identifies these) carry the standard category windows, except: (a) CHANGE_OF_MIND windows are halved and rounded down (appliances 3 days, decor 3 days, apparel 7 days); (b) clearance items per Clause 4.1(e) remain non-returnable.

**11.2** Where a coupon applied at order level is invalidated by a partial return (order total drops below the coupon threshold), the coupon value is clawed back proportionally from the refund, itemised in the verdict email.

**11.3** "Buy 2 Get 1" promotional sets: returning any paid unit while retaining the free unit triggers the Clause 3.5 deduction; returning the entire set refunds the full amount.

---

# INTERNAL SOP — Returns Adjudication Desk (Clauses 12–18, not published externally)

## 12. Adjudication Routing: Auto-Lane vs. Human Review

**12.1** Every return request is first assembled into a Case File: order particulars (SKU, category, invoice value, payment mode, Delivery Date, sale-event flag), customer particulars (Return Rate, lifetime order value, RTO events), the mapped reason code (Clause 5.0), and evidence status.

**12.2 Auto-lane (straight-through) conditions.** A verdict may be issued and communicated automatically ONLY if ALL of the following hold:
  (a) the reason code requires no photographic or video evidence for this category (see Clause 12.3);
  (b) the request is unambiguously inside or outside the applicable window (Clause 2), with no holiday-extension edge case pending;
  (c) the item is not a High-Value Item;
  (d) the account's Return Rate is below the applicable threshold in Clause 13;
  (e) no clause in this document explicitly routes the combination to human review;
  (f) the deterministic checks and the retrieved policy clauses agree on a single verdict.

**12.3 Mandatory human review triggers.** The following ALWAYS route to human review (verdict ESCALATE_HUMAN pending adjudicator decision), regardless of all other factors:
  (a) any case whose reason code requires photo or video evidence (all DEFECT, DAMAGE_TRANSIT, WRONG_ITEM, MISSING_PARTS, and NOT_AS_DESCRIBED claims with evidence attached or required) — automated systems must not adjudicate on image content;
  (b) High-Value Items (Clause 1.6), all reason codes;
  (c) safety flags (Clause 5.4.2);
  (d) Return Rate at or above the Clause 13 thresholds;
  (e) COD cases matching Clause 6.3 or Clause 6.4;
  (f) warehouse-record contradictions (Clause 5.5.3);
  (g) repeat claims on the same unit (Clause 5.1.4);
  (h) any case where the reason narrative alleges conduct (delivery executive behaviour, tampering) rather than product condition;
  (i) partial refunds below 50% (Clause 7.5).

**12.4 Customer communication by lane.** Auto-lane cases: the verdict email is sent immediately with clause citations. Human-review cases: a holding email ("request received, under review, expect a decision within 24 business hours") is sent immediately; the verdict email is sent only after the human adjudicator confirms or amends the system-proposed verdict. Under no circumstances may a final verdict be communicated to the customer while the case awaits human review.

**12.5 Admin digest.** Auto-lane verdicts are compiled into a daily FYI digest to the Returns Desk (no action required). Human-review cases generate an immediate case email containing the full Case File, the system-proposed verdict with cited clauses, and one-click approve/amend controls.

## 13. Fraud and Abuse Thresholds

**13.1** Return Rate bands (prepaid accounts): below 30% — normal processing; 30–50% — human review on all requests; above 50% — human review plus store-credit-only refunds (Clause 13.4).

**13.2** New accounts (first order within trailing 60 days) have no meaningful Return Rate; treat as normal unless another trigger applies.

**13.3** COD accounts: the Clause 13.1 bands tighten to 20% and 40% respectively.

**13.4** Store-credit-only restriction: where applied, refunds are issued as store credit at 100% (the Clause 6.1 incentive does not apply); the customer is informed with a neutral wording template (Clause 16.3) that does not use the words "fraud" or "abuse".

**13.5** Serial-returner review: accounts with 5+ returns in 90 days are flagged to the monthly abuse-review meeting irrespective of Return Rate.

**13.6** Evidence-reuse check: where the same image hash appears across claims from different accounts, freeze all matching cases (HOLD_INVESTIGATION) and escalate to Quality & Compliance.

## 14. Warranty vs. Return Boundary

**14.1** Within the return window, a defective appliance is a return (refund/replacement at customer's choice). Outside the window but inside warranty, it is a service claim (repair-first, replacement at service centre's discretion). The verdict email for REDIRECT_WARRANTY must include the service-centre locator link and the customer's warranty reference number.

**14.2** Warranty is void where QC finds physical damage inconsistent with normal use, water ingress in non-rated products, or third-party repair marks; such findings route back to human review before any customer communication.

## 15. Decision Log and Auditability

**15.1** Every verdict — automated or human — is logged with: timestamp, case ID, full Case File snapshot, clauses cited, verdict, lane (auto/human), and, for human verdicts, whether the system proposal was confirmed or amended.

**15.2** Amendment-rate KPI: where human adjudicators amend more than 10% of system proposals in a rolling month, the policy-engine owner must review the divergence log and either fix the logic or amend this document.

**15.3** Clause citations in customer emails use the public numbering (Clauses 1–11 only). Internal clauses (Clauses 12–18) are cited in the decision log and admin digest but never in customer-facing communication.

## 16. Communication Standards

**16.1** Verdict emails must state: the decision, the clause(s) relied upon in plain language, the refund method and timeline per Clause 7.2, and the next physical step (pickup window or no-action).

**16.2** Rejection emails must offer exactly one recourse path: reply-to-reopen with new evidence (where evidence was the gap) or the grievance email (where policy was the gap). Never both.

**16.3** Restricted-refund wording (store-credit-only cases): "Based on your account's recent return activity, refunds on this order are available as Rivaya store credit."

**16.4** Tone: plain language, no legalese in the body; clause numbers in a footer line ("This decision applied: Clause 2.3, Clause 5.3.1").

## 17. Controlled Verdict List

APPROVE_INSTANT · APPROVE_ON_PICKUP · APPROVE_ON_QC · APPROVE_REPLACEMENT · APPROVE_PARTIAL · REJECT_POLICY · REJECT_WINDOW · REJECT_NO_EVIDENCE · REJECT_IDENTITY · REDIRECT_WARRANTY · REDIRECT_MARKETPLACE · HOLD_EVIDENCE · HOLD_QC_DISPUTE · HOLD_INVESTIGATION · ESCALATE_HUMAN · CLOSE_PICKUP_FAILED

**17.1** Each verdict maps to exactly one action bundle (status update + customer email template + admin routing). No free-text verdicts are permitted.

## 18. Precedence and Interpretation

**18.1** Where two clauses conflict, the more specific clause prevails (category-specific over general; reason-code-specific over category-general).

**18.2** Where a case genuinely matches no clause, the verdict is ESCALATE_HUMAN — never a guessed outcome. The gap is logged for the quarterly policy review.

**18.3** This document supersedes all prior versions. Version history: 3.0 (Oct 2025, introduced Clause 13 thresholds), 3.1 (Jan 2026, festival-sale window halving), 3.2 (Apr 2026, photo-evidence cases moved to mandatory human review).

— End of Document —
