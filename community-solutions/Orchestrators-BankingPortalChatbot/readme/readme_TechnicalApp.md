# TechnicalApp — Technical Reference

> **Port:** 5002 &nbsp;|&nbsp; **Audience:** Engineers, Solution Architects, Protegrity Demos  
> **Login:** `http://localhost:5002/tech/login`

---

## Prerequisites

Before running the TechnicalApp, ensure:

1. **Protegrity Developer Edition** is installed and running — use `bash scripts/setup_protegrity.sh`
2. **Python dependencies** are installed — `pip install -r config/requirements.txt`
3. **Environment variables** are configured in `.env` (LLM keys, Protegrity credentials)

See the [main README](README.md) for full installation steps.

---

## Goal

The TechnicalApp is a **fully configurable AI orchestration explorer** designed to demonstrate
how Protegrity's dual-gate architecture integrates with multiple AI frameworks.

Its primary purpose is **technical demonstration and validation**:

- Show that PII **never reaches an LLM in clear text**, regardless of orchestrator or LLM provider
- Let engineers **compare orchestrators** (Direct, LangGraph, CrewAI, LlamaIndex) side-by-side
- Let engineers **compare LLM providers** (OpenAI, Anthropic, Groq) with the same data
- Demonstrate **role-based unprotection** — different Protegrity users see different PII fields
- Expose the **full pipeline trace** so every gate, retrieval, and LLM call is visible

---

## Key Features

| Feature | Details |
|---|---|
| **Live configuration** | Switch orchestrator, LLM, data sources, and Protegrity role from the UI — no restart needed |
| **Pipeline trace** | Every step (Gate 1, KB lookup, RAG, KG, LLM, Gate 2) shown with duration in ms |
| **Guardrail toggle** | Enable/disable semantic guardrail independently of data discovery |
| **Discovery toggle** | Enable/disable PII tokenization — useful to see what the LLM *would* receive unprotected |
| **Protegrity user roles** | Superuser sees all PII; Marketing/Finance/Support see only their allowed fields |
| **15 test customers** | Full banking dataset (CUST-100000 to CUST-100014) with accounts, cards, loans, transactions |
| **RAG** | ChromaDB vector store over all customer KB profiles |
| **Knowledge Graph** | NetworkX graph of customer → account → card → transaction relationships |
| **Conversation history** | Per-customer, per-session chat history with protected messages |

---

## Architecture

```
Browser
  │
  ▼
Flask App (TechnicalApp/app.py)
  │
  ├── POST /tech/api/config     ← change orchestrator / LLM / settings
  │
  └── POST /tech/api/chat
        │
        ├── 1. Gate 1 ──────────────────────────────────────────────────────────┐
        │      ├── Semantic Guardrail (SGR) — risk score, block if > threshold   │
        │      └── find_and_protect() — tokenize PII in user message             │
        │                                                                        │
        ├── 2. Load KB Context                                                   │
        │      └── banking_data/knowledge_base/{customer_id}.txt (pre-tokenized) │
        │          register_tokens_from_context() — pre-load token map           │
        │                                                                        │
        ├── 3. Orchestrator ─────────────────────────────────────────────────────┤
        │      ├── direct:     LLM(KB context + protected message)               │  Protegrity
        │      ├── langgraph:  state machine → KB + RAG + KG + LLM              │  tokens flow
        │      ├── crewai:     retriever agent → responder agent                 │  through the
        │      └── llamaindex: query engine → RAG + KB + LLM                    │  entire chain
        │                                                                        │
        └── 4. Gate 2 ─────────────────────────────────────────────────────────┘
               ├── restore=True  → find_and_unprotect() — detokenize for user
               └── restore=False → find_and_redact() — replace tokens with [REDACTED]
```

### Protected Data Flow

```
customers_protected.json
  "name": "[PERSON]C4idPSY LLxx[/PERSON]"
  "email": "[EMAIL_ADDRESS]gBlgez41oo3t@example.org[/EMAIL_ADDRESS]"
  "ssn":   "[SOCIAL_SECURITY_ID]996-25-6169[/SOCIAL_SECURITY_ID]"
       │
       ▼
knowledge_base/CUST-100000.txt  ←── pre-tokenized at data-prep time
       │
       ▼
LLM system prompt + user context  ←── only tokens, never real PII
       │
       ▼
LLM response: "The SSN is [SOCIAL_SECURITY_ID]996-25-6169[/SOCIAL_SECURITY_ID]"
       │
       ▼
Gate 2 unprotect → "The SSN is 755-14-8936"   ←── real value restored by SDK
```

---

## Orchestrators

### Direct
Simplest pipeline: one LLM call with the KB profile as context.  
Uses: **KB only**. Best for: quick demos, low latency baseline.

```
User (protected) + KB context → LLM → Gate 2 → Response
```

### LangGraph
State machine with conditional branching across all three data sources.  
Uses: **KB + RAG + KG**. Best for: complex multi-source retrieval demos.

```
protected_query
    │
    ├── KB node     → load tokenized profile
    ├── RAG node    → ChromaDB similarity search
    ├── KG node     → NetworkX relationship query
    └── LLM node    → synthesize with all context
```

### CrewAI
Multi-agent pipeline: a Retriever agent gathers context, a Responder agent generates the answer.  
Uses: **KB + KG**. Best for: demonstrating agent delegation patterns.

```
Retriever Agent: "Fetch account data for CUST-100000"
    │
Responder Agent: "Here are your accounts: ..."
```

### LlamaIndex
Query engine over a vector index of all KB profiles.  
Uses: **KB + RAG**. Best for: semantic search over large document sets.

```
protected_query → LlamaIndex query engine → similarity search → LLM synthesis
```

---

## Protegrity User Roles (Gate 2)

The `protegrity_user` setting controls **which PII fields are unprotected** in Gate 2:

| Protegrity User | Fields Unprotected | Use Case |
|---|---|---|
| `superuser` | All PII (name, SSN, email, phone, card, DOB) | Full access — admin |
| `Marketing` | Name, email only | Campaign teams |
| `Finance` | Name, account numbers, card numbers | Payment processing |
| `Support` | Name, phone only | Customer service |

This demonstrates **attribute-level access control** — the same LLM response yields
different output depending on the authenticated user's role, with no application code changes.

---

## Configuration Reference

### URL Parameters / API

`POST /tech/api/config` accepts JSON:

```json
{
  "orchestrator":       "langgraph",
  "llm_provider":       "openai",
  "guardrail_enabled":  true,
  "discovery_enabled":  true,
  "show_trace":         true,
  "kb_enabled":         true,
  "rag_enabled":        true,
  "kg_enabled":         false,
  "protegrity_user":    "superuser"
}
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TECH_PORT` | `5002` | Flask listen port |
| `ORCHESTRATOR` | `direct` | Default orchestrator |
| `LLM_PROVIDER` | `openai` | Default LLM provider |
| `GUARDRAIL_ENABLED` | `true` | Semantic guardrail on/off |
| `GUARDRAIL_RISK_THRESHOLD` | `0.7` | Block threshold (0–1) |
| `CLASSIFY_URL` | `http://localhost:8580/...` | Protegrity Data Discovery |
| `SGR_URL` | `http://localhost:8581/...` | Protegrity Semantic Guardrail |
| `PROTEGRITY_USER` | `superuser` | Default Gate 2 role |

---

## Integration Tests

The `test_app_integration.py` script drives the live API with `requests.Session`:

| Suite | Tests | Coverage |
|---|---|---|
| `quick` | ~14 | Smoke — 1 customer, direct/openai |
| `prompts` | 7 | All 7 pre-prompts, direct/openai |
| `matrix` | 12 | All 4 orchestrators × 3 LLMs |
| `customers` | 15 | All 15 customers, direct/openai |
| `datasources` | 4 | LangGraph data source combinations |
| `roles` | 4 | All Protegrity user roles |
| `full` | **252** | 7 prompts × 3 customers × 12 combos |

```bash
# Run full matrix (requires app on port 5002)
python3 tests/test_app_integration.py --suite full
```

---

## Advantages

1. **Vendor-agnostic**: the same Protegrity protection layer works identically across
   OpenAI, Anthropic, and Groq — and across four different orchestration frameworks.

2. **Zero PII leakage by design**: the LLM is structurally incapable of receiving
   real PII — it only ever processes Protegrity tokens, regardless of configuration.

3. **Live reconfigurability**: engineers can switch every axis (LLM, orchestrator,
   data source, Protegrity role) without restarting the server — ideal for demos.

4. **Full observability**: the trace panel shows exact duration for each pipeline step,
   making it easy to identify bottlenecks or unexpected behaviour.

5. **Comprehensive test coverage**: 252 integration tests validated a 100% pass rate
   across all orchestrator/LLM/customer combinations in production conditions.
