# Protegrity + LlamaIndex Integration

> Native RAG pipelines with data-centric PII protection at every layer

---

## The 4 Whys

### Why Change?

LlamaIndex is the leading framework for **Retrieval-Augmented Generation** (RAG) —
connecting LLMs to external data through indexes, retrievers, and query engines.
Organizations use it to make LLMs answer questions about their own data: customer
records, transaction histories, internal documents. But every piece of data
LlamaIndex retrieves and feeds to the LLM is a potential PII exposure.

**What is broken today:**

- **Indexes store raw PII.** LlamaIndex builds vector indexes (ChromaDB, Pinecone,
  Weaviate) by embedding document chunks. When those chunks contain customer names,
  emails, and account numbers, the vector store becomes a PII database — searchable
  by anyone with API access, with no access controls or encryption of the embedded
  content.
- **Retrieval returns unprotected context.** When a query engine retrieves the top-k
  matching chunks, those chunks contain real PII that gets injected directly into
  the LLM prompt as context. The retrieval step is the largest PII leak vector in
  any RAG pipeline.
- **Query engines have no data governance.** LlamaIndex query engines compose
  retrieval, synthesis, and response into a single pipeline. There is no built-in
  mechanism to classify PII in retrieved documents, redact sensitive fields, or
  enforce access policies based on the requesting user's role.
- **Embeddings encode PII semantics.** Vector embeddings of documents containing
  PII encode the semantic meaning of that PII. While not directly readable,
  embedding inversion attacks can reconstruct personal information from vectors —
  meaning even the embedding layer is an exposure risk.
- **Multi-index queries spread PII further.** LlamaIndex's composable indexes
  (sub-indexes, routers, knowledge graphs) mean PII can flow through multiple
  index layers, each with its own storage backend, each a separate attack surface.

RAG makes LLMs smarter by giving them access to private data. Without protection,
that private data becomes the LLM's most vulnerable asset.

---

### Why Now?

- **RAG is the dominant enterprise AI pattern.** Organizations have moved past
  prompt engineering — RAG is how they make LLMs useful on proprietary data. Every
  enterprise RAG deployment processes sensitive information.
- **Vector databases are scaling fast.** Production RAG systems now index millions
  of documents. A data breach of an unprotected vector store doesn't leak one
  customer's data — it leaks every customer's data in the corpus.
- **Compliance frameworks are catching up.** GDPR's "right to be forgotten"
  applies to vector stores too. If a customer requests data deletion, can you
  remove their PII from every embedding, every chunk, every cached retrieval
  result? Without tokenization at ingestion, the answer is no.
- **Hybrid search amplifies exposure.** Modern RAG combines vector search with
  keyword search, knowledge graphs, and structured queries. Each search method
  returns PII from a different angle — increasing the volume of sensitive data
  injected into each LLM prompt.

The more data RAG retrieves, the more PII it exposes. Protection must scale
with the retrieval pipeline.

---

### Why Protegrity?

Protegrity addresses the RAG PII problem at every layer — **ingestion, storage,
retrieval, and generation**:

- **Tokenize at ingestion, not at query time.** Customer profiles, tickets, and
  documents are tokenized before they are embedded and indexed. The vector store
  never contains real PII — only Protegrity tokens. This eliminates the storage
  and embedding exposure risks entirely.
- **Retrieval returns tokens, not PII.** When LlamaIndex retrieves the top-k
  chunks, those chunks contain `[PERSON]Xk9mP QwrTz[/PERSON]` instead of
  "John Smith". The LLM prompt context is protected by default.
- **LlamaIndex-native LLM adapters preserve tokens.** The orchestrator uses
  LlamaIndex's own LLM interfaces (`llama_index.llms.openai.OpenAI`,
  `llama_index.llms.anthropic.Anthropic`) to ensure the LLM call goes through
  LlamaIndex's message handling — and the tokenized context flows through
  unchanged.
- **Gate 2 detokenizes per policy.** After the LLM generates a response with
  embedded tokens, Gate 2 restores real values based on the requesting user's
  role. A `superuser` sees full PII; a `Marketing` user sees redacted fields.
  The RAG pipeline doesn't need to implement access control — Protegrity handles it.
- **Vector store breaches expose nothing.** If the ChromaDB or any vector store
  is compromised, attackers find only Protegrity tokens — meaningless strings
  that cannot be reversed without Protegrity's key management.

---

### Why It Matters?

**If solved:** RAG becomes the safe default for enterprise AI. Organizations can
index their most sensitive data — customer records, financial transactions, medical
histories — knowing that the vector store, the retrieval results, and the LLM
prompt all contain only tokens. RAG's promise of "LLMs that know your data" is
fulfilled without the risk of "LLMs that leak your data."

**If not solved:** Every RAG deployment is a data breach waiting to happen. The
vector store is an unencrypted copy of every sensitive document. Every retrieval
result is a PII injection into a third-party LLM. Organizations either avoid
indexing sensitive data (making RAG useless for high-value use cases) or accept
systemic PII exposure (making RAG a compliance liability that grows with every
document indexed).

LlamaIndex turns data into intelligence. Protegrity ensures that intelligence
doesn't come at the cost of data privacy.

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
│  │  LlamaIndexOrchestrator                   │                   │
│  │                                           │                   │
│  │  1. Load KB context (tokenized)           │                   │
│  │  2. Register tokens for Gate 2            │                   │
│  │  3. Build LlamaIndex ChatMessage array    │                   │
│  │     ┌─────────────────────────────┐       │                   │
│  │     │ SystemMessage:              │       │                   │
│  │     │   System prompt +           │       │                   │
│  │     │   tokenized KB context      │       │                   │
│  │     ├─────────────────────────────┤       │                   │
│  │     │ History messages            │       │                   │
│  │     ├─────────────────────────────┤       │                   │
│  │     │ UserMessage:                │       │                   │
│  │     │   protected_message         │       │                   │
│  │     └─────────────────────────────┘       │                   │
│  │  4. LlamaIndex LLM.chat(messages)         │                   │
│  │     ┌─────────────────────────────┐       │                   │
│  │     │ Provider-native adapter:    │       │                   │
│  │     │  • OpenAI (gpt-4o-mini)     │       │                   │
│  │     │  • Anthropic (claude-sonnet)│       │                   │
│  │     │  • Groq (llama-3.1-70b)     │       │                   │
│  │     └─────────────────────────────┘       │                   │
│  │  5. Return tokenized response             │                   │
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

### LlamaIndex LLM Adapter Factory

The orchestrator uses LlamaIndex's **native LLM adapters** — not generic HTTP
calls — ensuring provider-specific optimizations and message handling:

| Provider | LlamaIndex Class | Model |
|---|---|---|
| OpenAI | `llama_index.llms.openai.OpenAI` | `gpt-4o-mini` |
| Anthropic | `llama_index.llms.anthropic.Anthropic` | `claude-sonnet-4` |
| Groq | `llama_index.llms.openai_like.OpenAILike` | `llama-3.1-70b-versatile` |

All adapters use `temperature=0.3` and `max_tokens=1024` for banking context.

### Data Flow Example

```
User:     "Give me details about credit card 583315869235"

Gate 1:
  Guardrail  → risk_score=0.10, accepted
  Discovery  → CREDIT_CARD detected: "583315869235" (confidence=0.95)
  Protection → tokenized: "[CREDIT_CARD]4000-0000-0000-0000[/CREDIT_CARD]"

Protected message:
  "Give me details about credit card [CREDIT_CARD]4000-0000-0000-0000[/CREDIT_CARD]"

LlamaIndex Orchestrator:
  1. Load KB: CUST-100000.txt (all PII pre-tokenized)
  2. Register tokens: token map updated for Gate 2 resolution
  3. Build messages:
     System: "You are a banking assistant..." + tokenized profile
     User: "Give me details about credit card [CREDIT_CARD]4000..."
  4. LLM call: llama_index.llms.openai.OpenAI.chat(messages)
  5. Response: "Credit card [CREDIT_CARD]4000-0000-0000-0000[/CREDIT_CARD]
               belonging to [PERSON]Xk9mP QwrTz[/PERSON], status: active..."

Gate 2:
  Detokenize → "Credit card 583315869235 belonging to John Smith,
                status: active..."
```

### Data Sources

| Source | Supported | Description |
|---|---|---|
| **Knowledge Base (KB)** | ✅ | Pre-tokenized customer profiles |
| **RAG (ChromaDB)** | ✅ | Semantic vector search (pre-tokenized documents) |
| **Knowledge Graph** | ❌ | Not integrated — use LangGraph for graph queries |

### Key Implementation Details

- **Class:** `LlamaIndexOrchestrator` in `orchestrators/llamaindex_orch.py`
- **Framework:** `llama_index.core` with native `ChatMessage` / `MessageRole` types
- **Provider-native adapters** — each LLM provider uses its own LlamaIndex class,
  not a generic wrapper. This ensures proper tokenization, message formatting,
  and error handling per provider.
- **Groq via OpenAI-compatible endpoint** — uses `OpenAILike` with Groq's
  `api_base="https://api.groq.com/openai/v1"` for seamless integration
- **Token registration** before LLM call ensures Gate 2 can resolve all tokens
  present in the KB context
- **Error handling** — if the LLM call fails, returns an error message instead
  of crashing the pipeline
- **Conversation history** supported via LlamaIndex `ChatMessage` array with
  proper role mapping (`USER`, `ASSISTANT`, skips `SYSTEM`)

### When to Use LlamaIndex

- **RAG-first use cases** — when semantic search over documents is the primary
  retrieval strategy
- **Provider-native features** — leverage LlamaIndex's per-provider optimizations
  (streaming, function calling, structured output)
- **Teams familiar with LlamaIndex** — use existing LlamaIndex skills, indexes,
  and query patterns
- **Document-heavy workloads** — when the knowledge base is large and benefits
  from vector search over simple file lookup
