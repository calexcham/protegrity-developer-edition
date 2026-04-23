# Protegrity × Composio Secure Data Bridge — Reference for Claude

> **Purpose:** Complete documentation for Claude to resume work without re-discovery.
>
> **Last updated:** 2026-04-01

---

## 1. End-to-End Dataflow

### Step-by-Step: User Request → Protected Output

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER / CLIENT                                      │
│                  (Browser UI · POST /api/ask · REST)                        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  ① User submits a natural-language request
                                   │     e.g. "Fetch the top issues from my GitHub repo
                                   │            and send a summary to Slack"
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMPOSIO AGENT  (agent.py)                              │
│              ProtegrityComposioAgent.run(prompt)                            │
└──────────┬───────────────────────────────────────────────┬──────────────────┘
           │                                               │
           │  ② Agent calls a Composio tool               │  (repeated for each
           │     e.g. GitHub → list issues                 │   platform interaction)
           ▼                                               │
┌──────────────────────────┐                               │
│   EXTERNAL PLATFORM      │                               │
│  GitHub / Gmail / Slack  │                               │
│  Salesforce / HubSpot …  │                               │
└──────────┬───────────────┘                               │
           │                                               │
           │  ③ Platform returns raw data                  │
           │     (may contain PII: names, emails,          │
           │      SSNs, credit cards, phone numbers …)     │
           ▼                                               │
┌─────────────────────────────────────────────────────────┐│
│           PROTEGRITY — SEMANTIC GUARDRAIL               ││
│         pb.semantic_guardrail(raw_data)                 ││
│         POST → http://localhost:8581/…/scan             ││
│                                                         ││
│   ④ Risk score evaluated against threshold              ││
│                                                         ││
│      risk_score ≥ threshold?                            ││
│         YES → ✋ BLOCKED — pipeline stops here          ││
│               error returned to user                    ││
│         NO  → ✅ PASS — continue to Gate 1              ││
└─────────────────────────────┬───────────────────────────┘│
                              │                             │
                              │  ⑤ Data cleared by         │
                              │     Semantic Guardrails     │
                              ▼                             │
┌─────────────────────────────────────────────────────────┐│
│        PROTEGRITY — GATE 1: FIND AND PROTECT            ││
│         pb.find_and_protect(raw_data, cfg)              ││
│         POST → http://localhost:8580/…/classify         ││
│                                                         ││
│   ⑥ Protegrity Policy applied:                         ││
│      • Classify: detect PII entity types                ││
│        (PERSON, EMAIL_ADDRESS, SSN, CCN, PHONE …)       ││
│      • Tokenize: replace real PII with opaque tokens    ││
│        "John Smith" → [PERSON]K7xmPQ RLzz[/PERSON]     ││
│        "042-80-1234" → [SSN]Hj9mNzX[/SSN]              ││
│      • Fallback: sdk.discover() if SDK returns          ││
│        unchanged text (character-span wrapping)         ││
│                                                         ││
│   Result: protected_data — NO raw PII remains           ││
└─────────────────────────────┬───────────────────────────┘│
                              │                             │
                              │  ⑦ Only tokenized data     │
                              │     leaves this boundary   │
                              ▼                             │
┌─────────────────────────────────────────────────────────┐│
│                    LLM  (OpenAI)                        ││
│       gpt-4o-mini / gpt-4  via openai Python SDK       ││
│                                                         ││
│   ⑧ LLM processes protected_data                       ││
│      • Sees tokens, NEVER real PII                      ││
│      • Reasons, summarises, drafts reply                ││
│      • Must preserve [TAG]…[/TAG] wrappers in output   ││
│                                                         ││
│   Result: llm_output (may still contain tokens)        ││
└─────────────────────────────┬───────────────────────────┘│
                              │                             │
                              │  ⑨ Does the agent need     │
                              └─────► another platform? ───┘
                                        YES → back to ②
                                        NO  → all steps done
                                              ↓
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│        PROTEGRITY — FINAL OUTPUT SEMANTIC GUARDRAIL                         │
│         pb.semantic_guardrail(llm_output)                                   │
│         POST → http://localhost:8581/…/scan                                 │
│                                                                             │
│   ⑩ Final LLM output risk-scored before delivery                           │
│                                                                             │
│      risk_score ≥ threshold?                                                │
│         YES → ✋ BLOCKED — output suppressed, error returned to user        │
│         NO  → ✅ PASS — continue to Gate 2                                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │  ⑪ Output cleared by Semantic Guardrails
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│             PROTEGRITY — GATE 2: RBAC-GATED OUTPUT                         │
│         ProtegrityComposioAgent.reveal(text, role)                          │
│         pb.find_and_unprotect / find_and_redact                             │
│                                                                             │
│   ⑫ Role checked against Protegrity RBAC policy:                           │
│                                                                             │
│      ┌──────────────┬────────────────────────────────────────────────────┐  │
│      │ RBAC Role    │ Gate 2 Action                                      │  │
│      ├──────────────┼────────────────────────────────────────────────────┤  │
│      │ admin        │ find_and_unprotect() → real PII restored           │  │
│      │              │ [PERSON]K7xmPQ RLzz[/PERSON] → "John Smith"       │  │
│      ├──────────────┼────────────────────────────────────────────────────┤  │
│      │ analyst      │ find_and_redact()    → [REDACTED] in place         │  │
│      │              │ [PERSON]K7xmPQ RLzz[/PERSON] → [REDACTED]         │  │
│      ├──────────────┼────────────────────────────────────────────────────┤  │
│      │ viewer       │ tokens passed through unchanged                    │  │
│      │              │ [PERSON]K7xmPQ RLzz[/PERSON] stays as-is          │  │
│      └──────────────┴────────────────────────────────────────────────────┘  │
└──────────┬────────────────────────────────┬──────────────────────────────────┘
           │                                │
           ▼                                ▼
┌────────────────────────┐      ┌───────────────────────────┐
│   AUTHORIZED USER      │      │  UNAUTHORIZED USER         │
│   (admin role)         │      │  (analyst / viewer role)   │
│                        │      │                            │
│  Full unprotected      │      │  Redacted output or        │
│  data:                 │      │  opaque tokens only:       │
│  "John Smith"          │      │  "[REDACTED]" or           │
│  "042-80-1234"         │      │  "[SSN]Hj9mNzX[/SSN]"     │
│  "card: 4111…"         │      │  "[PERSON]K7xm…[/PERSON]" │
└────────────────────────┘      └───────────────────────────┘
```

### Summary Table

| Step | Component | What happens |
|------|-----------|-------------|
| ① | User / Client | Natural-language request submitted |
| ② | Composio Agent | Tool call dispatched to external platform |
| ③ | External Platform | Raw data returned (may contain PII) |
| ④ | Semantic Guardrail (input) | Risk-score raw data — **BLOCK** if risky |
| ⑤ | Guardrail PASS | Data cleared to proceed |
| ⑥ | Gate 1 — Find and Protect | Protegrity policy classifies + tokenizes all PII |
| ⑦ | Token boundary | Only tokenized data crosses into LLM |
| ⑧ | LLM | AI reasoning on protected data only |
| ⑨ | Agent loop | Repeat ②–⑧ for every platform the agent needs to call |
| ⑩ | Semantic Guardrail (output) | Risk-score final LLM output — **BLOCK** if risky |
| ⑪ | Guardrail PASS | Output cleared for delivery |
| ⑫ | Gate 2 — RBAC Output | Unprotect (admin) / redact (analyst) / tokens (viewer) |
| — | Authorized user | Receives real, unprotected data |
| — | Unauthorized user | Receives `[REDACTED]` or opaque tokens |

---

## 2. Project Location & Directory

```
/home/azure_usr/protegrity_ai_integrations/protegrity_composio/
```

---

## 3. Directory Structure

```
protegrity_composio/
├── .env                      # API keys and endpoints (copy from .env.example)
├── .env.example              # Template for .env
├── .env.local                # Optional local overrides
├── readme_for_Claude.md      # THIS FILE
├── run.sh                    # Launcher — starts FastAPI via uvicorn on port 8900
│
├── main.py                   # FastAPI app — all HTTP routes + middleware
├── config.py                 # Config dataclass + load_config() from .env
├── agent.py                  # ProtegrityComposioAgent (live + demo mode) + RBAC_ROLES
├── protegrity_bridge.py      # Thin wrapper around Protegrity SDK (protect/unprotect/redact/guardrail)
│
├── pipeline.py               # GitHub Issues → Gate 1 → Gate 2 → Google Sheets
├── email_pipeline.py         # Gmail → GitHub Issues → Gate 1 + Gate 2 → email reply
├── slack_pipeline.py         # GitHub Issues → Gate 1 → per-role Gate 2 → Slack DMs
├── mock_demo_pipeline.py     # Fully mocked pipeline (no external deps) for offline demo
│
├── gmail_agent.py            # Gmail IMAP/SMTP client (App Password auth)
├── gmail_api_client.py       # Gmail REST API client (OAuth2 token auth)
├── google_drive.py           # Google Drive + Sheets integration (OAuth2 or Service Account)
│
├── frontend/
│   ├── index.html            # Single-page UI
│   └── static/               # CSS, JS assets
│
└── google_auth/
    ├── token.json            # Google Drive OAuth2 token (created after auth)
    ├── gmail_state.json      # Gmail-specific saved state
    └── service_account.json  # Google Service Account key (alternative to OAuth2)
```

---

## 4. Architecture Overview

### Core Concept — Dual-Gate per Pipeline

Every pipeline routes external data through two Protegrity gates before it
reaches the LLM or any outbound channel:

```
External Platform (GitHub / Gmail / Slack / Salesforce / …)
    │
    ▼ Composio tool call fetches raw data (may contain PII)
    │
    ▼ GATE 1 — protegrity_bridge.find_and_protect()
    │           Classifies + tokenizes every PII entity
    │           LLM / downstream NEVER sees raw PII
    │
    ▼ LLM reasoning / formatting (works with tokens only)
    │
    ▼ GATE 2 — protegrity_bridge.find_and_unprotect()  [RBAC-gated]
    │           admin role  → detokenize → real PII for final output
    │           viewer role → tokens stay → masked output
    │           analyst role → [REDACTED] replaced
    │
    ▼ Outbound (API response / Google Sheets / Slack DM / email reply)
```

### Operating Modes

| Mode | Condition | Behaviour |
|------|-----------|-----------|
| **Live** | Composio apps connected | Real tool calls via composio CLI + SDK |
| **Demo** | No apps connected | Synthetic PII-rich scenario data used to show Gate 1/2 |

---

## 5. Pipelines

### 4.1 GitHub → Google Sheets (`pipeline.py`)

```
GitHub Issues API (oauth token optional)
    │ fetch_github_issues()  →  5 issues max, PRs filtered out
    ▼
_slim_issue()  →  reduce fields to: number, title, state, user.login, labels, body[:500], html_url
    ▼
GATE 1: pb.find_and_protect(json_text)  →  all PII tokenized
    │   PII elements list built: [{type, token}, …]
    ▼
GATE 2: pb.find_and_unprotect(protected_json, cfg, role)
    │   admin  → real data restored
    │   viewer → token strings kept
    ▼
Google Drive: create_issues_spreadsheet(issues, title)
    │   Columns: #, Title, State, Author, Labels, Created, Description, Link
    ▼
Returns: { stage_1_fetch, stage_2_protect, stage_3_unprotect, stage_4_drive, pii_count }
```

### 4.2 Gmail Agentic Pipeline (`email_pipeline.py`)

```
Gmail IMAP/SMTP (App Password) OR Gmail REST API (OAuth2)
    │ fetch_unread_recent(hours=24)
    ▼
parse_intent(subject, body)
    │ Extracts: action (recent_issues | specific_issues), issue_numbers, count, repo
    ▼
GitHub Issues API (fetch per intent)
    ▼
GATE 1: pb.find_and_protect(issues_text)
    ▼
[optional LLM formatting step]
    ▼
GATE 2: pb.find_and_unprotect(…)  [admin only for replies]
    ▼
GmailClient.send_reply()  →  formatted email with protected/unprotected issues
GmailClient.mark_as_read()
    ▼
Returns: { emails_processed, replies_sent, pipeline_steps, error }
```

### 4.3 GitHub → Slack (`slack_pipeline.py`)

```
GitHub Issues API  →  fetch_today_issues() (last 24h, falls back to most-recent 5)
    ▼
GATE 1: pb.find_and_protect(issues_json)
    ▼
For each configured Slack recipient:
    role == "admin"  → GATE 2 find_and_unprotect → send plain data
    role == "viewer" → skip Gate 2              → send tokenized data
    ▼
Slack WebClient.chat_postMessage (DM via user lookup by email / @username / display-name)
    ▼
Returns: { sent, failed, recipients_detail }
```

### 4.4 Mock Demo Pipeline (`mock_demo_pipeline.py`)

```
MOCK_INBOUND_EMAIL  (hardcoded with SSN, phone, names)
    ▼
MOCK_GITHUB_ISSUES  (hardcoded with emails, IPs, SSNs)
    ▼
GATE 1: pb.find_and_protect()   — calls real Protegrity classify API
    ▼
Semantic Guardrail: pb.semantic_guardrail()  — calls real SGR API
    ▼
GATE 2: pb.find_and_unprotect() — calls real Protegrity detokenize API
    ▼
Mock email reply text + mock spreadsheet rows
    ▼
Returns: { stages: [inbound_email, github_issues, gate1, guardrail, gate2, outbound] }
```

### 4.5 Agent / Free-form Query (`agent.py`)

```
POST /api/ask  {prompt: "…"}
    ▼
ProtegrityComposioAgent.run(prompt)
    │
    ├── Live mode: composio CLI tool calls
    │     _protect_tool_result() applied after EACH tool response
    │
    └── Demo mode: _run_demo_mode()   (selects scenario from keyword matching)
          scenario keywords: github/repo/issue/pr → GitHub scenario
                             email/gmail/mail     → Email scenario
                             salesforce/lead/crm  → Salesforce scenario
                             (default)            → Generic customer data
    ▼
Final answer protected through Gate 1
    ▼
Returns: { pipeline: [steps], final_answer, total_steps, pii_found }

POST /api/reveal  {text, role}  → Gate 2 on demand for authorized roles
```

---

## 6. Key Files — Detailed Reference

### 5.1 `main.py`

- **Framework:** FastAPI + uvicorn (port 8900, `--reload`)
- **Frontend:** `frontend/index.html` served at `/`; `frontend/static/` at `/static`
- **CORS:** all origins allowed (demo deployment)
- **Model classes:** `DemoRunRequest`, `GmailRunRequest`, `SlackRunRequest`, `RevealRequest`, `AskRequest`, etc.
- **Redirect URI detection:** `_detect_redirect_uri()` — handles VS Code devtunnels, ngrok, Azure App Service, plain localhost automatically

### 5.2 `config.py`

- **`Config` dataclass** — frozen, holds all credentials + endpoint URLs
- **`load_config()`** — reads `.env`, validates required vars, raises `EnvironmentError` if any missing
- **Required vars:** `DEV_EDITION_EMAIL`, `DEV_EDITION_PASSWORD`, `DEV_EDITION_API_KEY`, `COMPOSIO_API_KEY`, `OPENAI_API_KEY`
- **Optional vars with defaults:** `CLASSIFY_URL`, `SGR_URL`, `DETOKENIZE_URL`, `OPENAI_MODEL` (`gpt-4o-mini`), `PORT` (8900)

### 5.3 `protegrity_bridge.py`

- **`find_and_protect(text, cfg)`** — SDK `find_and_protect()` + discover-based fallback if SDK returns unchanged text
- **`find_and_unprotect(text, cfg, role)`** — RBAC check → SDK `find_and_unprotect()` for admin, redact for analyst, return tokens for viewer
- **`find_and_redact(text)`** — strips tags and replaces content with `[REDACTED]`
- **`semantic_guardrail(text, cfg)`** — POST to SGR API, returns `{risk_score, blocked, reason}`
- **`_discover_and_protect_fallback(text, sdk)`** — calls `sdk.discover()`, applies character-position spans, avoids overlapping entities, priority-ranked
- **`_protect_lines(text, sdk)`** — splits on newlines to protect long blocks line-by-line
- **`NAMED_ENTITY_MAP`** — entity type → SDK data element (email, ssn, ccn, phone, string, address)
- **Entity patches** — imports `ENTITY_TO_DATA_ELEMENT` + `COMBINED_ENTITY_MAPPINGS` from BankingPortalChatbot's `services/protegrity_config.py` (shared config)
- **`_sdk_configured`** — module-level flag; SDK only bootstrapped once per process

### 5.4 `agent.py`

- **`ProtegrityComposioAgent`** — main orchestrator class
- **`run(prompt)`** — entry point; auto-detects live vs. demo mode
- **`_protect_tool_result(app, action, raw_text)`** — applies Gate 1, records `PipelineStep`
- **`reveal(text, role)`** — applies Gate 2 (unprotect / redact / passthrough based on RBAC)
- **`COMPOSIO_CLI`** — path resolution: `which composio` → `myenv/bin/composio` → `~/.composio/composio`
- **`_run_cli(*args)`** — subprocess wrapper around composio CLI, returns parsed JSON
- **`get_connected_apps()`** — calls `composio connected-accounts list`
- **`DEMO_SCENARIOS`** — dict of keyword → list of `{app, action, raw}` steps with PII-rich synthetic data

### 5.5 `pipeline.py`

- **`fetch_github_issues(repo, github_token, limit)`** — GitHub REST API, filters PRs, handles 404/401
- **`_slim_issue(issue)`** — keeps only displayable fields, truncates body to 500 chars
- **`run_full_pipeline(repo, github_token, cfg, rbac_role)`** — returns all 4 stages as a single dict

### 5.6 `email_pipeline.py`

- **`parse_intent(subject, body)`** — regex-based NLP: extracts `action`, `issue_numbers`, `count`, `repo`
- **`run_email_pipeline(gmail_client, github_token, cfg, default_repo, dry_run)`** — full pipeline; `dry_run=True` skips sending
- **Intent patterns:** `_ISSUE_NUM` (`#42`), `_LAST_N` (`last 3 issues`), `_REPO` (`owner/repo`), `_SEND_VERB`

### 5.7 `slack_pipeline.py`

- **`fetch_today_issues(repo, github_token, limit)`** — fetches issues updated in last 24h
- **`run_slack_pipeline(slack_token, repo, github_token, recipients, cfg, dry_run)`**
- **Recipient lookup:** by Slack email, @username, or display name — uses `users.list` API
- **Slack scopes required:** `chat:write`, `im:write`, `users:read`, `users:read.email`

### 5.8 `gmail_agent.py`

- **`GmailClient`** — IMAP/SMTP using App Password (not OAuth2)
- **`fetch_unread_recent(hours=24)`** — returns up to 20 unread emails
- **`send_reply(original, body_text)`** — sets `In-Reply-To` and `References` headers
- **`mark_as_read(imap_id)`** — marks email read via IMAP `+FLAGS \\Seen`

### 5.9 `gmail_api_client.py`

- **`GmailAPIClient`** — Gmail REST API using OAuth2 token (`google_auth/gmail_state.json`)
- **`get_auth_url(client_id, client_secret, redirect_uri)`** — returns authorization URL
- **`exchange_code(code, state)`** — exchanges OAuth code for token + saves state
- **`is_connected()`** / **`get_connected_email()`** — checks stored token
- **`disconnect()`** — deletes stored token
- **Important:** uses separate `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` env vars — NEVER fall back to `GOOGLE_CLIENT_ID` (which may be Composio's)

### 5.10 `google_drive.py`

- **OAuth2 flow:** `get_auth_url()` → browser → `/api/google/callback` → `exchange_code()` → token saved to `google_auth/token.json`
- **Service Account alternative:** `save_service_account(json_str)` → saves to `google_auth/service_account.json`
- **`is_connected()`** — checks for valid token or service account file
- **`create_issues_spreadsheet(issues, title)`** — creates a Google Sheet with issue data; returns `{spreadsheet_id, url}`
- **Scopes:** `drive.file`, `spreadsheets`

### 5.11 `mock_demo_pipeline.py`

- Self-contained demo — no GitHub token or Gmail credentials needed
- `MOCK_INBOUND_EMAIL` + `MOCK_GITHUB_ISSUES` constants contain rich synthetic PII
- Calls real Protegrity classify + SGR APIs
- Returns all intermediate stages for side-by-side visualization in the UI

---

## 7. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve frontend (`frontend/index.html`) |
| `GET` | `/api/health` | Check Protegrity, Composio CLI, GitHub, Google Drive, OpenAI status |
| `GET` | `/api/roles` | Return RBAC role definitions |
| `GET` | `/api/connected-apps` | List connected Composio apps + available app catalog |
| `POST` | `/api/connect` | Return Composio platform URL to connect an app |
| `POST` | `/api/ask` | Run agent with prompt (live or demo mode) |
| `POST` | `/api/reveal` | Gate 2 on demand — unprotect / redact based on `role` |
| `POST` | `/api/demo/test-github` | Validate GitHub repo access |
| `POST` | `/api/demo/run` | Full GitHub → Protegrity → Google Sheets pipeline |
| `GET` | `/api/google/status` | Google Drive connection status + redirect URI |
| `GET` | `/api/google/redirect-uri` | Return the detected redirect URI (add to Google Cloud Console) |
| `POST` | `/api/google/auth-url` | Start Google Drive OAuth2 flow |
| `GET` | `/api/google/callback` | OAuth2 callback — exchanges code, stores token |
| `DELETE` | `/api/google/disconnect` | Remove Google Drive token/service account |
| `POST` | `/api/google/service-account` | Alternative: paste Service Account JSON |
| `GET` | `/api/gmail/status` | Gmail connection status |
| `POST` | `/api/gmail/auth-url` | Start Gmail OAuth2 flow |
| `GET` | `/api/gmail/callback` | Gmail OAuth2 callback |
| `DELETE` | `/api/gmail/disconnect` | Remove Gmail token |
| `POST` | `/api/gmail/test` | Verify Gmail REST API connectivity |
| `POST` | `/api/gmail/preview` | Dry-run: fetch emails + parse intent (no replies sent) |
| `POST` | `/api/gmail/run` | Live email pipeline (fetch + protect + reply) |
| `POST` | `/api/slack/test` | Verify Slack bot token |
| `POST` | `/api/slack/run` | GitHub → Protegrity → Slack DM pipeline |
| `POST` | `/api/mock-demo` | Fully mocked pipeline (no external deps) |

---

## 8. Environment Variables (`.env`)

```bash
# ── Protegrity Developer Edition ─────────────────────────────────────────────
DEV_EDITION_EMAIL=your@email.com
DEV_EDITION_PASSWORD=yourpassword
DEV_EDITION_API_KEY=your-protegrity-api-key

# Protegrity local service endpoints (started by Docker Compose in AI_dev_Edition/)
CLASSIFY_URL=http://localhost:8580/pty/data-discovery/v1.1/classify
SGR_URL=http://localhost:8581/pty/semantic-guardrail/v1.1/conversations/messages/scan
DETOKENIZE_URL=http://localhost:8580/pty/data-protection/v1.1/detokenize

# ── Composio ──────────────────────────────────────────────────────────────────
# Project API Key (PAK) from https://platform.composio.dev → Settings → API Keys
# NOT the UAK from 'composio login' — UAK only works with the CLI binary
COMPOSIO_API_KEY=pak_...

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini       # optional — default is gpt-4o-mini

# ── Server ────────────────────────────────────────────────────────────────────
PORT=8900

# ── Optional: GitHub token (avoids rate limits on public repos) ───────────────
GITHUB_TOKEN=ghp_...

# ── Optional: Google Drive OAuth2 (set via UI, or add here) ──────────────────
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8900/api/google/callback  # override if using tunnel

# ── Optional: Gmail OAuth2 (SEPARATE from Google Drive credentials) ───────────
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
```

---

## 9. Startup

### Start (or restart) the app

```bash
# Option A — use the run.sh launcher
cd /home/azure_usr/protegrity_ai_integrations/protegrity_composio
bash run.sh

# Option B — direct uvicorn call
source /home/azure_usr/myenv/bin/activate
cd /home/azure_usr/protegrity_ai_integrations/protegrity_composio
python -m uvicorn main:app --host 0.0.0.0 --port 8900 --reload
```

### What `run.sh` does

1. `source .env` — loads environment variables
2. Resolves `PYTHON` (prefers `/home/azure_usr/myenv/bin/python`)
3. Starts `uvicorn main:app --host 0.0.0.0 --port $PORT --reload`

### Restart procedure (kill + restart)

```bash
# Kill existing processes on port 8900
kill $(lsof -ti:8900) 2>/dev/null || fuser -k 8900/tcp 2>/dev/null
sleep 1
cd /home/azure_usr/protegrity_ai_integrations/protegrity_composio
bash run.sh &
```

### Ensure Protegrity containers are running first

```bash
# Start Protegrity Developer Edition Docker containers
bash /home/azure_usr/start-protegrity.sh

# Quick status check
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
# Expected: semantic_guardrail (:8581), classification_service (:8580),
#           pattern_provider, context_provider
```

### Install dependencies (if needed)

```bash
source /home/azure_usr/myenv/bin/activate
pip install -r /home/azure_usr/protegrity_ai_integrations/protegrity_composio/requirements.txt
```

---

## 10. Auth Setup Guides

### 9.1 Composio

```
# CLI login (gives UAK — works with composio binary only)
composio login

# For SDK / API key mode (PAK — works with Python SDK):
# 1. Go to https://platform.composio.dev → Settings → API Keys
# 2. Create a Project API Key (PAK)
# 3. Set COMPOSIO_API_KEY=pak_... in .env

# Connect an app (opens browser)
composio apps connect github

# List connected accounts
composio connected-accounts list
```

### 9.2 Google Drive OAuth2

```
# 1. Go to https://console.cloud.google.com → APIs & Services → Credentials
# 2. Create OAuth2 Client → Web application
# 3. Add Authorized redirect URI:
#      http://localhost:8900/api/google/callback      (local)
#      https://<your-tunnel>.devtunnels.ms/api/google/callback   (VS Code tunnel)
#      Use GET /api/google/redirect-uri to get the exact URI this server expects
# 4. Enable "Google Drive API" and "Google Sheets API"
# 5. Copy Client ID + Secret into .env as GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
# 6. Click "Connect Google Drive" in the UI → authorize → token saved to google_auth/token.json

# Alternative: Service Account
# 1. Create a Service Account in Google Cloud Console → download JSON key
# 2. Enable Drive + Sheets API
# 3. Paste JSON into the UI → saved to google_auth/service_account.json
# 4. Share a Drive folder with the service account email to see files in your Drive
```

### 9.3 Gmail — App Password (IMAP/SMTP)

```
# No OAuth needed — simpler but requires 2FA on the Google account:
# 1. Enable 2-Step Verification: https://myaccount.google.com/security
# 2. Generate App Password: https://myaccount.google.com/apppasswords
#    (App: Mail, Device: Other → name it "ProtegrityDemo" → copy 16-char password)
# 3. Enter Gmail address + that 16-char password in the UI's Gmail section
```

### 9.4 Gmail — OAuth2 (REST API)

```
# Use YOUR OWN Google Cloud project — NOT Composio's credentials
# 1. Go to https://console.cloud.google.com → APIs & Services → Credentials
# 2. Create OAuth2 Client → Web application
# 3. Add Authorized redirect URI:
#      http://localhost:8900/api/gmail/callback
#      (or tunnel equivalent — GET /api/gmail/status returns the exact URI)
# 4. Enable "Gmail API" in the same project
# 5. Set GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET in .env
# 6. Click "Connect Gmail" in the UI → credentials stored in google_auth/gmail_state.json
```

### 9.5 Slack Bot Token

```
# 1. Go to https://api.slack.com/apps → Create New App → From scratch
# 2. OAuth & Permissions → Bot Token Scopes — add:
#      chat:write   im:write   users:read   users:read.email
# 3. Install App to workspace
# 4. Copy the Bot User OAuth Token (xoxb-...)
# 5. Paste into the UI's Slack section (stored in-memory only, not saved to .env)
```

---

## 11. RBAC Roles

| Role | `can_reveal` | Behaviour at Gate 2 |
|------|-------------|---------------------|
| `admin` | ✅ Yes | `find_and_unprotect()` — real PII restored |
| `analyst` | ❌ No | `find_and_redact()` — `[REDACTED]` in place of tokens |
| `viewer` | ❌ No | tokens passed through unchanged |

Roles are defined in `agent.py::RBAC_ROLES`.
In production these would come from an IdP or Protegrity policy engine.

---

## 12. PII Tag Format

Same format as BankingPortalChatbot:

```
[PERSON]C4idPSY LLxx[/PERSON]
[EMAIL_ADDRESS]gBlgez41oo3t@example.org[/EMAIL_ADDRESS]
[PHONE_NUMBER]728.751.7930[/PHONE_NUMBER]
[SOCIAL_SECURITY_ID]996-25-6169[/SOCIAL_SECURITY_ID]
[CREDIT_CARD]1158885255938243[/CREDIT_CARD]
[LOCATION]yZiXS[/LOCATION]
[DATETIME]1749-05-23[/DATETIME]
[ORGANIZATION]Acme Corp[/ORGANIZATION]
[IP_ADDRESS]10.0.0.1[/IP_ADDRESS]
```

The `_discover_and_protect_fallback()` uses the ORIGINAL text as the token content
(not the SDK-generated token) — this is expected for the demo to show PII detection.

---

## 13. Security Design Principles

1. **No raw PII reaches the LLM** — Gate 1 runs before any LLM call
2. **No raw PII in agent final answer** — final answer also passed through Gate 1
3. **RBAC enforced at Gate 2** — `can_reveal: false` roles never see detokenized data
4. **Separate Gmail vs. Google Drive credentials** — `GMAIL_CLIENT_ID` ≠ `GOOGLE_CLIENT_ID`
5. **Composio PAK vs. UAK distinction** — UAK (CLI login) only works with the binary; SDK requires PAK from platform.composio.dev
6. **Semantic Guardrail available** — `pb.semantic_guardrail()` for risk scoring incoming text
7. **Protegrity SDK shared config** — imports `ENTITY_TO_DATA_ELEMENT` from BankingPortalChatbot's `services/protegrity_config.py` as single source of truth
8. **Discover-based fallback** — if SDK `find_and_protect()` returns unchanged text, `sdk.discover()` + character spans used; `URL` entity suppressed to avoid false positives on emails
9. **Dry-run support** — all pipelines accept `dry_run=True` to preview without side effects

---

## 14. Shared Dependencies

The Protegrity SDK entity mapping is shared with `BankingPortalChatbot`:

```python
# protegrity_bridge.py imports from:
sys.path.insert(0, "/home/azure_usr/protegrity_ai_integrations/protegrity_demo/BankingPortalChatbot/services")
from protegrity_config import ENTITY_TO_DATA_ELEMENT, COMBINED_ENTITY_MAPPINGS, get_data_element
```

Changes to entity mappings in `BankingPortalChatbot/services/protegrity_config.py` affect both apps.
