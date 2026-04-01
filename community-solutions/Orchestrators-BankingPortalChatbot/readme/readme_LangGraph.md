# Protegrity + LangGraph Integration

> Stateful, composable AI pipelines with data-centric PII governance

---

## The 4 Whys

### Why Change?

LangGraph lets teams build AI systems as **composable state machines** — graphs
where each node is a retrieval step, an LLM call, a tool invocation, or a
decision point. This is powerful, but it introduces a new class of risk.

**What is broken today:**

- **PII flows through every node unprotected.** In a LangGraph pipeline, the same
  customer data passes through retrieval nodes, prompt-building nodes, LLM nodes,
  and tool-calling nodes. Each node is a potential leak point — a logging statement,
  a tracing call, or a failed tool invocation can expose real PII.
- **State persistence stores raw PII.** LangGraph's state management means customer
  data lives in dictionaries that flow across the graph. If state is checkpointed,
  logged, or serialized for debugging, PII is captured in plain text.
- **Multi-source retrieval multiplies the attack surface.** LangGraph excels at
  combining Knowledge Bases, RAG vector stores, and Knowledge Graphs in a single
  pipeline. Each data source is a separate PII exposure point — and each requires
  its own protection strategy.
- **Conditional routing creates unpredictable data paths.** LangGraph's branching
  logic means PII can flow through different nodes depending on runtime conditions.
  Application-level security cannot cover every path.

The more composable the pipeline, the more places PII can leak.

---

### Why Now?

- **LangGraph is becoming the standard for production AI.** Teams are moving from
  simple chains to state machines that orchestrate multiple retrievers, tools, and
  LLMs. The complexity demands governance that scales with the graph.
- **Agentic AI amplifies the risk.** As LangGraph pipelines gain tool-calling
  capabilities — executing code, querying databases, calling APIs — a single leaked
  PII value can propagate across systems, not just within a chat response.
- **Observability tools capture everything.** LangSmith, LangFuse, and custom
  tracers record every node's input and output. Without data-level protection,
  observability becomes a PII logging system.
- **Regulatory auditors follow the data path.** Compliance is not "did the LLM
  see PII?" — it's "did any component in the pipeline see PII?" LangGraph's
  multi-node architecture means auditors have more components to inspect.

The shift from simple chains to stateful graphs makes application-level PII
controls insufficient. Protection must operate at the data level.

---

### Why Protegrity?

Protegrity's dual-gate architecture is **graph-native** — it wraps the entire
LangGraph pipeline, not individual nodes:

- **Tokenize once at the boundary, not at every node.** Gate 1 protects the input
  before it enters the graph. Every node — retrieve, LLM, tool — operates on
  tokenized data. No per-node protection logic needed.
- **State is always protected.** LangGraph's `PipelineState` dictionary carries
  only tokens. Checkpointing, tracing, and debugging never expose real PII —
  even if state is persisted to disk or sent to a monitoring service.
- **Multi-source retrieval stays safe.** KB files, ChromaDB vectors, and Knowledge
  Graph nodes are all pre-tokenized at ingestion time. The retrieval nodes return
  protected data by design — not by runtime enforcement.
- **Graph topology doesn't matter.** Whether the pipeline is linear (retrieve → LLM),
  branching (conditional routing), or cyclic (agent loops), the data flowing through
  is always tokenized. Protegrity's protection is topology-independent.
- **Gate 2 detokenizes once at the exit.** After the graph completes, a single
  unprotection step restores real values — controlled by user role and policy, not
  by which nodes executed.

---

### Why It Matters?

**If solved:** LangGraph becomes a **production-grade orchestration layer** for
sensitive data. Teams can build complex, multi-source, multi-step AI pipelines
without worrying about PII exposure at any node. Graph complexity becomes a
feature (better answers) rather than a liability (more leak points).

**If not solved:** Every LangGraph node is a potential compliance violation.
Organizations either simplify their graphs (losing the multi-source advantage)
or accept uncontrolled PII flow (creating audit failures). The more sophisticated
the pipeline, the greater the risk — which is the opposite of what teams need.

LangGraph's power is composability. Protegrity ensures that composability doesn't
compromise data governance.

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
│  │  LangGraphOrchestrator                    │                   │
│  │                                           │                   │
│  │  StateGraph(PipelineState)                │                   │
│  │                                           │                   │
│  │  ┌───────────┐      ┌───────────┐        │                   │
│  │  │  retrieve  │─────▶│    llm    │──▶ END │                   │
│  │  │           │      │           │        │                   │
│  │  │ • Load KB │      │ • Build   │        │                   │
│  │  │ • Query   │      │   prompt  │        │                   │
│  │  │   RAG     │      │ • Call    │        │                   │
│  │  │ • Query   │      │   LLM    │        │                   │
│  │  │   KG      │      │ • Return │        │                   │
│  │  │ • Register│      │   answer │        │                   │
│  │  │   tokens  │      │          │        │                   │
│  │  └───────────┘      └───────────┘        │                   │
│  │                                           │                   │
│  │  State flows through graph (all tokenized)│                   │
│  └──────────────────┬────────────────────────┘                   │
│                     │ raw_response (tokenized)                    │
│                     ▼                                             │
│  ┌───────────────────────────────────────────┐                   │
│  │  GATE 2 — Output Unprotection             │                   │
│  │  Detokenize per user role/policy          │                   │
│  └──────────────────┬────────────────────────┘                   │
│                     ▼                                             │
│              Final Response                                      │
└──────────────────────────────────────────────────────────────────┘
```

### LangGraph State Schema

```python
class PipelineState(TypedDict, total=False):
    user_message: str              # Protected query from Gate 1
    customer_id: str               # Customer identifier
    conversation_history: list     # Multi-turn context
    protected_context: str         # Pre-loaded tokenized KB data
    kb_context: str                # Retrieved KB content (tokenized)
    llm_response: str              # Raw LLM output (tokenized)
    answer: str                    # Final answer (still tokenized)
```

Every field in the state carries **only tokenized data**. If the state is logged,
checkpointed, or serialized, no real PII is exposed.

### Graph Nodes

**Node 1: `retrieve`** — Data source aggregation
- Loads pre-tokenized KB profile from `banking_data/{customer_id}.txt`
- Optionally queries ChromaDB (RAG) for semantic matches
- Optionally traverses Knowledge Graph for structured relationships
- Registers all context tokens with Gate 2's token map
- Output: `kb_context` (combined, tokenized context string)

**Node 2: `llm`** — LLM invocation
- Builds system prompt with tokenized context
- Appends conversation history for multi-turn support
- Calls LLM via provider factory (OpenAI / Anthropic / Groq)
- Output: `llm_response` and `answer` (both tokenized)

**Graph Edges:**
```
Entry → retrieve → llm → END
```

### Data Flow Example

```
User:     "What credit cards do I have?"

Gate 1:
  Guardrail  → risk_score=0.08, accepted
  Discovery  → no PII detected in query
  Protection → message unchanged (no PII to tokenize)

LangGraph StateGraph:
  ┌─ retrieve ──────────────────────────────────────────────────┐
  │ KB: Load CUST-100000.txt (pre-tokenized profile)           │
  │ RAG: ChromaDB search → 3 matching ticket chunks            │
  │ KG: NetworkX query → customer→credit_card relationships    │
  │ register_context_tokens(all_context)                       │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─ llm ──────────────────────────────────────────────────────┐
  │ System: "Banking assistant" + tokenized KB + RAG + KG       │
  │ LLM: "You have credit card [CREDIT_CARD]4000-0000-0000..."│
  └─────────────────────────────────────────────────────────────┘

Gate 2:
  Detokenize → "You have credit card 5833-1586-9235..."
```

### Data Sources

| Source | Supported | Description |
|---|---|---|
| **Knowledge Base (KB)** | ✅ | Pre-tokenized customer profiles |
| **RAG (ChromaDB)** | ✅ | Semantic vector search over ticket content |
| **Knowledge Graph** | ✅ | NetworkX graph traversal (customer → tickets → orders) |

LangGraph is the **only orchestrator** that supports all three data sources
simultaneously, making it the most comprehensive retrieval option.

### Key Implementation Details

- **Class:** `LangGraphOrchestrator` in `orchestrators/langgraph_orch.py`
- **Framework:** `langgraph.graph.StateGraph` with `TypedDict` state
- **Composable by design** — add new nodes (e.g., summarization, validation)
  by inserting them into the graph without modifying existing nodes
- **Token registration** happens in the retrieve node, ensuring Gate 2 can
  resolve all tokens seen in KB, RAG, and KG context
- **All state is protected** — no real PII in any `PipelineState` field at any point

### When to Use LangGraph

- **Multi-source retrieval** — combine KB, RAG, and KG for comprehensive answers
- **Complex pipelines** — add validation, summarization, or routing nodes
- **Auditability** — LangGraph's state tracing shows exactly what each node processed
- **Production scaling** — composable architecture adapts as requirements grow
