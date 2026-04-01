# Protegrity + CrewAI Integration

> Multi-agent collaboration with enterprise-grade PII governance

---

## The 4 Whys

### Why Change?

CrewAI enables **multi-agent architectures** where specialized AI agents
collaborate on tasks — a research agent retrieves data, an analyst interprets it,
a responder drafts the answer. This division of labor produces better results, but
it multiplies the points where PII can be exposed.

**What is broken today:**

- **Every agent sees raw PII.** In a typical CrewAI setup, customer data passes
  from agent to agent in plain text. A research agent retrieves customer profiles.
  An analyst agent processes them. A response agent formats the answer. Each agent
  is a separate LLM call — each one sends real PII to a third-party provider.
- **Agent delegation is uncontrolled.** CrewAI agents can delegate work to each
  other, creating dynamic task chains. PII flows along these chains unpredictably —
  a delegated sub-task might send customer data to a tool or API that was never
  intended to handle sensitive information.
- **Agent memory stores PII.** CrewAI's memory and context-sharing mechanisms
  retain data between tasks. Customer names, account numbers, and transaction
  details accumulate in agent memory with no governance or expiration.
- **Verbose mode logs everything.** During development and debugging, CrewAI's
  verbose output prints full agent inputs and outputs — including customer PII —
  to console and log files.
- **Backstory-based guardrails are unreliable.** Telling an agent "never expose PII"
  in its backstory is prompt engineering, not enforcement. An adversarial or
  hallucinating model can ignore these instructions entirely.

The more agents collaborate, the more copies of PII exist in memory, logs, and
API calls.

---

### Why Now?

- **Multi-agent systems are going to production.** CrewAI is no longer experimental.
  Organizations are deploying agent crews for customer support, document processing,
  and financial analysis — all involving sensitive customer data.
- **Agent autonomy is increasing.** As crews gain tool-use capabilities (database
  queries, API calls, code execution), a single unprotected PII value can propagate
  far beyond the chat interface into operational systems.
- **Compliance requires data lineage.** Regulations demand knowing where PII was
  sent, who processed it, and how it was protected — at every step. Multi-agent
  architectures create complex data lineage that is impossible to audit without
  systematic protection.
- **Agent-to-agent communication is a new attack surface.** Prompt injection in a
  multi-agent system doesn't just trick one model — it can cascade through the crew,
  with each agent amplifying the compromised instruction.

The more agents an organization deploys, the more urgent data-level protection
becomes.

---

### Why Protegrity?

Protegrity's approach is uniquely suited to multi-agent architectures because it
operates **outside the agent boundary**:

- **Agents never see real PII.** Gate 1 tokenizes all input before the crew starts.
  The research agent retrieves tokenized profiles. The response agent formats
  tokenized answers. No agent, at any point, processes a real customer name, email,
  or SSN.
- **Agent delegation is safe by default.** It doesn't matter how many agents a task
  is delegated to — they all operate on tokens. CrewAI's `allow_delegation` setting
  becomes a workflow concern, not a security concern.
- **Agent memory contains only tokens.** Context shared between agents, cached
  in memory, or persisted for debugging contains only Protegrity tokens. A memory
  dump reveals nothing about real customers.
- **Verbose mode is safe.** Developers can enable CrewAI's full verbose output
  during development without risking PII exposure. Every log line contains
  tokens — never real values.
- **Protection can't be overridden by prompts.** Unlike backstory-based guardrails,
  Protegrity's tokenization is a data transformation, not an instruction. An agent
  that hallucinates, ignores its backstory, or follows injected instructions still
  can only produce tokenized output.

---

### Why It Matters?

**If solved:** Multi-agent AI becomes enterprise-ready. Organizations can leverage
CrewAI's collaborative intelligence — specialized agents producing better answers
through division of labor — while maintaining complete data governance. Agent
complexity becomes an advantage (better reasoning) rather than a liability
(more leak points).

**If not solved:** Every agent added to a crew multiplies compliance risk. Teams
either restrict their crews to non-sensitive tasks (underutilizing the technology)
or accept uncontrolled PII propagation across agents (creating regulatory exposure
proportional to crew size). The most capable architecture becomes the most
dangerous.

CrewAI's value proposition is that multiple specialized agents outperform a single
general agent. Protegrity ensures this specialization doesn't come at the cost
of data governance.

---

## Technical Integration

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    TechnicalApp (Flask)                           │
│                                                                  │
│  User Message                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌───────────────────────────────────────────┐                   │
│  │  GATE 1 — Input Protection                │                   │
│  │  Guardrail → Discovery → Tokenization     │                   │
│  └──────────────────┬────────────────────────┘                   │
│                     │ protected_message                           │
│                     ▼                                             │
│  ┌───────────────────────────────────────────┐                   │
│  │  CrewAIOrchestrator                       │                   │
│  │                                           │                   │
│  │  Crew(process=sequential)                 │                   │
│  │                                           │                   │
│  │  ┌─────────────────────────────────────┐  │                   │
│  │  │  Agent 1: Research Analyst          │  │                   │
│  │  │  "Retrieve customer data from KB"   │  │                   │
│  │  │                                     │  │                   │
│  │  │  Task: Retrieve info for CUST-ID    │  │                   │
│  │  │  Input: tokenized context           │  │                   │
│  │  │  Output: relevant data (tokenized)  │  │                   │
│  │  └──────────────┬──────────────────────┘  │                   │
│  │                 │                          │                   │
│  │                 ▼                          │                   │
│  │  ┌─────────────────────────────────────┐  │                   │
│  │  │  Agent 2: Service Representative    │  │                   │
│  │  │  "Answer the banking question"      │  │                   │
│  │  │                                     │  │                   │
│  │  │  Task: Generate response            │  │                   │
│  │  │  Input: research output (tokenized) │  │                   │
│  │  │  Output: answer (tokenized)         │  │                   │
│  │  └──────────────┬──────────────────────┘  │                   │
│  │                 │                          │                   │
│  └─────────────────┼──────────────────────────┘                   │
│                    │ raw_response (tokenized)                     │
│                    ▼                                              │
│  ┌───────────────────────────────────────────┐                   │
│  │  GATE 2 — Output Unprotection             │                   │
│  │  Detokenize per user role/policy          │                   │
│  └──────────────────┬────────────────────────┘                   │
│                     ▼                                             │
│              Final Response                                      │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Definitions

**Research Analyst Agent:**
```
Role:      "Banking Research Analyst"
Goal:      Retrieve relevant customer data from the knowledge base
Backstory: "You have access to pre-protected customer records.
            All PII is tokenized — never attempt to decode tokens."
Delegation: Disabled (allow_delegation=False)
```

**Customer Service Representative Agent:**
```
Role:      "Customer Service Representative"
Goal:      Answer the customer's banking question using tokenized data
Backstory: System prompt + "Preserve all [TAG]value[/TAG] tokens exactly
            as they appear."
Delegation: Disabled (allow_delegation=False)
```

### Task Execution Flow

**Task 1 — Research:**
- Input: Customer ID + tokenized KB context (up to 2000 chars)
- Action: Research agent analyzes the available context
- Output: Relevant customer data extracted from the tokenized profile

**Task 2 — Response:**
- Input: Research output + tokenized user question
- Action: Response agent formulates a banking answer
- Constraint: Must preserve `[TAG]value[/TAG]` tokens exactly
- Output: Customer-facing answer (still tokenized)

**Execution:** `crew.kickoff()` runs tasks sequentially. If CrewAI fails,
the orchestrator falls back to a direct LLM call with the same tokenized context.

### Data Flow Example

```
User:     "List my recent transactions"

Gate 1:
  Guardrail  → risk_score=0.05, accepted
  Discovery  → no PII in query
  Protection → unchanged

CrewAI Crew:
  ┌─ Task 1: Research ─────────────────────────────────────────┐
  │ Agent: Research Analyst                                     │
  │ Input: CUST-100005 profile (tokenized names, accounts)     │
  │ Output: "Customer [PERSON]Rk4mN vWxPq[/PERSON] has         │
  │          3 recent transactions on account                   │
  │          [BANK_ACCOUNT]7291038456[/BANK_ACCOUNT]..."       │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─ Task 2: Response ─────────────────────────────────────────┐
  │ Agent: Service Representative                               │
  │ Input: Research output + user question                     │
  │ Output: "Here are your recent transactions:                │
  │          Account [BANK_ACCOUNT]7291038456[/BANK_ACCOUNT]   │
  │          1. Mar 15 - $245.00 at Grocery Store              │
  │          2. Mar 14 - $89.99 at Electronics..."             │
  └─────────────────────────────────────────────────────────────┘

Gate 2:
  Detokenize → Real account numbers and names restored
```

### Data Sources

| Source | Supported | Description |
|---|---|---|
| **Knowledge Base (KB)** | ✅ | Pre-tokenized profiles fed to Research Agent |
| **RAG (ChromaDB)** | ❌ | Not used — research via KB context |
| **Knowledge Graph** | ✅ | Structured relationships for customer data |

### Key Implementation Details

- **Class:** `CrewAIOrchestrator` in `orchestrators/crewai_orch.py`
- **Framework:** `crewai.Crew` with `Process.sequential`
- **Two agents, two tasks** — separation of retrieval and response generation
- **No delegation** — agents cannot create sub-tasks (controlled pipeline)
- **Fallback mechanism** — if `crew.kickoff()` fails, falls back to a direct
  LLM call using the same tokenized context
- **Token preservation** enforced in both agent backstories and task descriptions
- **Verbose mode disabled** in production but safe to enable (all data is tokenized)

### When to Use CrewAI

- **Role-based reasoning** — when retrieval and response benefit from
  separate agent perspectives
- **Auditable agent workflows** — clear separation of "what was retrieved"
  vs "what was generated"
- **Teams familiar with CrewAI** — leverage existing CrewAI skills and patterns
- **Future extensibility** — easily add agents (validator, summarizer, translator)
  that all operate safely on tokenized data
