# System Architecture

The Rivaya Returns automation pipeline is built using a microservices approach, decoupling the orchestration layer from the core business logic. The system currently relies on a highly deterministic, rule-based engine to process returns.

## Core Components

The architecture consists of three primary components working in tandem:

### 1. The Storefront (Client Layer)
* **File:** `rivaya_demo_store.html`
* **Role:** A mock D2C e-commerce frontend. 
* **Function:** Customers use this UI to submit return requests (selecting the item, reason, and attaching optional photo evidence). It constructs a JSON payload and POSTs it directly to the n8n webhook.

### 2. The Adjudicator Service (Logic Layer)
* **Directory:** `/adjudicator`
* **Tech Stack:** Python, FastAPI.
* **Role:** The "brain" of the operation.
* **Function:** It receives the structured payload from n8n and evaluates it against hardcoded business rules (e.g., checking delivery windows, item categories, COD value, and evidence requirements). It then determines the appropriate processing "lane" (`AUTO` or `HUMAN_REVIEW`), proposes a verdict, and logs the decision. It also exposes a `/metrics` endpoint to monitor system performance.

### 3. The Orchestrator (Integration Layer)
* **Directory:** `/n8n`
* **Tech Stack:** n8n (Workflow Automation).
* **Role:** The central nervous system.
* **Function:** It coordinates the flow of data between the storefront, the Adjudicator API, and the human support agents.

## The Adjudication Flow

When a return is submitted, n8n orchestrates the following flow:

1. **Intake & Acknowledgment:** n8n receives the webhook from the storefront and immediately returns an HTTP 200 OK so the customer's UI doesn't hang.
2. **API Call:** n8n forwards the payload to the FastAPI Adjudicator service.
3. **Lane Branching:** The Adjudicator responds with a lane assignment, and n8n routes the workflow accordingly using an `If` node.
   
   * **AUTO Lane:** For standard approvals or clear-cut rejections (e.g., out of policy window), n8n immediately fires off a personalized email to the customer and closes the case.
   
   * **HUMAN_REVIEW Lane (Human-in-the-Loop):** 
     * For edge cases, high-value items, or requests requiring visual inspection of a photo, n8n sends a holding email to the customer.
     * Simultaneously, it sends a rich HTML "Case File" email to an admin's inbox.
     * **The Wait Node:** The n8n execution then *pauses indefinitely* using a Wait node.
     * **One-Click Resolution:** The admin email contains "Approve" and "Amend" buttons embedded with secure webhook URLs. When the admin clicks a button, the HTTP GET request resumes the paused n8n execution, records the human's verdict, and emails the final decision to the customer.

## Audit & Compliance

Every decision made by the system is tracked in an append-only JSON log within the FastAPI service. If a case goes to Human Review, the log captures both the engine's original proposed verdict and the human's final recorded outcome, allowing the business to audit the "Amendment Rate" and ensure the automated rules remain aligned with human expectations.
