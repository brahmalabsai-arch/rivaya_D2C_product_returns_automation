# Returns Adjudicator — Implementation Plan
**Project:** Rivaya Returns Adjudication Engine (n8n + RAG portfolio project)
**Policy basis:** `rivaya_returns_policy.md` (RHL-POL-RET-3.2)
**Demo frontend:** `rivaya_demo_store.html`
**Status legend:** ✅ done · 🔨 next · ⏳ later · 🔔 reminder phase

---

## 1. Architecture (target state)

```
                         ┌─────────────────────────────┐
  Customer               │  Demo storefront (static)   │
  ────────►  Form intake │  rivaya_demo_store.html     │
  ────────►  Chat intake │  (client-held session)      │
                         └──────┬──────────────┬───────┘
                                │ return       │ chat turns
                                │ payload      │ (stage 4b only)
                                ▼              ▼
                    ┌──────────────────────────────────────┐
                    │  n8n                                 │
                    │  Webhook A: /rivaya-returns          │
                    │  Webhook B: /rivaya-returns-chat 🔔  │
                    │  (B = LLM slot-filling brain; emits  │
                    │   the SAME payload into A's flow)    │
                    └──────┬───────────────────────────────┘
                           │ POST payload
                           ▼
                    ┌──────────────────────────────────────┐
                    │  Adjudication service (FastAPI)      │
                    │  deterministic checks + RAG over     │
                    │  policy clauses → proposed verdict   │
                    └──────┬───────────────────────────────┘
                           │ {verdict, lane, clauses, draft}
                           ▼
        n8n branches by lane:
        AUTO  → verdict email to customer + row in FYI digest
        HUMAN → holding email to customer + case email to admin
                (admin approves/amends → final email)
        ALL   → append to decision log (Sheet/CSV)
```

**Core invariant (do not violate):** both intake channels converge on one
payload schema (§3.1). Retrieval queries are constructed server-side from
structured payload fields — never from free-form LLM text. The LLM
perceives; the deterministic layer decides; every verdict cites clauses.

---

## 2. Stage plan

| # | Stage | Where | Status |
|---|-------|-------|--------|
| 1 | Synthetic policy doc (RHL-POL-RET-3.2) | done in chat | ✅ |
| 2 | Demo storefront: login, 6 engineered orders, return form, route preview, webhook + simulation mode | done in chat | ✅ |
| 2.5 | Chat intake UI on the storefront: client-held session, scripted sim bot, attach control, chat-endpoint setting | done in chat | ✅ |
| 3 | Adjudication service (RAG + rules) | Claude Code | ✅ |
| 4 | n8n workflow: Webhook A → service → lane branching → emails → decision log | n8n | ✅ |
| 4b | **🔔 REMINDER — the real LLM chat brain.** Build ONLY after stage 4's main path works end-to-end. Webhook B (or n8n Chat Trigger) + LLM node with slot-filling prompt + structured output honoring the §3.2 contract; on `complete`, feed the assembled payload into the stage-4 flow. Until then the storefront's scripted sim bot stands in. | n8n | 🔔 |
| 5 | Polish: README with architecture diagram + ROI math, demo video (6 scenarios + chat), decision-log screenshots, eval numbers | repo | 🔨 |

Rationale for 4b's position: the chat brain is an *intake* enhancement.
It needs a working adjudication pipeline to hand off to; building it
earlier means testing an LLM against a stub. The storefront already
falls back to the scripted bot when Webhook B is unreachable, so
nothing blocks demos in the meantime.

---

## 3. Contracts (source of truth)

### 3.1 Return payload (storefront → Webhook A) — BOTH channels emit this
```json
{
  "requestId": "RET-XXXXXXXX",
  "submittedAt": "ISO-8601",
  "customer": { "email": "user@example.com" },
  "order": {
    "orderId": "ORD-1044", "sku": "RV-KA-MIX-750",
    "itemName": "750W Mixer Grinder, 3 jars",
    "category": "appliance | decor | apparel | personal_care",
    "invoiceValue": 3299, "paymentMode": "PREPAID | COD",
    "deliveryDate": "YYYY-MM-DD", "daysSinceDelivery": 6,
    "flags": { "clearance": false, "festivalSale": false, "fragile": false, "highValue": false }
  },
  "return": {
    "reasonCode": "DEFECT | DAMAGE_TRANSIT | WRONG_ITEM | MISSING_PARTS | NOT_AS_DESCRIBED | SIZE_FIT | CHANGE_OF_MIND | LATE_DELIVERY_REFUSED",
    "description": "free text",
    "photoAttached": true,
    "photo": { "fileName": "", "mimeType": "", "base64": "" }
  },
  "meta": { "source": "rivaya-demo-store", "intakeChannel": "form | chat", "policyVersion": "RHL-POL-RET-3.2" }
}
```

### 3.2 Chat turn (storefront → Webhook B, stage 4b) 🔔
Request:
```json
{ "sessionId": "CS-...", "customerEmail": "...", "message": "user text",
  "history": [{ "role": "user|bot", "text": "..." }],
  "slots": { "orderId": null, "reasonCode": null, "description": null },
  "photoAttached": false,
  "catalog": [{ "orderId": "...", "name": "...", "category": "...", "price": 0,
                "paymentMode": "...", "daysSinceDelivery": 0, "flags": {} }] }
```
Response: `{ "reply": "bot text", "slots": { ...updated... }, "complete": false }`
When `complete: true`, the client assembles the §3.1 payload from slots
and submits it to Webhook A. The LLM must only ever fill `reasonCode`
from the controlled list; anything unmappable stays null and the bot
asks again. The frontend already implements this client side.

### 3.3 Adjudication response (service → n8n)
```json
{ "requestId": "...", "verdict": "ONE OF THE 16 CONTROLLED VERDICTS (policy Clause 17)",
  "lane": "AUTO | HUMAN_REVIEW",
  "citedClauses": ["Clause 5.1.1", "Clause 12.3(a)"],
  "reasoning": "one paragraph, plain language",
  "customerEmailDraft": { "subject": "", "body": "" },
  "deductions": [{ "label": "", "amount": 0 }],
  "confidence": "CLEAR | AMBIGUOUS" }
```

---

## 4. Stage 3 build spec (Claude Code) ✅

Suggested layout:
```
adjudicator/
  app.py              # FastAPI: POST /adjudicate, GET /health
  rules.py            # deterministic checks (run BEFORE retrieval)
  retrieval.py        # clause chunking + vector store + query builder
  verdicts.py         # controlled verdict enum + lane mapping
  emailer.py          # draft generation (LLM) from verdict + clauses
  policy/rivaya_returns_policy.md
  tests/test_fixtures.py
  fixtures/*.json     # captured from the storefront payload viewer
```

Key decisions already made — implement, don't re-litigate:
1. **Chunk by clause, not by tokens.** Split on the `**N.N**` /
   `N.N.N` markers; each chunk = one clause with its section heading
   prepended. Store clause number as metadata; citations come from
   metadata, never from generation.
2. **Deterministic pre-checks in `rules.py` run first** (hard gates,
   in order): identity (Clause 3.2) → marketplace (3.3) →
   non-returnable (4.1) → window incl. festival halving (2, 11.1) →
   mandatory human-review triggers (12.3, incl. photo-evidence rule
   12.3(a), high-value 12.3(b), COD 6.3/6.4). Any hit short-circuits
   with the verdict/lane; retrieval then only fetches the cited
   clauses to ground the email draft.
3. **Retrieval query is built from structured fields** — template like
   `"{category} {reasonCode} return, {paymentMode}, day {daysSinceDelivery},
   flags: {...}"` plus the description text as a secondary query.
   Top-k ≈ 6, then keep clauses that mention the reason code, the
   category, or general sections. Hybrid (BM25 + embeddings) is a
   nice-to-have, not required for v1.
4. **LLM roles in the service are narrow:** (a) sanity-map the free-text
   description against the chosen reasonCode (mismatch → AMBIGUOUS →
   human lane); (b) draft the customer email from verdict + cited
   clause texts. The LLM never selects the verdict.
5. **Confidence rule:** if deterministic checks and retrieved clauses
   point to one verdict → CLEAR; any conflict, gap (policy Clause 18.2),
   or reason/description mismatch → AMBIGUOUS → HUMAN_REVIEW.

Acceptance criteria (stage 3 is done when):
- [x] The six storefront fixtures return exactly:
      ORD-1043+SIZE_FIT → APPROVE_ON_PICKUP/AUTO ·
      ORD-1044+DEFECT+photo → ESCALATE_HUMAN/HUMAN_REVIEW ·
      ORD-1045 (day 20) → REJECT_WINDOW/AUTO ·
      ORD-1046 (clearance, non-exempt reason) → REJECT_POLICY/AUTO ·
      ORD-1047+CHANGE_OF_MIND (COD ₹3,450) → ESCALATE_HUMAN/HUMAN_REVIEW ·
      ORD-1048+CHANGE_OF_MIND (festival, day 4) → REJECT_WINDOW/AUTO
- [x] Every response cites ≥1 clause; cited clause numbers exist in the doc
- [x] DEFECT without photo → HOLD_EVIDENCE (Clause 5.1.1)
- [x] A nonsense case (no matching clause) → ESCALATE_HUMAN, never a guess
- [x] Decision log line written per request (JSONL is fine for v1)

Built at `adjudicator/` — see `adjudicator/README.md`. 59 tests pass; the
service runs with or without an `ANTHROPIC_API_KEY` (the two LLM roles fall
back to a keyword matcher and templated drafts). Two ordering decisions are
documented in `rules.py`: safety narratives (5.4.2) jump ahead of the window
check under Clause 18.1, and HOLD_EVIDENCE sits on the AUTO lane because
Clause 5.1.1 prescribes a templated evidence-request email and 12.3(a) has no
image to adjudicate yet.

## 5. Stage 4 build spec (n8n) ✅
- Webhook A (POST, respond immediately with 200 + requestId) →
  HTTP Request node → adjudication service → Switch on `lane`.
- AUTO: send `customerEmailDraft` → append to daily digest list.
- HUMAN_REVIEW: holding email to customer → case email to admin with
  full case file + proposed verdict + two links (n8n Wait-for-webhook
  approve/amend) → on approve, send final email.
- All paths: append decision-log row (Sheet or the service's JSONL).
- CORS: enable allowed origin for the storefront host on both webhooks,
  or serve the HTML from the same host. (Known gotcha — see README.)

Built at `n8n/` — two importable workflows plus a step-by-step setup guide
in `n8n/README.md`. Notes on what changed while building it:

- The digest is its own scheduled workflow (`rivaya-returns-daily-digest`)
  rather than an append-to-list inside the main flow. It reads the service's
  own log, so there is one source of truth and no Google credentials needed.
- The decision-log row is written by the service, not by n8n. n8n calls
  `POST /decisions/{caseId}/outcome` after a human decides, which appends a
  second row — the engine's proposal is never overwritten.
- Stage 3 gained three endpoints that stage 4 needs: `POST /draft` (verdict
  email for the outcome a human picked — n8n must not write customer copy),
  `POST /decisions/{caseId}/outcome` (Clause 15.2 audit trail), and
  `GET /metrics` (straight-through and amendment rates for stage 5).
- The engine now returns `humanReview` on escalated cases: the Clause 12.5
  system-proposed verdict plus the one-click options. It deliberately proposes
  **nothing** for evidence, safety, conduct and policy-gap escalations —
  proposing on a photo case would mean adjudicating image content, which
  12.3(a) forbids.

## 6. Stage 5 checklist ⏳
README (architecture, invariant, ROI: ~5 min/case human baseline vs
~20 s automated; 70–80% straight-through target; amendment-rate KPI per
policy Clause 15.2) · 2-min demo video: three form scenarios + one full
chat scenario + admin approval · decision-log screenshot · limitations
section (sim bot vs 4b, synthetic data, no real payments).
