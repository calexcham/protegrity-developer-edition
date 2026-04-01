# Orchestrators & Protegrity Integration — Technical Reference

> **How Protegrity's dual-gate security integrates with four orchestration frameworks,**
> **and why each combination matters.**
>
> Version: 0.8.1 | Last updated: 2026-03-31

---

## 1. The Core Question: Why Four Orchestrators?

This demo answers **four "why" questions** that enterprise customers ask when evaluating Protegrity for AI/LLM pipelines:

### Why #1 — "Why does Protegrity work with *any* LLM pipeline?"

**Answer: The Direct orchestrator proves it.**

The Direct orchestrator is the simplest possible pipeline: user → Gate 1 → LLM → Gate 2 → response. No framework, no agents, no graph. This proves that Protegrity's dual-gate model is **framework-agnostic** — it works at the boundary, not inside the pipeline. Any LLM provider (OpenAI, Anthropic, Groq) works without modification.

### Why #2 — "Why does Protegrity scale to complex multi-step workflows?"

**Answer: The LangGraph orchestrator proves it.**

LangGraph builds a DAG (Directed Acyclic Graph) with discrete nodes for retrieval and LLM calls. Protegrity tokens flow through every node in the graph — KB retrieval, RAG search, Knowledge Graph queries, and the LLM — without ever materializing raw PII. Adding new nodes or edges doesn't weaken the protection. This proves Protegrity scales with workflow complexity.

### Why #3 — "Why does Protegrity work with multi-agent systems?"

**Answer: The CrewAI orchestrator proves it.**

CrewAI runs multiple specialized agents (Research Agent, Response Agent) that collaborate to answer queries. Each agent only ever sees tokenized data — the tokens are opaque across the entire crew. This proves that Protegrity maintains isolation even when **multiple AI agents** reason independently over shared protected data.

### Why #4 — "Why does Protegrity work with semantic retrieval (RAG)?"

**Answer: The LlamaIndex orchestrator proves it.**

LlamaIndex performs vector-based semantic search over ChromaDB, where all documents contain tokenized PII. Even at the **embedding layer** — where text is converted to numeric vectors — real PII is never exposed. This proves that Protegrity tokens survive the entire RAG pipeline: ingestion → embedding → search → retrieval → LLM context.

---

## 2. Architecture: Gates as Boundaries, Not Components

The key architectural decision: **Protegrity gates are the caller's responsibility, NOT the orchestrator's.**

```
┌─ TechnicalApp (app.py) ────────────────────────────────┐
│                                                         │
│  User Input                                             │
│      │                                                  │
│      ▼                                                  │
│  ╔═══════════════════════════════════╗                   │
│  ║  GATE 1 — Protegrity Input       ║  ← app.py        │
│  ║  Semantic Guardrail + Tokenize   ║                   │
│  ╚═══════════════════════════════════╝                   │
│      │ (tokenized message)                              │
│      ▼                                                  │
│  ┌─────────────────────────────────┐                    │
│  │  Data Source Retrieval          │  ← app.py          │
│  │  KB + RAG + KG (all tokenized) │                     │
│  │  register_tokens_from_context() │                    │
│  └─────────────────────────────────┘                    │
│      │ (tokenized context)                              │
│      ▼                                                  │
│  ┌─────────────────────────────────┐                    │
│  │  ORCHESTRATOR (pluggable)       │  ← orchestrators/  │
│  │  Direct / LangGraph / CrewAI /  │                    │
│  │  LlamaIndex                     │                    │
│  │                                 │                    │
│  │  Receives: tokenized message    │                    │
│  │           + tokenized context   │                    │
│  │  Returns:  tokenized answer     │                    │
│  │                                 │                    │
│  │  ⚠ NEVER sees real PII         │                    │
│  └─────────────────────────────────┘                    │
│      │ (tokenized response)                             │
│      ▼                                                  │
│  ╔═══════════════════════════════════╗                   │
│  ║  GATE 2 — Protegrity Output      ║  ← app.py        │
│  ║  Per-user detokenization         ║                   │
│  ╚═══════════════════════════════════╝                   │
│      │                                                  │
│      ▼                                                  │
│  Final Response (PII restored per policy)               │
└─────────────────────────────────────────────────────────┘
```

**Why this design?**
- Orchestrators are **pure "protected-in, protected-out" pipelines**
- Gate logic doesn't need to be duplicated in every framework
- Adding a new orchestrator requires **zero Protegrity code** — just implement `BaseOrchestrator.run()`
- The security boundary is in one place: `app.py`

---

## 3. The Four Orchestrators — Detailed Comparison

### 3.1 Direct Orchestrator

| Property | Value |
|----------|-------|
| **File** | `orchestrators/direct_orch.py` |
| **Library** | None (pure Python) |
| **Data Sources** | KB only |
| **Pipeline** | Context → LLM → Response |
| **Lines of code** | ~50 |

**How it works:**
```python
class DirectOrchestrator(BaseOrchestrator):
    def run(self, user_message, *, protected_context=None, **kw):
        system = SYSTEM_PROMPT
        if protected_context:
            system += f"\n\nCustomer Data:\n{protected_context}"

        messages = [{"role": "system", "content": system}]
        messages.append({"role": "user", "content": user_message})

        provider_fn = get_llm_provider()  # OpenAI / Anthropic / Groq
        raw = provider_fn(messages)

        return PipelineResult(answer=raw)
```

**Protegrity integration:** Zero — it just receives tokenized input and returns tokenized output. That's the point. Gates are invisible to the simplest pipeline.

---

### 3.2 LangGraph Orchestrator

| Property | Value |
|----------|-------|
| **File** | `orchestrators/langgraph_orch.py` |
| **Library** | `langgraph` (StateGraph) |
| **Data Sources** | KB + RAG + KG |
| **Pipeline** | retrieve → llm (DAG nodes) |
| **Lines of code** | ~110 |

**How it works:**
```python
class PipelineState(TypedDict, total=False):
    user_message: str
    customer_id: str
    protected_context: str
    kb_context: str
    llm_response: str
    answer: str

# Node 1: Retrieve tokenized context
def _node_retrieve(state):
    context = state.get("protected_context", "")
    if context:
        register_context_tokens(context)  # Register tokens for Gate 2
    return {"kb_context": context}

# Node 2: LLM call with tokenized context
def _node_llm(state):
    provider_fn = get_llm_provider()
    messages = [{"role": "system", "content": SYSTEM_PROMPT + context}]
    messages.append({"role": "user", "content": state["user_message"]})
    return {"answer": provider_fn(messages)}

# Graph: retrieve → llm → END
graph = StateGraph(PipelineState)
graph.add_node("retrieve", _node_retrieve)
graph.add_node("llm", _node_llm)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "llm")
graph.add_edge("llm", END)
```

**Protegrity integration:** `register_context_tokens()` is called in the retrieve node to register all `[TAG]token[/TAG]` patterns from the KB/RAG/KG context. This ensures Gate 2 can later detokenize any tokens the LLM echoes back. The graph itself never calls any Protegrity API — it only handles tokenized data.

**Why LangGraph?** Demonstrates that Protegrity tokens survive a **stateful DAG execution**. Each node receives and passes protected state. Adding new nodes (e.g., a compliance check node, an audit node) doesn't weaken the protection — tokens flow through cleanly.

---

### 3.3 CrewAI Orchestrator

| Property | Value |
|----------|-------|
| **File** | `orchestrators/crewai_orch.py` |
| **Library** | `crewai` (Agent, Task, Crew, Process) |
| **Data Sources** | KB + KG |
| **Pipeline** | Research Agent → Response Agent (sequential) |
| **Lines of code** | ~120 |

**How it works:**
```python
# Agent 1: Research Analyst
research_agent = Agent(
    role="Banking Research Analyst",
    goal="Retrieve relevant customer data from the knowledge base.",
    backstory="You have access to pre-protected customer records. "
              "All PII is tokenized — never attempt to decode tokens.",
)

# Agent 2: Customer Service Rep
response_agent = Agent(
    role="Customer Service Representative",
    goal="Answer the customer's banking question using tokenized data.",
    backstory=f"{system_context}\n\n"
              "You must preserve all [TAG]value[/TAG] tokens exactly as they appear.",
)

# Sequential execution: research → response
crew = Crew(
    agents=[research_agent, response_agent],
    tasks=[research_task, response_task],
    process=Process.sequential,
)
crew_output = crew.kickoff()
```

**Protegrity integration:** Agent backstories explicitly instruct agents that PII is tokenized and must not be decoded. `register_context_tokens()` is called before agents run. The agents' internal LLM calls use tokenized data throughout.

**Why CrewAI?** Demonstrates that Protegrity tokens remain opaque across **multi-agent collaboration**. The Research Agent finds tokenized data, passes it to the Response Agent, who formats it — neither ever sees real PII. This is critical for enterprise scenarios where different AI agents have different responsibilities.

**Fallback:** If CrewAI execution fails, automatically falls back to a direct LLM call with the same tokenized context.

---

### 3.4 LlamaIndex Orchestrator

| Property | Value |
|----------|-------|
| **File** | `orchestrators/llamaindex_orch.py` |
| **Library** | `llama-index-core`, `llama-index-llms-openai`, `llama-index-llms-anthropic` |
| **Data Sources** | KB + RAG |
| **Pipeline** | Retrieve → LlamaIndex native LLM chat |
| **Lines of code** | ~120 |

**How it works:**
```python
def _get_llama_llm():
    """LlamaIndex-native LLM adapters for each provider."""
    if provider == "openai":
        from llama_index.llms.openai import OpenAI as LlamaOpenAI
        return LlamaOpenAI(model=model, api_key=key)
    elif provider == "anthropic":
        from llama_index.llms.anthropic import Anthropic as LlamaAnthropic
        return LlamaAnthropic(model=model, api_key=key)
    elif provider == "groq":
        from llama_index.llms.openai_like import OpenAILike
        return OpenAILike(model=model, api_base="https://api.groq.com/openai/v1")

class LlamaIndexOrchestrator(BaseOrchestrator):
    def run(self, user_message, *, protected_context=None, **kw):
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=system + context)]
        messages.append(ChatMessage(role=MessageRole.USER, content=user_message))

        llm = _get_llama_llm()
        response = llm.chat(messages)
        return PipelineResult(answer=response.message.content)
```

**Protegrity integration:** Uses LlamaIndex's native `ChatMessage` format — the tokenized content is passed directly through LlamaIndex's message pipeline. `register_context_tokens()` is called before the LLM chat to register tokens for Gate 2.

**Why LlamaIndex?** Demonstrates that Protegrity tokens survive the **semantic retrieval pipeline**. ChromaDB stores pre-tokenized documents, computes embeddings over tokenized text, and retrieves relevant chunks — all without exposing real PII at the embedding layer. The LLM then reasons over tokenized context using LlamaIndex's native adapters.

---

## 4. Data Sources Per Orchestrator

Each orchestrator supports a specific combination of data sources, demonstrating different retrieval capabilities:

| Data Source | Direct | LangGraph | CrewAI | LlamaIndex |
|------------|--------|-----------|--------|------------|
| **KB** (Knowledge Base files) | ✅ | ✅ | ✅ | ✅ |
| **RAG** (ChromaDB vector search) | ❌ | ✅ | ❌ | ✅ |
| **KG** (Knowledge Graph - NetworkX) | ❌ | ✅ | ✅ | ❌ |

### KB — Pre-Protected Customer Profiles

```
banking_data/knowledge_base/CUST-100000.txt
```

Text files generated from `customers_protected.json`. All PII already tokenized:
```
Customer Profile: CUST-100000
Name: [PERSON]C4idPSY LLxx[/PERSON]
Email: [EMAIL_ADDRESS]gBlgez41oo3t@example.org[/EMAIL_ADDRESS]
Acct#: 9697354961 | Balance: $61,336.23
```

### RAG — ChromaDB Semantic Search

**File:** `common/rag_retriever.py`

ChromaDB indexes the same KB text files as vector embeddings. Queries use semantic similarity to find relevant customer data. **Customer isolation:** retrieval uses `where={"customer_id": customer_id}` metadata filter — a user's query can only retrieve their own data.

```python
results = retrieve(query, top_k=3, customer_id="CUST-100000")
# Returns tokenized document chunks matching the semantic query
```

### KG — Knowledge Graph (NetworkX)

**File:** `common/knowledge_graph.py`

A directed graph built from `customers_protected.json` with:
- **Node types:** Customer, Account, CreditCard, Loan, Transaction
- **Edge types:** HAS_ACCOUNT, HAS_CARD, HAS_LOAN, HAS_TRANSACTION, ACCOUNT_TRANSACTION
- **871 nodes, 1,625 edges** across 15 customers
- All PII fields in nodes are tokenized (names, emails, SSNs, etc.)

```python
kg_data = query_customer("CUST-100000")
# Returns customer node + all related accounts, cards, loans, transactions
```

---

## 5. Unified Interface — BaseOrchestrator

All four orchestrators implement the same abstract interface:

```python
class BaseOrchestrator(ABC):
    @abstractmethod
    def run(
        self,
        user_message: str,                              # Already tokenized by Gate 1
        *,
        customer_id: Optional[str] = None,              # For scoped retrieval
        conversation_history: Optional[List[Dict]] = None,
        protected_context: Optional[str] = None,        # Pre-loaded tokenized context
    ) -> PipelineResult:
        """Protected-in, protected-out pipeline."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable orchestrator name."""
        ...


@dataclass
class PipelineResult:
    answer: str                                         # Tokenized LLM response
    raw_llm_response: str = ""
    rag_context: List[Dict] = field(default_factory=list)
    kg_context: Dict = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""
    metadata: Dict = field(default_factory=dict)
```

### Factory Pattern

```python
# orchestrators/factory.py
def get_orchestrator() -> BaseOrchestrator:
    if ORCHESTRATOR == "direct":
        return DirectOrchestrator()
    elif ORCHESTRATOR == "langgraph":
        return LangGraphOrchestrator()
    elif ORCHESTRATOR == "crewai":
        return CrewAIOrchestrator()
    elif ORCHESTRATOR == "llamaindex":
        return LlamaIndexOrchestrator()
```

### Adding a New Orchestrator

To add a fifth orchestrator (e.g., AutoGen, Semantic Kernel):

1. Create `orchestrators/my_orch.py` implementing `BaseOrchestrator`
2. Add the case to `orchestrators/factory.py`
3. Add entry to `ORCHESTRATOR_INFO` in `TechnicalApp/app.py`
4. **No Protegrity code needed** — gates are handled by `app.py`

---

## 6. LLM Provider Layer

All orchestrators use the same pluggable LLM provider factory:

**File:** `llm_providers/factory.py`

```python
def get_llm() -> Callable[[List[Dict]], str]:
    """Returns: fn(messages) -> str"""
    if provider == "openai":    return _openai_llm(model)
    if provider == "anthropic": return _anthropic_llm(model)
    if provider == "groq":      return _groq_llm(model)
```

| Provider | Default Model | SDK |
|----------|--------------|-----|
| OpenAI | `gpt-4o-mini` | `openai` |
| Anthropic | `claude-sonnet-4-20250514` | `anthropic` |
| Groq | `llama-3.1-70b-versatile` | `groq` |

LlamaIndex uses its own native adapters (`llama_index.llms.openai`, etc.) instead of the shared factory, but supports the same three providers.

---

## 7. Runtime Configuration

Orchestrator and LLM settings are configurable at runtime via the TechnicalApp dashboard:

| Setting | Values | Where |
|---------|--------|-------|
| Orchestrator | direct, langgraph, crewai, llamaindex | Dashboard dropdown |
| LLM Provider | openai, anthropic, groq | Dashboard dropdown |
| LLM Model | Auto-selected per provider (or manual override) | Dashboard text field |
| Data sources | KB, RAG, KG (locked per orchestrator) | Dashboard toggles |

When the orchestrator changes:
1. Data source toggles auto-update and lock (e.g., Direct disables RAG/KG)
2. Server-side enforcement rejects disallowed data sources
3. The orchestrator factory creates the correct instance

When the LLM provider changes:
1. The model field auto-clears (picks provider default)
2. All orchestrators use the new provider on next request

---

## 8. How `app.py` Orchestrates the Full Pipeline

The unified flow in `get_llm_response()`:

```python
def get_llm_response(user_message, customer_id):
    # 1. Gate 1 — Protegrity tokenizes input
    gate1_result = guard.gate1_input(user_message, ...)
    protected_message = gate1_result.transformed_text

    # 2. Retrieve data sources (all tokenized)
    kb_context = KB_DIR / f"{customer_id}.txt"        # Pre-tokenized
    rag_context = retrieve(protected_message, ...)     # Tokenized search
    kg_context = query_customer(customer_id)           # Tokenized graph

    combined_context = join(kb, rag, kg)
    register_tokens_from_context(combined_context)     # For Gate 2

    # 3. Orchestrator — all go through same path
    history = get_or_create_history(session_key)
    history.add_user_message(protected_message)
    orch_result = _call_orchestrated(
        protected_message, customer_id, combined_context,
        conversation_history=history.get_messages(),
    )
    raw_response = orch_result["answer"]               # Still tokenized
    history.add_assistant_message(raw_response)

    # 4. Gate 2 — Protegrity detokenizes per user policy
    final = _user_unprotect(raw_response, protegrity_user)

    return {"response": final, "trace": trace}
```

**Key point:** Steps 1, 2, and 4 are identical regardless of which orchestrator runs in step 3. The orchestrator is a swappable black box that only handles tokenized data.

---

## 9. Pipeline Trace — Visibility into Each Step

Every chat request generates a detailed trace showing how data flows through the orchestrator:

```json
[
  {"step": "Gate 1 (Guardrail + Protect)", "risk_score": 0.15, "pii_elements": 2},
  {"step": "KB File Retrieval", "file": "CUST-100000.txt", "chars": 2284},
  {"step": "RAG (ChromaDB)", "results": 3, "context_chars": 1500},
  {"step": "Knowledge Graph", "graph_nodes": 871, "graph_edges": 1625},
  {"step": "Orchestrator (langgraph)", "provider": "openai", "model": "gpt-4o-mini",
   "context_sources": ["KB", "RAG", "KG"]},
  {"step": "Gate 2 (Unprotect as 'superuser')", "protegrity_user": "superuser"}
]
```

This trace is visible in the TechnicalApp chat UI, providing full transparency for demos.

---

## 10. Summary: What Each Orchestrator Proves

| Orchestrator | Framework | Protegrity Proof Point |
|-------------|-----------|----------------------|
| **Direct** | None | Gates work with any LLM — zero framework dependency |
| **LangGraph** | StateGraph DAG | Tokens survive stateful graph execution with multiple nodes |
| **CrewAI** | Multi-Agent | Tokens remain opaque across collaborating AI agents |
| **LlamaIndex** | RAG Pipeline | Tokens survive embedding, vector search, and retrieval |

**Bottom line:** Protegrity's dual-gate model is a **boundary concern**, not a pipeline concern. Regardless of how complex the orchestration becomes — DAGs, agents, RAG, knowledge graphs — PII never enters the pipeline in plain text, and it only exits through a policy-controlled gate.
