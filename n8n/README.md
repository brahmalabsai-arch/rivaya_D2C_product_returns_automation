# Stage 4 — n8n workflows, and how to stand them up

Two importable workflows:

| File | What it does |
|---|---|
| `rivaya-returns-adjudication.json` | Webhook A → adjudication service → lane branch → emails → human approve/amend loop |
| `rivaya-returns-daily-digest.json` | Daily FYI digest of auto-lane verdicts + the Clause 15.2 amendment-rate control |

Built against **n8n 1.6x** (Docker or `npx n8n`). Node types used: Webhook, Respond to
Webhook, Set, HTTP Request, Code, If, Send Email, Wait, Schedule Trigger, NoOp.

```
Webhook A ─► Config ─► Ack 200 ─► Adjudicate ─► Build case ─► Lane?
                                                                │
                        AUTO ◄──────────────────────────────────┤
                         └─► Send verdict email ─► (logged by the service)
                                                                │
                HUMAN_REVIEW ◄──────────────────────────────────┘
                 └─► Holding email ─► Admin case email ─► ⏸ Wait
                        ─► Read decision ─► Record outcome ─► Draft final ─► Send verdict
```

---

## Step 1 — Start the adjudication service so n8n can reach it

**Bind to `0.0.0.0`, not the default localhost** — otherwise a containerised n8n cannot
connect, and you will get `ECONNREFUSED` on the Adjudicate node.

```bash
.venv/Scripts/python -m uvicorn adjudicator.app:app --host 0.0.0.0 --port 8000
```

Confirm it answers:

```bash
curl http://localhost:8000/health
```

Note which URL **n8n** should use — they are not the same thing:

| How you run n8n | URL for the `Config` node |
|---|---|
| Docker / Docker Desktop | `http://host.docker.internal:8000` |
| `npx n8n` on the same machine | `http://localhost:8000` |
| n8n on another host | `http://<your-machine-ip>:8000` (open the firewall) |

## Step 2 — Import both workflows

n8n → **Workflows** → **Import from File** → pick `rivaya-returns-adjudication.json`,
then repeat for `rivaya-returns-daily-digest.json`. The sticky notes on the canvas
explain each section; you don't need this file open while you work.

## Step 3 — Set the three values in `Config`

Open the **`Config`** node in each workflow. It is the only place any of this is
configured — every other node reads from it.

| Field | Set it to |
|---|---|
| `adjudicatorUrl` | The URL from step 1 (no trailing slash) |
| `adminEmail` / `deskEmail` | Where the case email and digest go — **your own inbox** for the demo |
| `fromEmail` | The address your SMTP account is allowed to send as |

## Step 4 — Connect SMTP

Click any **Send Email** node → **Credential to connect with** → **Create new**. For a
Gmail account use host `smtp.gmail.com`, port `465`, SSL on, and an **App Password**
(not your normal password — Google rejects that). Create the credential once; assign
the same one to all four email nodes.

*Demoing without a mail server?* Point SMTP at [Mailtrap](https://mailtrap.io) or
[Mailpit](https://github.com/axllent/mailpit) — every email lands in a fake inbox you
can screenshot, which is what you want for stage 5 anyway.

## Step 5 — Activate and copy the webhook URL

Toggle the adjudication workflow to **Active**, then open **Webhook A** and copy the
**Production URL** — something like:

```
http://localhost:5678/webhook/rivaya-returns
```

> **Activation is not optional.** The approve/amend links come from the Wait node's
> resume URL, and that only works in a production (active) execution. In test mode the
> links point at a test URL that dies when you navigate away.

## Step 6 — Point the storefront at it

Open `rivaya_demo_store.html`, sign in with an email you can actually read, expand
**Demo settings**, and paste the production URL into **n8n webhook URL**. Leave the
chat endpoint blank — that's stage 4b, and the scripted bot stands in until then.

## Step 7 — Walk the six scenarios

Each storefront order exercises a different policy path. Tick the **Demo lens**
checkbox to see which one before you submit.

| Order | Reason to pick | Expected |
|---|---|---|
| ORD-1043 Kurta Set | Size or fit isn't right | `APPROVE_ON_PICKUP` · AUTO · verdict email |
| ORD-1044 Mixer Grinder | Defect **+ attach a photo** | `ESCALATE_HUMAN` · holding email + case email |
| ORD-1044 Mixer Grinder | Defect **without** a photo | `HOLD_EVIDENCE` · AUTO · "send us one photo" |
| ORD-1045 Ceramic Vase | Changed my mind | `REJECT_WINDOW` · AUTO (day 20 vs 7) |
| ORD-1046 Oil Trio | Changed my mind | `REJECT_POLICY` · AUTO (clearance badge) |
| ORD-1047 Bedsheet Set | Changed my mind | `ESCALATE_HUMAN` · COD ≥ ₹3,000 |
| ORD-1048 Brass Lamp | Changed my mind | `REJECT_WINDOW` · AUTO (festival halves 7 → 3) |

Watch **Executions** in n8n as each one runs.

## Step 8 — Close a human-review case

Submit ORD-1047, then open the case email in your admin inbox. You get the full Case
File, the system proposal with its cited clauses, and one-click controls:

- **Approve — APPROVE_ON_PICKUP** — the engine's proposal (green)
- **Amend → APPROVE_PARTIAL** / **Amend → REJECT_POLICY** (blue)

Click one. The paused execution resumes, records the outcome against the case, asks the
service for copy matching *that* verdict, and emails the customer.

ORD-1044-with-photo looks different on purpose: **there is no Approve button**, only
amend options. Clause 12.3(a) forbids an automated system from adjudicating on image
content, so the engine refuses to propose an outcome it would have to guess. That
contrast is worth showing on camera.

Confirm it was recorded:

```bash
curl "http://localhost:8000/decisions?limit=3"
```

You'll see two rows for the case — the engine's original proposal *and* the human
outcome. The log is append-only, so the divergence stays auditable (Clause 15.1).

## Step 9 — The digest workflow

Activate `Rivaya Returns — Daily Digest`. It runs at 09:00; hit **Execute Workflow** to
see it now. It emails the day's auto-lane verdicts plus the rolling numbers, and turns
red if adjudicators amended more than 10% of proposals (the Clause 15.2 control).

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ECONNREFUSED` on Adjudicate | Service bound to localhost only, or wrong host in `Config`. Restart uvicorn with `--host 0.0.0.0`; use `host.docker.internal` from Docker. |
| Storefront shows a CORS/network error | Webhook A's `Allowed Origins (CORS)` must be `*`. It ships that way — check it survived import. |
| Storefront hangs on submit | You are on the **Test** URL and haven't pressed *Execute workflow*, or the workflow isn't Active. |
| Approve/amend links 404 | Workflow wasn't Active when the case ran, or `WEBHOOK_URL` is wrong behind a tunnel. Re-run the case after activating. |
| `Read adjudicator decision` throws "resume request carried no ?outcome=" | Your n8n's Wait node isn't surfacing the query string. Open the node, set **Resume** → *On Webhook Call*, and check the error message — it prints the keys it actually received. |
| Emails silently don't arrive | SMTP credential not assigned to *that* node — each email node needs it. Check the Executions view for the red node. |
| `422` from `/adjudicate` | The payload isn't §3.1-shaped. Copy it from the storefront's "Show the payload" panel and post it with curl to see the detail. |

---

## Preparing for stage 5

Stage 5 is README + demo video + numbers. Capture these **while** you walk step 7,
because re-staging them later is tedious:

**Screenshots**
1. The n8n canvas, both lanes visible.
2. An Executions list showing green runs across several scenarios.
3. The admin case email with its controls — one from ORD-1047 (has Approve), one from
   ORD-1044 (deliberately doesn't).
4. Two or three customer emails: an approval, a rejection with its clause footer, and
   the evidence-request hold.
5. `curl http://localhost:8000/decisions?limit=5 | jq` — the append-only log.

**Numbers** — run all seven scenarios, close two human cases (confirm one, amend one),
then grab the real figures instead of estimating:

```bash
curl "http://localhost:8000/metrics?windowDays=30"
```

That gives you the straight-through rate, the amendment rate against the Clause 15.2
ceiling, the verdict mix, and mean engine latency. The ROI line writes itself: compare
`latency.avgMs` against `humanBaselineSeconds` (300 s of adjudicator time per case).

**Video, ~2 minutes**: three form scenarios (auto-approve → auto-reject → escalation),
one chat scenario, then the admin approving a case and the customer email landing.

**Limitations to state plainly** in the README — the scripted chat bot stands in for the
stage-4b LLM brain, the data is synthetic, no payments are touched, and the retriever is
BM25 rather than embeddings.

Stage 4b (the real LLM chat brain on Webhook B) is deliberately still open — it needs
this pipeline working first, which it now is.
