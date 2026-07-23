# Phase02/01_RAG_Architecture.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Core Requirements & Philosophy](#2-core-requirements--philosophy)
3. [Overall Architecture](#3-overall-architecture)
4. [Ingestion Pipeline](#4-ingestion-pipeline)
5. [Retrieval Pipeline](#5-retrieval-pipeline)
6. [Components & Responsibilities](#6-components--responsibilities)
7. [Interfaces & Data Models](#7-interfaces--data-models)
8. [Failure Recovery & Graceful Degradation](#8-failure-recovery--graceful-degradation)
9. [Caching & Performance Optimization](#9-caching--performance-optimization)
10. [Scalability & Future Extensions](#10-scalability--future-extensions)
11. [Tradeoffs](#11-tradeoffs)

---

# 1. Executive Summary

This document defines the architecture for the Retrieval-Augmented Generation (RAG) Engine (Module 3) of the DSA Educational Pipeline. The RAG subsystem enriches raw LeetCode problems with deep, curated algorithmic knowledge (complexity analysis, pattern templates, edge cases, visual explanation guidelines) to ensure the Script Generator produces highly accurate and educational content. 

The system leverages **LlamaIndex** as the orchestration framework, **ChromaDB** for local, offline-first vector storage, and **Gemini Embeddings** for high-dimensional semantic search.

---

# 2. Core Requirements & Philosophy

- **Educational First:** The knowledge base must ground the LLM, preventing hallucinations regarding time/space complexity, optimal patterns, and edge cases.
- **Offline-First Vector Store:** Once indexed, the vector database must live entirely on the local filesystem (`data/chroma_db`), eliminating network latency during retrieval (excluding the embedding API call).
- **Interchangeable LLM Foundation:** While Gemini Embeddings are used initially, the LlamaIndex orchestration must abstract the embedding model, allowing future swaps to local open-source embeddings (e.g., HuggingFace `all-MiniLM-L6-v2`) or other providers without rewriting the retrieval logic.
- **Performance:** Retrieval latency must remain strictly under 2.0 seconds.

---

# 3. Overall Architecture

The RAG architecture is divided into two distinct lifecycles: **Asynchronous Ingestion** (performed by a developer/cron job) and **Synchronous Retrieval** (performed dynamically during the pipeline run).

```mermaid
graph TD
    subgraph Ingestion Pipeline (Offline)
        A[Markdown Knowledge Base] --> B[LlamaIndex DirectoryReader]
        B --> C[Node Parser / Chunker]
        C --> D[Gemini Embedding Model]
        D --> E[(Local ChromaDB)]
    end

    subgraph Retrieval Pipeline (Runtime)
        F[Orchestrator] --> G[RAG Engine]
        G --> H[Query Generator]
        H --> I[Gemini Embedding Model]
        I --> J[(Local ChromaDB)]
        J --> K[Post-Processor / Reranker]
        K --> L[RAGContext Output]
        L --> M[Script Generator]
    end
```

---

# 4. Ingestion Pipeline

The ingestion pipeline builds the brain of the educational AI. It is executed out-of-band (e.g., `python -m src.rag.ingest`).

1. **Source Material:** High-quality Markdown files stored in `data/knowledge_base/`. Files are structured by category (e.g., `patterns/sliding_window.md`, `complexities/amortized_analysis.md`, `visualizations/linked_list_pointers.md`).
2. **Chunking Strategy:** 
   - Uses `MarkdownNodeParser` from LlamaIndex to split documents structurally by headers (`#`, `##`, `###`) rather than naive character counts. This preserves the semantic context of a specific algorithm section.
3. **Embedding:** `GoogleGenAIEmbedding` converts text chunks into vector representations.
4. **Storage:** Stored persistently in a local `chromadb.PersistentClient`.

---

# 5. Retrieval Pipeline

At runtime, the `RAGEngine` is invoked by the Pipeline Orchestrator to fetch context for a specific LeetCode problem.

1. **Query Construction:** The engine takes the `ScrapedProblem` and the `TagKnowledge` (from M2) to formulate a synthetic search query.
   *Example Query:* `"Explain the optimal sliding window approach for longest substring without repeating characters, including time complexity and edge cases."*
2. **Vector Retrieval:** LlamaIndex queries the local ChromaDB using `similarity_top_k=5`.
3. **Metadata Filtering:** (Future) Pre-filter nodes by category (e.g., `category="algorithm_pattern"`) based on `TagKnowledge`.
4. **Formatting:** The retrieved `NodeWithScore` objects are mapped into the canonical `RAGContext` dataclass.

---

# 6. Components & Responsibilities

| Component | Technology | Responsibility |
|---|---|---|
| **Document Reader** | `SimpleDirectoryReader` | Ingests Markdown files, extracting metadata (file name, topic). |
| **Node Parser** | `MarkdownNodeParser` | Splits documents by headers to maintain educational context boundaries. |
| **Embedder** | `GoogleGenAIEmbedding` | Translates queries and nodes into vectors. Wrapped by LlamaIndex's `BaseEmbedding`. |
| **Vector Store** | `ChromaVectorStore` | Local SQLite/Parquet persistence of embeddings (`data/chromadb`). |
| **Query Engine** | `VectorStoreIndex.as_retriever` | Performs cosine similarity search. |
| **RAG Service** | Custom Python Class | Maps the LlamaIndex abstractions to the project's strict `RAGEngineProtocol`. |

---

# 7. Interfaces & Data Models

### 7.1 Configuration
```python
@dataclass(frozen=True)
class RAGConfig:
    knowledge_base_dir: Path
    chroma_db_dir: Path
    embedding_model: str = "models/text-embedding-004"
    top_k: int = 3
    similarity_threshold: float = 0.75
```

### 7.2 Core Interface (`RAGEngineProtocol`)
```python
def retrieve(self, problem: ScrapedProblem, tags: TagKnowledge) -> RAGContext:
    """Retrieve relevant educational context based on problem and tags."""
    
def index_knowledge_base(self) -> int:
    """Wipe and rebuild the local ChromaDB index. Returns chunks indexed."""
```

---

# 8. Failure Recovery & Graceful Degradation

The RAG module is classified as **Non-Critical**. If retrieval fails, the pipeline must proceed.

### 8.1 Fallback Strategy
If `IndexNotFoundError`, `EmbeddingError`, or network timeout occurs:
1. The `RAGEngine` catches the library exception and raises a `RAGError` (which inherits from `NonCriticalError`).
2. The Orchestrator catches `NonCriticalError`.
3. The Orchestrator calls the Null Object factory: `RAGContext.empty()`.
4. The Script Generator proceeds using only the LLM's intrinsic knowledge.

### 8.2 Missing ChromaDB
If the local `chroma_db` directory does not exist at startup, the Orchestrator should log a `WARNING` but should **not** automatically trigger `index_knowledge_base()` during a batch run, as ingestion takes time and uses API quota. The run degrades gracefully.

---

# 9. Caching & Performance Optimization

### 9.1 Embedding Cache
LlamaIndex's `IngestionCache` (backed by a local Key-Value store) is utilized during the `index_knowledge_base` step to prevent re-embedding Markdown files that have not changed since the last build.

### 9.2 Retrieval Latency
Because ChromaDB is local, the only network latency is the Gemini Embedding API call for the single search query (~200ms). The overall `retrieve` method will consistently execute in `< 500ms`.

---

# 10. Scalability & Future Extensions

### 10.1 Future Interactivity (Chatbot / Q&A)
By using LlamaIndex, the architecture seamlessly supports transitioning from a strict `Retriever` to a `ChatEngine`. In the future, a viewer could ask, *"Why didn't we use a hash map here?"* The `ChatEngine` would use the existing ChromaDB index + conversation history to generate a response.

### 10.2 Local Embeddings (Cost Optimization)
The architecture abstracts the embedder. Scaling to 10,000+ chunks can be made entirely free by swapping `GoogleGenAIEmbedding` for `HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")`, running locally on the CPU/NPU.

### 10.3 Hybrid Search
Currently, retrieval relies solely on dense vector similarity. Future versions can easily adopt BM25 sparse retrieval (Keyword search) + Vector Search, combined using a Reciprocal Rank Fusion (RRF) reranker to ensure highly specific terms (e.g., "KMP Algorithm") are matched accurately.

---

# 11. Tradeoffs

| Decision | Alternative Considered | Rationale |
|---|---|---|
| **ChromaDB (Local)** | Pinecone / Qdrant (Cloud) | Ensures the pipeline can run entirely offline (once local LLMs are swapped in) without cloud vector DB costs or latency. |
| **LlamaIndex** | LangChain / Custom NumPy | LlamaIndex is purpose-built for RAG and data ingestion, offering superior `NodeParsers` (like Markdown parsing) out-of-the-box compared to LangChain's generic text splitters. |
| **Markdown Source** | PDF / HTML | Markdown is native to developers, easily version-controlled in Git, and trivially parsed into semantic chunks based on headers. |
| **Synchronous Retrieval**| Async Retrieval | Matches the global architectural rule of the pipeline. Eliminates `asyncio` complexity for a batch process where parallelizing a 300ms call yields negligible pipeline benefits. |
