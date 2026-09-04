# RecoverAI — Autonomous AI Revenue Recovery Agent

RecoverAI is an AI-powered revenue recovery system built for **Track 3: AI Revenue Recovery**.

It analyzes failed payments, recommends a recovery action using an LLM, validates that recommendation through deterministic financial guardrails, executes a bounded recovery step, and verifies the final outcome through signed Razorpay webhooks.

> **Core idea:** The LLM recommends, the policy decides, execution acts, and the signed webhook verifies.

---

## Problem Statement

Failed online payments can happen for many reasons such as:

- Bank decline
- Network error
- Timeout
- Insufficient funds
- Expired payment
- Abandoned checkout
- Unknown failure

Using the same recovery strategy for every failed payment is unsafe and inefficient. For example, a temporary timeout may be suitable for retry, while a bank-declined payment may be better handled using a payment link.

RecoverAI chooses a safer recovery strategy based on transaction context.

---

## Solution

RecoverAI follows this workflow:

**Observe → LLM Reason → Policy Guard → Persist Decision → Act → Verify → Update State**

### Observe
The system reads transaction context such as transaction amount, failure reason, retry count, customer opt-out status, previous recovery state, and whether the transaction is synthetic or live Test Mode data.

### LLM Reasoning
The LLM recommends one of the following actions:

- `retry`
- `payment_link`
- `payment_link_later`
- `human_review`
- `stop`

### Deterministic Policy Guard
The LLM does **not** directly control financial execution.

The policy layer validates or overrides the recommendation using deterministic rules such as retry limits, failure reason, transaction value, customer opt-out, already recovered state, human-review requirements, and synthetic transaction protection.

### Persist Approved Decision
The final guarded decision is stored in the database and reused during execution so that reasoning and execution remain consistent.

### Execute Recovery
RecoverAI can create a Razorpay Test Payment Link, schedule a bounded retry, delay recovery, escalate to human review, or stop unsafe recovery.

### Verify Outcome
A transaction is marked recovered only after a **signed Razorpay webhook** is successfully verified.

---

## Verified Razorpay Test Mode Recovery

RecoverAI includes a verified Test Mode recovery for transaction **TXN007**:

- Original amount: **₹2,499**
- Failure reason: **bank_decline**
- LLM recommendation: **retry**
- Policy override: **payment_link**
- Razorpay Test Payment Link created
- Customer completed payment in Test Mode
- Signed webhook verified
- Final status: **recovered**
- Verified Test Mode recovered amount: **₹2,499**

This demonstrates that the LLM is advisory while deterministic policy remains the final financial authority.

---

## Synthetic Evaluation

RecoverAI also includes a separate deterministic synthetic evaluation of **100 failed transactions**.

Example evaluation result:

- Total synthetic revenue at risk: **~₹5.77 lakh**
- Simulated recovered amount: **~₹1.44 lakh**
- Simulated recovery rate: **~24.99%**
- Simulated recovered transactions: **29 / 100**

> These values are **synthetic / simulated evaluation metrics** and are completely separate from the verified Razorpay Test Mode recovery.

Synthetic transactions never trigger real Razorpay recovery actions.

---

## Key Features

- AI-based recovery recommendation
- Deterministic financial policy guardrails
- Persistent approved decisions
- Razorpay Test Payment Link integration
- Signed webhook verification
- PostgreSQL production persistence
- SQLite local fallback
- Bounded retry workflow
- Human-review escalation
- Customer opt-out protection
- Synthetic batch evaluation
- Recovery dashboard
- Audit-friendly recovery state

---

## Tech Stack

### Frontend
- React
- Vite
- Axios
- Recharts
- Lucide Icons

### Backend
- Python
- Flask
- Flask-CORS
- Gunicorn

### AI
- OpenRouter API
- LLM-based recovery reasoning
- Deterministic fallback logic

### Database
- PostgreSQL — production
- SQLite — local development and isolated testing
- psycopg2

### Payments
- Razorpay Test Mode
- Payment Links
- Signed Webhooks

### Deployment
- Render — Flask backend
- Render PostgreSQL

---

## Architecture

```text
Failed Payment
      ↓
OBSERVE
      ↓
LLM REASON
      ↓
POLICY GUARD
      ↓
PERSIST APPROVED DECISION
      ↓
ACT
      ↓
VERIFY SIGNED WEBHOOK
      ↓
UPDATE RECOVERY STATE
```

---

## Production Persistence

The project originally used SQLite during local development.

After deployment, production state was migrated to PostgreSQL so that recovery decisions and webhook outcomes survive service restarts and redeployments.

The application automatically uses:

```text
DATABASE_URL present  → PostgreSQL
DATABASE_URL absent   → SQLite
```

---

## Reliability Improvements

During development, several production-level issues were identified and fixed:

- Migrated production persistence from SQLite to PostgreSQL
- Added persistent approved decisions
- Added deterministic policy overrides
- Added LLM fallback behavior
- Improved LLM JSON parsing and truncation handling
- Added controlled PostgreSQL connection pooling
- Fixed PostgreSQL query compatibility for literal `%` queries
- Prevented scheduled retries from being counted as recovered revenue
- Added signed webhook verification
- Clearly separated live Test Mode proof from synthetic metrics

---

## API Endpoints

Some major backend endpoints include:

```text
GET  /api/transactions
GET  /api/dashboard/metrics
GET  /api/agent/trace/<transaction_id>
POST /api/recover/<transaction_id>
POST /api/webhook/razorpay
```

---

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/shrutikushwaha18/AI-Revenue-Recovery.git
cd AI-Revenue-Recovery
```

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Local backend:

```text
http://127.0.0.1:5000
```

If `DATABASE_URL` is not set, the backend uses SQLite locally.

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## Environment Variables

Create the required environment variables locally or in the deployment platform.

```env
LLM_API_KEY=
LLM_API_URL=
LLM_MODEL=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

DATABASE_URL=
```

> Never commit API keys, database credentials, or webhook secrets to GitHub.

---

## Safety Principles

RecoverAI is designed around the principle that AI should assist financial decisions, not directly control them.

Important safeguards include:

- LLM is advisory only
- Deterministic policy is final authority
- Retry limits
- Customer opt-out handling
- Already-recovered protection
- High-value or risky cases can require human review
- Synthetic transactions cannot trigger real payment execution
- Signed webhook verification before marking recovery successful

---

## Demo Flow

1. Show failed transaction
2. Show LLM recommendation
3. Show deterministic policy decision or override
4. Show persisted approved action
5. Show Razorpay Test Payment Link execution
6. Show customer Test Mode payment
7. Show signed webhook verification
8. Show recovered transaction state
9. Show PostgreSQL persistence
10. Show separate synthetic evaluation

---

## Project Objective

RecoverAI aims to make failed-payment recovery more intelligent, safe, auditable, and reliable by combining:

- LLM-based contextual reasoning
- Deterministic financial controls
- Verified payment execution
- Persistent recovery state
- Scalable synthetic evaluation

---

## Future Improvements

- Multi-provider payment gateway support
- Merchant-specific policy configuration
- Customer communication automation
- Recovery prioritization using historical behavior
- Real-time risk scoring
- Better human-review workflows
- Production analytics and monitoring
- A/B testing of recovery strategies

---

## Author

**Shruti Kushwaha**  
B.Tech CSE (Artificial Intelligence)  
Pranveer Singh Institute of Technology, Kanpur

---

## Repository

https://github.com/shrutikushwaha18/AI-Revenue-Recovery

---

## Note

This project uses **Razorpay Test Mode** for payment execution proof.

Synthetic evaluation values shown in the dashboard are simulated and should not be interpreted as production revenue.
