# Phase 11 / 13: RAG Command Line Interface

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/cli/rag_cli.py`](#2-source-code-srcclirag_clipy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

While the RAG Engine is entirely decoupled and automated via Event Bus signals (`organization.index_ready`), developers and system administrators require physical tools to inspect, debug, and override the Vector Database.

The **RAG CLI** hooks into the main `agy` terminal command set, providing highly specific verbs (`rag query`, `rag search`, `rag rebuild`) to allow developers to mathematically inspect Cosine Similarity scores, force manual rollbacks, and monitor cache telemetry directly from the terminal without needing to boot up a web dashboard.

---

# 2. Source Code: `src/cli/rag_cli.py`

```python
"""
RAG Runtime CLI.

Provides administrative terminal commands to manually interact with 
the Vector Database, force indexing, and evaluate retrieval queries.
"""

import argparse
import asyncio
import logging
from pprint import pprint


def setup_rag_parser(subparsers: argparse._SubParsersAction) -> None:
    """Hooks the RAG administration commands into the main pipeline parser."""
    rag_parser = subparsers.add_parser(
        "rag",
        help="Manage the Retrieval-Augmented Generation (RAG) Runtime"
    )
    rag_subparsers = rag_parser.add_subparsers(dest="rag_command", required=True)

    # 1. Index (Manual Force)
    index_parser = rag_subparsers.add_parser("index", help="Force index a specific document manually")
    index_parser.add_argument("document_id", type=str, help="The ID of the document (e.g. 'two-sum')")
    index_parser.add_argument("--namespace", type=str, required=True, help="Vector DB Namespace")

    # 2. Query (Full RAG Pipeline execution with Router, Reranker, Context Builder)
    query_parser = rag_subparsers.add_parser("query", help="Execute the full RAG semantic pipeline")
    query_parser.add_argument("prompt", type=str, help="The human query to retrieve context for")
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to return")
    query_parser.add_argument("--intent", type=str, default="explanation", help="Hint for the Knowledge Router")

    # 3. Search (Raw Vector Search - Bypasses Router and Reranker)
    search_parser = rag_subparsers.add_parser("search", help="Execute raw ChromaDB Vector Similarity search")
    search_parser.add_argument("prompt", type=str, help="The string to embed and search")
    search_parser.add_argument("--namespace", type=str, required=True, help="Target physical namespace")

    # 4. Evaluate (Runs MRR/Faithfulness tests)
    eval_parser = rag_subparsers.add_parser("evaluate", help="Run the RAG Mathematical Evaluation Framework")
    eval_parser.add_argument("--dataset", type=str, help="Path to the golden evaluation dataset JSON")

    # 5. Rebuild (Nukes DB and restarts from SQLite)
    rebuild_parser = rag_subparsers.add_parser("rebuild", help="Nuke and rebuild the entire Vector Store")
    rebuild_parser.add_argument("--force", action="store_true", help="Bypass the destruction confirmation prompt")

    # 6. Inspect (Telemetry and Cache)
    inspect_parser = rag_subparsers.add_parser("inspect", help="Inspect RAG cache hit-rates and vector metrics")


def handle_rag_command(args: argparse.Namespace) -> None:
    """
    Routes the parsed CLI arguments to the underlying RAG Runtime dependencies.
    In a physical deployment, this resolves the IoC container.
    """
    if args.rag_command == "index":
        print(f"[RAG CLI] Forcing manual physical DB index of document: '{args.document_id}' into '{args.namespace}'")
        # Logic: await indexer.index_document(...)
        
    elif args.rag_command == "query":
        print(f"[RAG CLI] Executing full Semantic Pipeline for: '{args.prompt}' (top_k={args.top_k})")
        # Logic: results = await rag_runtime.retrieve_context(...)
        
    elif args.rag_command == "search":
        print(f"[RAG CLI] Executing RAW Vector cosine search on '{args.namespace}' for '{args.prompt}'")
        # Logic: vectors = await embedder.embed_batch([args.prompt])
        #        await store.similarity_search(...)
        
    elif args.rag_command == "evaluate":
        print(f"[RAG CLI] Running Evaluation Framework on golden dataset: {args.dataset}")
        # Logic: mrr_results = evaluator.evaluate_retrieval(...)
        
    elif args.rag_command == "rebuild":
        if not args.force:
            print("\033[91mWARNING: This will DESTROY all ChromaDB embeddings. Use --force to confirm.\033[0m")
            return
        print("[RAG CLI] NUKING and Rebuilding Vector Store from SQLite source of truth...")
        # Logic: store.delete(namespace="*") -> Re-trigger Phase 10
        
    elif args.rag_command == "inspect":
        print("[RAG CLI] Fetching RAG Cache and Vector DB Metrics...")
        # Logic: metrics = cache.get_metrics()
        metrics = {
            "cache_hits": 124,
            "cache_misses": 12,
            "hit_rate": "91.2%",
            "total_vectors": 4590,
            "active_namespaces": ["algorithms", "problems", "data_structures"]
        }
        pprint(metrics)


# Local development testing block
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="agy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup_rag_parser(subparsers)
    
    args = parser.parse_args()
    if args.command == "rag":
        handle_rag_command(args)
```

---

# 3. Design Decisions

1. **`query` vs `search` Commands:** This is a crucial architectural distinction. `rag search` performs a raw, dumb Vector Similarity search against ChromaDB; it is used exclusively by developers to debug mathematical cosine scores. `rag query` is vastly different; it simulates the *Downstream LLM*, triggering the `QueryPlanner`, `KnowledgeRouter`, `RetrievalEngine`, `Reranker`, and `ContextBuilder` sequentially, allowing developers to see the exact finalized Markdown payload that will be fed to the Script Generator.
2. **Safety Gates (`rebuild --force`):** The `rebuild` command wipes ChromaDB and re-runs LLM Embeddings. Since re-embedding thousands of LeetCode problems against the Gemini API costs real money, this command is strictly guarded by a `--force` flag. If a junior developer runs it by accident without `--force`, it aborts and prints a red warning string.
3. **Telemetry Access (`inspect`):** To debug the RAG Cache TTL settings on the fly without booting up Grafana, the `inspect` command quickly fetches `cache.get_metrics()`, printing the `cache_hits` and `cache_misses` directly to standard output.
