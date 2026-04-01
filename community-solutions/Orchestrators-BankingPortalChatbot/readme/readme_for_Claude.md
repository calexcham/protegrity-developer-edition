# BankingPortalChatbot — Architecture Reference for Claude

> **Purpose:** Complete documentation for Claude to resume work without re-discovery.
> **Scope:** TechnicalApp (admin portal) and its supporting services.
>
> **Last updated:** 2026-03-31

---

## 1. Project Location

```
/home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot/
```

---

## 2. Directory Structure

```
BankingPortalChatbot/
├── .env                              # Protegrity + LLM credentials (see §7)
├── start_apps.sh                     # Launcher (TechnicalApp only)
├── pytest.ini                        # Pytest configuration
├── readme_for_Claude.md              # THIS FILE
├── readme_for_Protegrity.md          # Protegrity dual-gate architecture reference
├── readme_for_Orchestrators.md       # Why four orchestrators, data-source matrix
├── orchestration_config.py           # ORCHESTRATOR + LLM_PROVIDER selection
├── run_orchestrated.py               # CLI entry point
├── requirements_orchestration.txt    # Extra pip dependencies
│
├── config/                           # Runtime configuration
│   └── users.json                    # SHA-256 hashed passwords, roles, protegrity_user
│
├── TechnicalApp/                     # Technical/admin portal (port 5002)
│   ├── app.py                        # Flask app — config panel, chat with trace
│   ├── run.py                        # Standalone launcher
│   ├── templates/                    # Jinja2 HTML templates
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   └── chat.html                 # Includes predefined prompt buttons
│   └── chat_history_tech/            # Per-customer chat history JSON files
│
├── services/                         # Shared modules
│   ├── __init__.py
│   ├── banking_service.py            # Data access layer (auth, summaries, unprotect)
│   ├── protegrity_guard.py           # Dual-gate PII protection (Gate 1 + Gate 2)
│   ├── protegrity_config.py          # Entity-to-data-element mappings
│   ├── protegrity_dev_edition_helper.py  # Dev Edition session/auth management
│   └── conversation_history.py       # Chat history management class
│
├── common/                           # Shared by ALL orchestrators
│   ├── protegrity_gates.py           # Gate 1 + Gate 2 wrappers
│   ├── rag_retriever.py              # ChromaDB over pre-protected KB
│   └── knowledge_graph.py            # NetworkX graph over customers_protected.json
│
├── llm_providers/                    # Pluggable LLM backends
│   ├── __init__.py
│   └── factory.py                    # OpenAI / Anthropic / Groq factory
│
├── orchestrators/                    # Pluggable orchestration frameworks
│   ├── base.py                       # BaseOrchestrator ABC + PipelineResult
│   ├── factory.py                    # get_orchestrator() dispatcher (direct/langgraph/crewai/llamaindex)
│   ├── direct_orch.py                # DirectOrchestrator — simple LLM-only pipeline
│   ├── langgraph_orch.py             # LangGraph StateGraph pipeline
│   ├── crewai_orch.py                # CrewAI agents + tasks pipeline
│   └── llamaindex_orch.py            # LlamaIndex query pipeline
│
├── banking_data/                     # All customer/banking data
│   ├── customers_protected.json      # Protected data (primary source; account numbers plain text)
│   ├── knowledge_base/               # Pre-protected KB files for LLM context
│   │   └── CUST-XXXXXX.txt
│   └── knowledge_prep/               # Data pipeline scripts
│       ├── generate_banking_data.py
│       ├── protect_customer_data.py
│       └── generate_knowledge_base.py
│
└── tests/                            # Unit + integration tests
    ├── __init__.py
    ├── conftest.py                   # Adds project root to sys.path, loads .env
    ├── smoke_test.py                 # Quick smoke tests
    ├── test_banking_service.py       # Banking service tests
    ├── test_conversation_history.py  # Conversation history tests
    ├── test_orchestration.py         # Orchestration integration tests
    ├── test_orchestrators.py         # Orchestrator factories, gates, config, TechnicalApp
    └── test_pii_tags.py             # PII tag verification (account numbers plain, etc.)
```

---

## 3. TechnicalApp (port 5002)

| Item | Detail |
|------|--------|
| **Main file** | `TechnicalApp/app.py` |
| **Launcher** | `TechnicalApp/run.py` (called by `start_apps.sh`) |
| **Purpose** | Technical/admin portal for orchestration & Protegrity configuration |
| **Features** | Config panel (orchestrator, LLM, Protegrity settings), per-customer chat with pipeline trace |
| **Auth source** | `config/users.json` — SHA-256 hashed passwords, roles, protegrity_user |
| **Templates** | `TechnicalApp/templates/` (`login.html`, `dashboard.html`, `chat.html`) |
| **Chat history** | `TechnicalApp/chat_history_tech/` |
| **Gate 2** | Configurable: `superuser` (full), `Marketing` (limited), etc. via UI dropdown |
| **Config API** | `GET/POST /tech/api/config` — read/update orchestrator, LLM, threshold, user at runtime |
| **Pipeline trace** | Full step-by-step trace (Gate 1, KB, LLM, Gate 2) with timing, returned in chat JSON |

### 3.1 TechnicalApp Capabilities

| Feature | Detail |
|---------|--------|
| Gate 2 user | Configurable via UI |
| Orchestrator | Selectable (direct/langgraph/crewai/llamaindex) |
| LLM provider | Selectable (openai/anthropic/groq) |
| Risk threshold | Adjustable 0.0–1.0 (Semantic Guardrail blocking, default 0.7) |
| Classify threshold | Adjustable 0.0–1.0 (PII Discovery confidence, default 0.5) |
| Data source lockdown | Per-orchestrator toggles (KB/RAG/KG enforced server-side) |
| Guardrail | Toggle via UI |
| Discovery | Toggle via UI |
| Pipeline trace | Visible in UI |
| Model auto-clear | Model selection resets on provider change |
| Predefined prompts | Quick-access prompt buttons in chat UI |
| Port | 5002 |

---

## 4. Data Flow

### 4.1 Data Pipeline (offline)

```
generate_banking_data.py → customers.json (raw PII)
        │
        ▼  protect_customer_data.py (appython Protector tokenization)
        │
customers_protected.json (PII in [TAG]token[/TAG] format)
        │
        ▼  generate_knowledge_base.py
        │
knowledge_base/CUST-XXXXXX.txt (pre-protected text for LLM)
```

### 4.2 TechnicalApp Chat Flow (runtime)

```
Admin message
    ▼ Gate 1: gate1_protect() — classify + tokenize + guardrail
    │         risk > threshold → BLOCKED
    ▼ Load pre-protected KB file (knowledge_base/CUST-XXXXXX.txt)
    │ register_tokens_from_context() — builds token map
    ▼ LLM call (selected orchestrator + LLM provider)
    ▼ Gate 2: gate2_unprotect() — configurable user (superuser, Marketing, etc.)
    ▼ Full pipeline trace (Gate 1, KB, LLM, Gate 2) with timing
    ▼ Display to admin
```

### 4.3 Dashboard Data Flow

```
customers_protected.json (tokenized names/cards; plain account numbers)
    ▼ banking_service.get_account_summary()
    │   Name:     _unprotect() → guard.find_and_unprotect()
    │   Acct#:    plain text → mask "****XXXX"
    │   Card#:    _unprotect() → real number → last 4 digits
    │   Balances: displayed directly (not PII)
    ▼ Display on dashboard
```

---

## 5. Key Files — Detailed Reference

### 5.1 `TechnicalApp/app.py`

- **Flask app** on port 5002
- **Auth:** loaded from `config/users.json` (SHA-256 hashed passwords, roles, protegrity_user)
- **Config API:** `GET/POST /tech/api/config` — runtime update of orchestrator, LLM, thresholds (risk + classify)
- **Chat API:** `POST /tech/api/chat` — ALL modes (including direct) go through `_call_orchestrated()`
- **`_call_orchestrated()`** passes `user_message`, `customer_id`, `protected_context`, and `conversation_history`
- **Data source lockdown:** server-side enforcement per orchestrator (Direct: KB only, LangGraph: KB+RAG+KG, etc.)
- **No direct LLM imports** — does NOT import openai, anthropic, groq; no `_call_llm`/`_call_openai`/etc. functions
- **No API key variables** — OPENAI_API_KEY etc. managed elsewhere
- **Pipeline trace:** step-by-step (Gate 1 → KB → LLM → Gate 2) with timing in JSON response

### 5.2 `services/banking_service.py`

- **Primary data source:** `customers_protected.json` (fallback: `customers.json`)
- **`_unprotect(text)`** — calls `guard.find_and_unprotect()`, falls back to `_strip_pii_tags()`
- **`_get_guard()`** — lazy-loads guard to avoid circular imports
- **`get_account_summary()`** — unprotects name, card numbers via SDK; account numbers are plain text
- **Singleton:** `get_banking_service()` returns cached `_service_instance`

### 5.3 `services/protegrity_guard.py`

- **`ProtegrityGuard` class** — wraps Protegrity SDK
- **`gate1_input(text, risk_threshold)`** — classify + tokenize + risk score
- **`gate2_output(text, restore)`** — find tagged tokens → detokenize
- **`find_and_protect(text)`** — classify + tokenize without risk scoring
- **`find_and_unprotect(text)`** — find tagged tokens + detokenize
- **`register_tokens_from_context(text)`** — extracts `[TAG]value[/TAG]` into `_token_map`
- **Entity mapping:** patches SDK's `DATA_ELEMENT_MAPPING` from `protegrity_config.py`
- **SDK:** `appython.Protector` for tokenize/detokenize
- **Classification API:** `http://localhost:8580/pty/data-discovery/v1.1/classify`
- **Guardrail API:** `http://localhost:8581/pty/semantic-guardrail/v1.1/conversations/messages/scan`

### 5.4 `services/protegrity_config.py`

- **Single source of truth** for entity → data element mappings
- **`ENTITY_TO_DATA_ELEMENT`** — maps PII entity types to SDK data elements
- **`FIELD_PROTECTION_MAP`** — maps JSON field names to (tag, data_element) tuples
- **`COMBINED_ENTITY_MAPPINGS`** — handles merged entity types (e.g., `URL|EMAIL_ADDRESS`)
- **`get_data_element(entity_tag)`** — lookup function

### 5.5 `services/protegrity_dev_edition_helper.py`

- **Manages Developer Edition session lifecycle**
- **Auto-login** using `.env` credentials (DEV_EDITION_EMAIL, PASSWORD, API_KEY)
- **Session refresh:** tracks expiry, auto-renews before timeout

### 5.6 `services/conversation_history.py`

- **`ConversationHistory` class** — message list management
- **`add_user_message()`**, **`add_assistant_message()`**
- **`get_messages()`** — returns last N turns
- **`save_to_file()`** / **`load_from_file()`** — JSON persistence

### 5.7 `orchestration_config.py`

- **`ORCHESTRATOR`** — `langgraph | crewai | llamaindex` (validated by assert; `direct` handled separately by TechnicalApp/factory)
- **`LLM_PROVIDER`** — `openai | anthropic | groq`
- **`get_model_name()`** — returns model name (env override or provider default)
- **Backward-compat aliases:** `get_model`, `RISK_THRESHOLD`, `PROTEGRITY_USER`, `KB_ENABLED`

### 5.8 `llm_providers/factory.py`

- **`get_llm()`** — returns callable `fn(messages) -> str`
- **`get_llm_for_langchain()`** — returns LangChain `ChatModel` instance
- **Backward-compat alias:** `get_llm_provider = get_llm`
- **Supports:** OpenAI, Anthropic, Groq (lazy imports, graceful `ImportError`)

### 5.9 `common/protegrity_gates.py`

- **`gate1_protect(text, ...)`** — Gate 1 wrapper → `Gate1Result` dataclass
- **`gate2_unprotect(text, ...)`** — Gate 2 wrapper → `Gate2Result` dataclass
- **`register_context_tokens(text)`** — registers tokens from KB context
- **Production code uses dict access:** `result.get("protected_text")` on `guard.gate1_input()` return

---

## 6. Data Files

### 6.1 `banking_data/customers_protected.json`

- **15 customers** (CUST-100000 to CUST-100014), PII fields tokenized
- **Tag types:** PERSON, EMAIL_ADDRESS, PHONE_NUMBER, SOCIAL_SECURITY_ID, CREDIT_CARD, LOCATION, DATETIME
- **Account numbers:** stored as **plain text** (NOT tokenized with ACCOUNT_NUMBER tags)
- **Primary data source** for apps via `banking_service.py`

### 6.2 `config/users.json`

- **5 entries** — admin, engineer, langgraph, crewai, llamaindex
- **Fields per user:** `password_hash` (SHA-256 via hashlib), `role`, `protegrity_user`, `orchestrator`
- **Passwords:** admin=`Adm!n@S3cure2026`, engineer=`Eng#Pr0tegrity!`, others orchestrator-specific
- **Orchestrator lock:** langgraph/crewai/llamaindex users locked to their orchestrator; admin/engineer have `null` (free choice)
- **Replaces:** previously hardcoded `TECH_USERS` dict and deleted `banking_data/credentials.json`

### 6.3 `banking_data/knowledge_base/CUST-XXXXXX.txt`

- **Pre-protected text files** — one per customer
- **Account numbers:** shown as plain digits (e.g., `Acct#: 9697354961`)
- **Card numbers:** tagged (e.g., `[CREDIT_CARD]1158885255938243[/CREDIT_CARD]`)
- **Injected into LLM system prompt** as customer context
- **Generated by:** `generate_knowledge_base.py`

---

## 7. Environment Variables (`.env`)

```
DEV_EDITION_EMAIL=...              # Protegrity Dev Edition login
DEV_EDITION_PASSWORD=...           # Protegrity Dev Edition password
DEV_EDITION_API_KEY=...            # Protegrity Dev Edition API key

CLASSIFY_URL=http://localhost:8580/pty/data-discovery/v1.1/classify
SGR_URL=http://localhost:8581/pty/semantic-guardrail/v1.1/conversations/messages/scan

PROTEGRITY_HOST=http://localhost:8580
DETOKENIZE_URL=http://localhost:8580/pty/data-protection/v1.1/detokenize
PROTEGRITY_API_TIMEOUT=30

OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# Orchestration overrides:
ORCHESTRATOR=langgraph             # langgraph | crewai | llamaindex
LLM_PROVIDER=openai                # openai | anthropic | groq
LLM_MODEL=                         # optional override (auto-selected per provider)

# Gate overrides:
SKIP_PROTEGRITY_GATES=false
SKIP_SEMANTIC_GUARDRAIL=true
PII_DISCOVERY_THRESHOLD=0.4
GUARDRAIL_RISK_THRESHOLD=0.7
PROTEGRITY_USER=default_user
```

---

## 8. Startup

### Start TechnicalApp

```bash
cd /home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot
bash start_apps.sh
```

### What `start_apps.sh` does

1. Kills any existing process on port 5002
2. Starts TechnicalApp via `python TechnicalApp/run.py`
3. Sleeps 3 seconds
4. Health-checks `http://localhost:5002/tech/login`

> **Note:** Only TechnicalApp is started. Previous CustomerApp and InternalCustomerServiceApp references were removed.

### Restart procedure

```bash
cd /home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
fuser -k 5002/tcp 2>/dev/null
sleep 1
python TechnicalApp/run.py &
```

---

## 9. Security Design Principles

1. **No raw PII in LLM context** — KB files contain only tokenized data (account numbers are plain text by design)
2. **Auth via hashed passwords** — `config/users.json` stores SHA-256 hashes, not plaintext
3. **All PII display goes through Protegrity** — `_unprotect()` → `find_and_unprotect()`
4. **Gate 1 blocks risky inputs** — semantic guardrail with configurable risk threshold
5. **Configurable Gate 2 user** — `superuser` (full) or policy-limited (e.g., `Marketing`)
6. **Fallback chain** — SDK → REST API → strip tags (graceful degradation)
7. **Session auto-renewal** — Dev Edition sessions expire; helpers handle refresh

---

## 10. PII Tag Format

```
[PERSON]C4idPSY LLxx[/PERSON]
[EMAIL_ADDRESS]gBlgez41oo3t@example.org[/EMAIL_ADDRESS]
[PHONE_NUMBER]728.751.7930[/PHONE_NUMBER]
[SOCIAL_SECURITY_ID]996-25-6169[/SOCIAL_SECURITY_ID]
[CREDIT_CARD]1158885255938243[/CREDIT_CARD]
[LOCATION]yZiXS[/LOCATION]
[DATETIME]1749-05-23[/DATETIME]
```

> **Note:** Account numbers are **plain text** — they are NOT wrapped in `[ACCOUNT_NUMBER]` tags.

The LLM is instructed to **preserve these tags** in responses.
Gate 2 detokenizes them before display.

---

## 11. Import Graph

```
TechnicalApp/app.py
    ├── services.banking_service (get_banking_service)
    ├── services.protegrity_guard (get_guard, register_tokens_from_context, _strip_pii_tags)
    ├── services.conversation_history (ConversationHistory)
    └── orchestrators/factory → _call_orchestrated() → orchestrator.run()
    (NO direct imports of openai, anthropic, groq, or API key variables)

services/protegrity_guard.py
    ├── services.protegrity_dev_edition_helper (protegrity_request, invalidate_session)
    └── services.protegrity_config (ENTITY_TO_DATA_ELEMENT, COMBINED_ENTITY_MAPPINGS, get_data_element)

services/banking_service.py
    └── services.protegrity_guard (get_guard) — lazy-loaded via _get_guard()
```

---

## 12. API Endpoints — TechnicalApp (port 5002)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tech/` | Redirect to login or dashboard |
| GET/POST | `/tech/login` | Admin login |
| GET | `/tech/logout` | Logout |
| GET | `/tech/dashboard` | Config panel + customer selector |
| GET | `/tech/chat/<customer_id>` | Chat interface with trace |
| GET | `/tech/api/config` | Get current configuration |
| POST | `/tech/api/config` | Update configuration (JSON body) |
| POST | `/tech/api/chat` | Send chat message (JSON: message + customer_id) |
| POST | `/tech/api/chat/clear` | Clear chat history |

---

## 13. Orchestration Layer

### 13.1 Configuration

Set via environment variables or `.env`:

```bash
ORCHESTRATOR=langgraph          # direct | langgraph | crewai | llamaindex
LLM_PROVIDER=openai             # openai | anthropic | groq
LLM_MODEL=gpt-4o-mini           # optional override
```

> **Note:** `orchestration_config.py` validates only `langgraph|crewai|llamaindex`. The `direct` mode is handled by `orchestrators/factory.py` and TechnicalApp separately.

Default models per provider:

| Provider | Default Model |
|----------|---------------|
| openai | gpt-4o-mini |
| anthropic | claude-sonnet-4-20250514 |
| groq | llama-3.1-70b-versatile |

### 13.2 Orchestrators

| Orchestrator | Library | Pipeline Style | Data Sources |
|-------------|---------|----------------|--------------|
| **Direct** | none | Simple LLM call via `get_llm_provider()` | KB only |
| **LangGraph** | `langgraph` | StateGraph with conditional edges (gate1 → retrieve → llm → gate2) | KB + RAG + KG |
| **CrewAI** | `crewai` | 4 agents (Security, Research, Response, Compliance) with sequential tasks | KB + KG |
| **LlamaIndex** | `llama-index` | ChatMessage pipeline with native LLM adapters | KB + RAG |

All four implement `BaseOrchestrator.run()` → `PipelineResult`.

Data source availability is enforced both in the UI (toggle lockdown) and server-side in `app.py`.

### 13.3 Shared Common Layer

| Module | Purpose |
|--------|---------|
| `common/protegrity_gates.py` | `gate1_protect()`, `gate2_unprotect()`, `register_context_tokens()` |
| `common/rag_retriever.py` | ChromaDB semantic search over `banking_data/knowledge_base/*.txt` |
| `common/knowledge_graph.py` | NetworkX graph from `customers_protected.json` |

### 13.4 Pipeline (all orchestrators)

```
User query
    ▼ Gate 1: gate1_protect() — classify + tokenize + guardrail
    │         blocked if risk > risk_threshold (default 0.7)
    ▼ Retrieve: RAG (ChromaDB) + Knowledge Graph (NetworkX)
    │           RAG has customer isolation via ChromaDB `where` filter
    │           register_context_tokens() for Gate 2
    ▼ LLM: provider-specific call (OpenAI / Anthropic / Groq)
    │       system prompt includes tokenized context
    ▼ Gate 2: gate2_unprotect() — detokenize per user policy
    ▼ PipelineResult (answer + full pipeline trace)
```

> **Note:** Data sources vary by orchestrator (see §13.2). Direct mode uses KB only.

### 13.5 Running

```bash
cd /home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot
pip install -r requirements_orchestration.txt

# LangGraph + OpenAI (default)
python run_orchestrated.py

# CrewAI + Anthropic
ORCHESTRATOR=crewai LLM_PROVIDER=anthropic python run_orchestrated.py

# LlamaIndex + Groq
ORCHESTRATOR=llamaindex LLM_PROVIDER=groq python run_orchestrated.py
```

### 13.6 Integrating with TechnicalApp

The orchestration layer is fully unified in `TechnicalApp/app.py`. **ALL** modes (including direct) go through `_call_orchestrated()`:

```python
# No inline direct-mode block — every orchestrator uses the same path
result = _call_orchestrated(user_message, customer_id, protected_context, conversation_history)
```

The `_call_llm`, `_call_openai`, `_call_anthropic`, `_call_groq` functions have been removed (dead code). `app.py` does not import `openai`, `anthropic`, or `groq` directly.

---

## 14. Tests

### Run all tests

```bash
cd /home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot
python -m pytest tests/ -v
```

### Test files

| File | Purpose |
|------|---------|
| `test_orchestrators.py` | Orchestrator factories, gates, config, TechnicalApp endpoints |
| `test_pii_tags.py` | PII tag verification — account numbers plain, cards tagged, KB tags, no name in creds |
| `test_banking_service.py` | Banking service unit tests |
| `test_conversation_history.py` | Conversation history management |
| `test_orchestration.py` | Orchestration integration tests |
| `smoke_test.py` | Quick smoke tests |

### Key test: `test_pii_tags.py`

| Test | Verifies |
|------|----------|
| `test_customers_protected_has_tagged_names` | Names are wrapped in `[PERSON]` tags |
| `test_account_numbers_plain` | Account numbers are plain digits (NOT tokenized) |
| `test_card_numbers_tagged` | Card numbers are wrapped in `[CREDIT_CARD]` tags |
| `test_credentials_has_no_name_field` | credentials.json has no `name` field |
| `test_knowledge_base_contains_tags` | KB files contain PII tags |
| `test_non_pii_fields_not_tagged` | Balance/status fields are NOT tagged |

### Key tests: `test_orchestrators.py`

| Section | Tests |
|---------|-------|
| Config exports | `test_config_exports`, `test_get_model_defaults`, `test_config_aliases` |
| Gate dataclasses | `test_gate1_result_dataclass`, `test_gate2_result_dataclass` |
| Gate skip | `test_gate1_skip`, `test_gate2_skip` |
| Gate mocked | `test_gate1_handles_dict_result`, `test_gate1_blocks_high_risk`, `test_gate2_handles_unprotect` |
| PipelineResult | `test_pipeline_result` |
| Entry point | `test_run_orchestrated_import` |
| Orchestrator factories | `test_factory_langgraph`, `test_factory_crewai`, `test_factory_llamaindex` |
| LLM factory | `test_llm_factory_alias` |
| TechnicalApp | `test_tech_app_imports`, `test_tech_config_endpoint_exists`, `test_tech_config_post_updates`, `test_tech_chat_endpoint_exists` |

---

## 15. Known Issues / Gotchas

1. **`run.py` overrides `template_folder`** — edit `run.py` to change template path
2. **Guard lazy-loading** — `banking_service.py` uses `_get_guard()` to avoid circular imports
3. **Session expiry** — Dev Edition sessions expire (~30 min); helpers handle auto-renewal
4. **Tests require project root on `sys.path`** — `conftest.py` handles this
5. **`get_model_name()` takes no arguments** — reads global `LLM_PROVIDER`; alias `get_model` is the same
6. **Gate mocks must return dicts** — `gate1_protect()` calls `result.get()` on `guard.gate1_input()` return
7. **`get_llm_provider` is an alias for `get_llm`** — both names work
8. **`orchestration_config.py` rejects "direct"** — the assert validates only langgraph/crewai/llamaindex; "direct" is handled by `orchestrators/factory.py` and TechnicalApp config logic
9. **Account numbers are plain text** — NOT tokenized in `customers_protected.json` or KB files; verified by `test_account_numbers_plain`
10. **Two thresholds** — `risk_threshold` (Semantic Guardrail blocking) and `classify_threshold` (PII Discovery confidence) are independent controls

---

## 16. Common Operations

### Regenerate protected data + KB files

```bash
cd /home/azure_usr/protegrity_ai_integrations/protegrity_demo/orchestration/BankingPortalChatbot
python banking_data/knowledge_prep/protect_customer_data.py
python banking_data/knowledge_prep/generate_knowledge_base.py
```

### Test SDK connectivity

```bash
python banking_data/knowledge_prep/protect_customer_data.py --test
```

### Verify account numbers are plain text

```bash
python3 -c "
import json
data = json.load(open('banking_data/customers_protected.json'))
for c in data:
    for a in c.get('accounts', []):
        n = a.get('account_number', '')
        if '[' in n: print(f'TAGGED: {c[\"customer_id\"]} {n}')
        elif not n.isdigit(): print(f'NOT DIGITS: {c[\"customer_id\"]} {n}')
print('All account numbers are plain digits')
"
```

---

## 17. Customer Data Summary

- **15 customers:** CUST-100000 through CUST-100014
- **Logins:** `allison100`/`pass100` through `tanya114`/`pass114`
- **Each customer has:** 1-3 bank accounts, 1-3 credit cards, 0-3 loans, 20-65 transactions
- **TechnicalApp logins:** `admin`/`Adm!n@S3cure2026`, `engineer`/`Eng#Pr0tegrity!`, `langgraph`/`crewai`/`llamaindex` (orchestrator-specific passwords)