# BusinessCustomerApp — Technical Reference

> **Port:** 5003 &nbsp;|&nbsp; **Audience:** End Customers (Banking Portal)  
> **Login:** `http://localhost:5003/bank/login`

---

## Prerequisites

Before running the BusinessCustomerApp, ensure:

1. **Protegrity Developer Edition** is installed and running — use `bash scripts/setup_protegrity.sh`
2. **Python dependencies** are installed — `pip install -r config/requirements.txt`
3. **Environment variables** are configured in `.env` (LLM keys, Protegrity credentials)

See the [main README](README.md) for full installation steps.

---

## Goal

The BusinessCustomerApp is a **customer-facing banking self-service portal** that
demonstrates how Protegrity can be embedded into a production-grade web application
to protect real customers' PII end-to-end.

Its primary purpose is to show **privacy by default**:

- Customer data is **stored encrypted** (`customers_protected.json`) — even at rest,
  SSNs, card numbers, names, emails, and phone numbers are Protegrity tokens
- The **dashboard and API unprotect data on demand** using `find_and_unprotect()` — no
  hand-rolled masking, no regex substitution, no application-level secrets
- The **AI chat assistant** wraps every message in a full dual-gate pipeline (Gate 1 +
  LangGraph + Gate 2) before any LLM call
- The **guardrail** blocks out-of-scope queries (e.g. weather, stock prices) before
  they reach the LLM or consume tokens

---

## Key Features

| Feature | Details |
|---|---|
| **Protected data by default** | All customer records loaded from `customers_protected.json` — Protegrity tokens at rest |
| **Protegrity unprotection on demand** | `find_and_unprotect()` called at the API boundary — values arrive clear only when needed |
| **Dashboard** | Accounts, credit cards (unprotected card numbers), loans, recent transactions |
| **PII fields unprotected at render time** | name, email, phone, address, DOB — via Protegrity, not manually |
| **AI chat assistant** | LangGraph + dual-gate (Gate 1 tokenize → LLM → Gate 2 unprotect) |
| **Semantic guardrail** | Out-of-scope prompts (weather, stocks, etc.) blocked before reaching the LLM |
| **Conversation history** | Per-customer persistent chat history, stored with protected messages |
| **15 demo customers** | Click-to-fill credentials panel on the login page |
| **Graceful degradation** | If Protegrity SDK is unavailable, raw tokens are returned as-is (no crash, no fake masking) |

---

## Architecture

```
Browser
  │
  ├── GET  /bank/login           ← credential panel with 15 demo users
  ├── POST /bank/login           ← SHA-256 password check vs customer_users.json
  ├── GET  /bank/dashboard       ← render template with Protegrity-unprotected PII
  │
  ├── GET  /bank/api/summary     ← JSON: name, email, phone, accounts, cards (unprotected)
  ├── GET  /bank/api/prompts     ← pre-prompt suggestions list
  │
  └── POST /bank/api/chat
        │
        ├── 1. Gate 1
        │      ├── Semantic Guardrail — block off-topic / malicious queries
        │      └── find_and_protect() — tokenize any PII in user message
        │
        ├── 2. Load KB context (pre-tokenized CUST-XXXXXX.txt)
        │      └── register_tokens_from_context()
        │
        ├── 3. LangGraph Orchestrator
        │      └── KB context + protected message → LLM
        │
        └── 4. Gate 2
               └── find_and_unprotect() — restore real values for the customer
```

### Data at Rest vs Data in Motion

```
                  AT REST                          IN MOTION
                     │                                 │
   customers_protected.json              /bank/api/summary response
   ┌─────────────────────────┐          ┌───────────────────────────┐
   │ name: [PERSON]Xk9[/]   │          │ name: "Allison Hill"       │
   │ email: [EMAIL]ab@[/]   │  ──────▶ │ email: "allison@acme.com"  │
   │ card: [CREDIT_CARD]..  │  unprotect│ card: "6011849593103413"   │
   │ ssn:  [SSN]996-25-6[/] │          │ (ssn not in public API)    │
   └─────────────────────────┘          └───────────────────────────┘
              ▲
         Protegrity SDK
         find_and_unprotect()
         called once per request
```

---

## Protegrity Integration Points

### 1. Data Source (`app.py` startup)

```python
# Loads protected data — not raw customers.json
_customers_path = PROJECT_ROOT / "banking_data" / "customers_protected.json"
```

All in-memory customer records contain Protegrity tokens, never real PII.

### 2. Dashboard Route (`GET /bank/dashboard`)

```python
display_customer = {
    **customer,
    "name":    _unprotect_text(customer.get("name", "")),
    "email":   _unprotect_text(customer.get("email", "")),
    "phone":   _unprotect_text(customer.get("phone", "")),
    "address": _unprotect_text(customer.get("address", "")),
    "dob":     _unprotect_text(customer.get("dob", "")),
}
```

Only fields needed for display are unprotected — SSN, for example, is never fetched.

### 3. Summary API (`GET /bank/api/summary`)

```python
# name, email, phone: unprotected in JSON response
# card_number: unprotected per card entry
card["card_number"] = _unprotect_text(cc.get("card_number", ""))
```

### 4. Chat Pipeline (`POST /bank/api/chat`)

```python
gate1  = guard.gate1_input(user_message, risk_threshold=0.7)  # protect + guardrail
result = ask(protected_message, protected_context=kb_context)  # LLM with tokens
gate2  = guard.gate2_output(raw_answer, restore=True)          # detokenize output
```

### 5. `_unprotect_text()` Helper

```python
def _unprotect_text(text: str) -> str:
    if not text or "[" not in text:
        return text                          # skip non-tokenized fields
    result = get_guard().find_and_unprotect(text)
    return result.transformed_text           # real value from Protegrity SDK
```

---

## Authentication

- Credentials are in `config/customer_users.json` — only `username`, `password_hash`
  (SHA-256), and `customer_id` — **no PII stored in the auth file**
- Customer display name in the session is resolved from the protected data store at
  login time via `_unprotect_text()`
- The login page includes a **collapsible demo credentials panel** — click any row to
  auto-fill the form

| Username range | Password range | Customers |
|---|---|---|
| `allison100` → `tanya114` | `pass100` → `pass114` | CUST-100000 → CUST-100014 |

---

## AI Chat — What the Guardrail Blocks

The semantic guardrail (risk threshold 0.7) blocks prompts unrelated to banking:

| Blocked Examples | Allowed Examples |
|---|---|
| "What's the weather today?" | "Show my personal details" |
| "Who won the football match?" | "What accounts do I have?" |
| "Write me a poem" | "List my recent transactions" |
| "Give me stock prices" | "What loans do I have?" |

Blocked responses are returned immediately without touching the LLM or consuming tokens.

---

## Integration Tests

`test_business_app_integration.py` drives the live app with `requests.Session`:

| Suite | Tests | Coverage |
|---|---|---|
| `quick` (default) | 14 | Connectivity, auth guards, dashboard, summary, PII check, chat |
| `login` | 45 | Login + summary structure + PII unprotection for all 15 customers |
| `chat` | 24 | All 7 pre-prompts + guardrail block × 3 customers |
| `full` | 83 | All of the above |

**Key validations:**
- No Protegrity tokens (`[ENTITY]...[/ENTITY]`) in any API response
- Unauthenticated requests redirected, not served
- Empty chat message returns HTTP 400
- Out-of-scope prompt triggers guardrail block

```bash
# Run (requires app on port 5003)
python3 tests/test_business_app_integration.py --suite full
```

---

## Advantages

1. **Privacy by default, not by afterthought**: the application never holds real PII
   in memory longer than the HTTP response — data at rest is always tokenized.

2. **No application-level masking logic**: there are no regex patterns, no `replace()`
   calls, no hardcoded field lists to maintain. Masking is delegated entirely to the
   Protegrity SDK — one function call, one source of truth.

3. **Audit-ready**: because all stored data is tokenized, a database breach exposes
   only Protegrity tokens — useless without the SDK and valid credentials.

4. **Consistent with the TechnicalApp**: both apps use the same `services/protegrity_guard.py`
   and `banking_data/customers_protected.json` — there is one protected dataset, two views of it.

5. **Graceful SDK failure**: if the Protegrity service is temporarily unavailable,
   the app logs a warning and returns the raw token rather than crashing — customers
   may see a token string, but the application stays available.

6. **Scalable unprotection pattern**: adding a new PII field to the dashboard requires
   only one line: `"field": _unprotect_text(customer.get("field", ""))` — no changes
   to the data layer, no new secrets, no new masking rules.
