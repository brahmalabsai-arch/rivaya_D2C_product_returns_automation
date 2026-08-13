# Rivaya Returns Adjudicator — Stage 3

Deterministic rules + clause-level retrieval over **RHL-POL-RET-3.2**, exposed as a
FastAPI service. This is the box in the middle of the architecture diagram: n8n's
Webhook A posts the §3.1 return payload here and gets back a verdict, a lane,
cited clauses and a drafted customer email.

**The invariant:** the LLM perceives, the deterministic layer decides, every
verdict cites clauses. Retrieval queries are built server-side from structured
payload fields — never from free-form model text — and citations are resolved out
of the policy document rather than generated, so a cited clause number always
exists.

## Run it

```bash
.venv/Scripts/python -m uvicorn adjudicator.app:app --reload --port 8000
```

```bash
.venv/Scripts/python -m pytest adjudicator/tests -q
```

The service is fully functional **without** an API key. Setting `ANTHROPIC_API_KEY`
switches the two narrow LLM roles on; nothing else changes.

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Enables the LLM roles (perception + email polish) |
| `RIVAYA_USE_LLM` | `1` | Set `0` to force the deterministic path even with a key |
| `RIVAYA_LLM_MODEL` | `claude-opus-5` | Model for both LLM roles |
| `RIVAYA_POLICY_PATH` | `policy/rivaya_returns_policy.md` | Policy document to index |
| `RIVAYA_DECISION_LOG` | `logs/decisions.jsonl` | Decision log (Clause 15.1) |
| `RIVAYA_TOP_K` | `6` | Supporting clauses retrieved per case |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/adjudicate` | The §3.1 payload in, the §3.3 response out |
| `POST` | `/draft` | Verdict email for an outcome a human just picked (stage 4) |
| `POST` | `/decisions/{caseId}/outcome` | Record a confirm/amend (Clauses 15.1, 15.2) |
| `GET` | `/metrics?windowDays=30` | Straight-through rate, amendment rate, verdict mix |
| `GET` | `/health` | Liveness, policy version, clause count, LLM state |
| `GET` | `/clauses/{id}` | Clause lookup (`5.1.1`, `12.3`, `17`) |
| `GET` | `/decisions?limit=20` | Tail of the decision log |

```bash
curl -X POST localhost:8000/adjudicate -H 'Content-Type: application/json' \
     -d @adjudicator/fixtures/ord-1044-defect-photo.json
```

## How a case is decided

```
payload ─► perception ─► deterministic gates ─► grounding ─► drafting ─► log
           (llm.py)      (rules.py)             (retrieval)  (emailer)  (JSONL)
           reason vs.    first hit wins;        resolve      templated  Clause
           description   picks the verdict      citations,   + optional 15.1
                                                top-k        LLM polish
```

Hard gates, in order — the first hit short-circuits:

| # | Gate | Clauses |
|---|---|---|
| 0 | Adjudicable at all (unknown reason code / category) | 5.0, 2, 18.2 |
| 1 | Identity — request from the registered account | 3.2 |
| 2 | Marketplace order | 3.3 |
| 3 | Non-returnable item | 4.1, 4.2 |
| 4 | Safety / conduct narrative | 5.4.2, 12.3(h) |
| 5 | Return window, festival halving, warranty boundary, 48h fragile rule | 2, 11.1, 5.1.2, 5.2.1 |
| 6 | Evidence present | 5.1.1, 5.5.1, 8.2 |
| 7 | Mandatory human review | 12.3, 6.3, 6.4, 13 |
| 8 | Auto lane, refund initiation point, fees | 12.2, 7.1, 7.4 |

Two ordering decisions are deliberate and documented in `rules.py`:

- **Safety narratives jump ahead of the window check.** Clause 5.4.2 removes
  adverse-reaction claims from this policy entirely, and Clause 18.1 makes the
  more specific clause prevail, so the window arithmetic is not the right first
  question. Conduct allegations (12.3(h)) ride along for the same reason.
- **`HOLD_EVIDENCE` sits on the AUTO lane.** Clause 5.1.1 prescribes a single
  templated evidence-request email and a 72-hour hold. Clause 12.3(a)'s rationale
  — "automated systems must not adjudicate on image content" — does not bite when
  there is no image yet. The human sees the case when the photo arrives.

## Where the LLM is, and is not

| Role | Implementation | Fallback with no API key |
|---|---|---|
| Does the description match the reason code? | Structured output (`messages.parse`) | Keyword matcher |
| Draft the customer email | Rewrites a complete templated draft | The template itself |

A mismatch never picks an outcome — it downgrades confidence to `AMBIGUOUS` and
sends the case to a person (Clause 18.2), because the reason code drives both the
window arithmetic and the evidence rules.

## Retrieval

Chunked by **clause, not by token count**: split on the `**N.N**` / `N.N.N`
markers, section heading prepended, clause number in metadata. 101 clauses
indexed, 84 of them rankable (section-level stubs like "Clause 2" stay citable
but never rank). Lettered sub-items are captured whether they sit on their own
line (Clause 4.1) or inline (Clause 5.1.1, 11.1), and cross-references such as
Clause 11.1's pointer at "Clause 4.1(e)" are excluded from 11.1's own letters —
so `Clause 11.1(a)` validates and `Clause 11.1(e)` does not.

Ranking is BM25: deterministic, dependency-free and auditable, which matters more
here than recall. `Retriever` is the seam for adding embeddings later; nothing
above it would change.

## Contract notes for stage 4

- `lane` is `AUTO` or `HUMAN_REVIEW` — the only Switch key n8n needs.
- `customerEmailDraft` is send-ready. For `HUMAN_REVIEW` it is a **holding**
  email (Clause 12.4): no final verdict reaches the customer before a person
  confirms or amends the proposal.
- `caseFile` is the Clause 12.1 snapshot for the admin case email.
- `humanReview` (present only on `HUMAN_REVIEW` cases) carries the Clause 12.5
  system-proposed verdict and the one-click options for the admin email.
  `proposedFinalVerdict` is deliberately `null` for evidence, safety, conduct
  and policy-gap escalations — proposing an outcome for a photo case would mean
  adjudicating image content, which Clause 12.3(a) forbids. The admin picks
  from `options` with no default in those cases.
- `citedClauses` may include internal clauses; the customer email footer is
  already filtered to public Clauses 1–11 (Clause 15.3).
- The decision log writes `humanOutcome: null` — n8n's approve/amend step fills
  it in, which is what the Clause 15.2 amendment-rate KPI counts.
- Photo bytes are scrubbed from the log and replaced with a byte count.

## Test coverage

59 tests: the six storefront fixtures, citation validity, evidence holds, the
nonsense case, decision-log shape, every rule gate (identity, marketplace,
clearance, hygiene seal, safety, conduct, festival halving, warranty boundary,
48-hour fragile rule, high value, return-rate bands, RTO history, fees and the
loyalty waiver), chunking and retrieval behaviour, and the HTTP contract.
