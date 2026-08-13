# Rivaya Returns — Autonomous D2C Returns Processing

Rivaya Returns is an end-to-end automation pipeline designed to process e-commerce returns for a fictional direct-to-consumer (D2C) brand. It replaces manual customer support workflows with a highly scalable, rule-based engine that strictly adheres to a complex business policy.

This project demonstrates how to orchestrate a **FastAPI backend** and an **n8n workflow engine** to handle autonomous decision-making, while keeping a secure **Human-in-the-Loop (HITL)** safety net for edge cases.

---

## 📖 Documentation
- [Problem Statement](problem_statement.md): Why manual return adjudication is a massive bottleneck for D2C brands.
- [System Architecture](architecture.md): A detailed breakdown of the FastAPI and n8n orchestration flow.

---

## 🚀 The Solution

This system reduces manual returns processing from ~5 minutes per ticket to ~200 milliseconds. 
- **Auto-Lane:** Standard cases (clear approvals or clear policy rejections) are resolved instantly using deterministic business logic, and the customer is notified automatically.
- **Human Review Lane:** Ambiguous cases (or cases requiring photo inspection) are escalated to a human adjudicator via a rich HTML email. The adjudicator can approve or amend the system's proposed verdict with a single click, instantly resuming the paused backend workflow.

### Key Features
* **Rule-Based Engine:** Uses deterministic business logic for strict policies (e.g., date windows, COD value, clearance item checks).
* **Semantic Policy Retrieval (BM25):** Implements a custom lexical BM25 retriever to dynamically chunk and search the `rivaya_returns_policy.md`, automatically appending relevant clauses to admin emails to ground human decision-making.
* **Append-Only Audit Log:** Tracks the engine's original proposed verdict alongside the human adjudicator's final decision.
* **Automated QA & Metrics:** Monitors the "Amendment Rate" (Clause 15.2). If human agents overwrite the engine's proposal more than 10% of the time, the daily digest flags the policy for review.

---

## ⚙️ Quick Start

### 1. Stand up the Adjudicator Service
Navigate to the `adjudicator` directory, install requirements, and run the FastAPI server:
```bash
cd adjudicator
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 2. Stand up the n8n Workflow
1. Import `n8n/rivaya-returns-combined.json` into your n8n instance.
2. Configure the **Config** and **Digest Config** nodes with your FastAPI URL and email addresses.
3. Configure your SMTP credentials in the Email nodes.
4. **Activate** the workflow to generate the production Webhook URL.

### 3. Run a Test
1. Open `rivaya_demo_store.html` in your browser.
2. Enter your n8n webhook URL in the "Demo settings" panel.
3. Submit a return request and watch the n8n execution log branch dynamically based on the rules!

---

## 📂 Repository Structure

```text
├── adjudicator/            # FastAPI microservice for policy evaluation
│   ├── app.py              # API routes
│   ├── rules.py            # Hardcoded business logic
│   ├── retrieval.py        # BM25 policy chunking and search
│   └── ...
├── n8n/                    # n8n Orchestration workflows
│   ├── rivaya-returns-combined.json   # Main exportable workflow
│   └── README.md           # Detailed n8n setup instructions
├── architecture.md         # Detailed system architecture document
├── problem_statement.md    # The business context and pain points
├── rivaya_demo_store.html  # Mock e-commerce storefront UI
└── rivaya_returns_policy.md # The fictional company policy document
```

---

## 📊 Measuring Success (ROI)

The API exposes a `/metrics` endpoint to monitor performance:
```bash
curl "http://localhost:8000/metrics?windowDays=30"
```
This tracks the Straight-Through Processing (STP) rate, median engine latency, and the critical Amendment Rate to guarantee the automated rules remain aligned with human expectations.

---

## 🔮 Future Scope

**LLM Integration for Perception & Communication**
While the current engine is purely deterministic and rule-based, the architecture is designed to support Large Language Models (LLMs) to handle qualitative perception tasks that rules cannot easily solve. Future iterations will integrate an LLM (e.g., Anthropic) for:
* **Perception Alignment:** Using the LLM to read the customer's free-text narrative and flag it if it contradicts the structured reason code they selected.
* **Customer Communication:** Using the LLM to draft highly personalized, empathetic customer emails based on the context of the return, rather than relying on static templates.
* **Image Analysis:** Using a vision-capable LLM to inspect attached evidence photos and intelligently determine if a defect claim is legitimate, drastically reducing human review volume for defect cases.
