"""
Comprehensive Test Suite for RAG Runtime Platform.

Tests Chunking bounds, Routing isolation, Semantic Cache hits,
and the physical mathematical assembly of Contexts.
"""

import time
import pytest

from src.core.rag.cache import RAGCache
from src.core.rag.chunker import ChunkingEngine
from src.core.rag.context_builder import ContextBuilder
from src.core.rag.evaluator import RAGEvaluator
from src.core.rag.query_planner import QueryPlanner, RetrievalStrategy
from src.core.rag.reranker import RerankingService
from src.core.rag.retriever import RetrievedContext


# ---------------------------------------------------------
# Fixtures & Environment Setup
# ---------------------------------------------------------
@pytest.fixture
def chunker():
    return ChunkingEngine(max_tokens=50, overlap_tokens=10)

@pytest.fixture
def cache():
    # Fast 1-second TTL specifically for testing evictions
    return RAGCache(default_ttl_seconds=1)

@pytest.fixture
def planner():
    return QueryPlanner()

@pytest.fixture
def context_builder():
    # Strict 100 token budget to forcefully test context truncation
    return ContextBuilder(max_context_tokens=100)

@pytest.fixture
def reranker():
    return RerankingService(use_cross_encoder=False)


# ---------------------------------------------------------
# Chunking Engine (Code Parsing & Overlap)
# ---------------------------------------------------------
def test_chunker_code_block_isolation(chunker):
    """Proves regex strictly isolates physical Python blocks from Markdown prose."""
    text = "Here is Dijkstra:\n```python\ndef dijkstra():\n    pass\n```\nAnd it's O(V^2)."
    chunks = chunker.chunk_document("doc1", text, {})
    
    # Expected: [Prose Chunk], [Code Chunk], [Prose Chunk]
    assert len(chunks) == 3
    assert chunks[1].is_code_block is True
    assert chunks[1].metadata["language"] == "python"
    assert chunks[0].is_code_block is False
    assert chunks[2].is_code_block is False


def test_chunker_adaptive_overlap(chunker):
    """Proves the sliding window successfully duplicates tail tokens into the next chunk."""
    # Build a raw text string that's roughly 100 tokens long (400 chars)
    text = "A" * 200 + "\n\n" + "B" * 200
    chunks = chunker.chunk_document("doc2", text, {})
    
    # Chunking splits at the \n\n breakpoint. 
    # But overlap logic must strictly prepend the tail of Chunk 1 to Chunk 2.
    assert len(chunks) == 2
    assert "A" * 40 in chunks[1].text_content # Overlap boundary carried over


# ---------------------------------------------------------
# Query Planner (Intent Pre-Processor)
# ---------------------------------------------------------
def test_query_planner_hybrid_detection(planner):
    """Proves the planner forces heavy Cross-Encoder compute on 'optimal' intent."""
    plan = planner.plan("What is the optimal time complexity of Two Sum?")
    
    assert plan.suggested_strategy == RetrievalStrategy.HYBRID_DEEP
    assert plan.require_cross_encoder is True
    assert plan.detected_intent == "optimization"


# ---------------------------------------------------------
# RAG Caching Layer
# ---------------------------------------------------------
def test_cache_hits_and_evictions(cache):
    """Proves the cache hashes complex DB payloads and respects physical TTL limits."""
    payload = {"vector": [0.1, 0.2]}
    cache.set("algorithms", "embed", "my_query", payload)
    
    # 1. Immediate fetch should result in a Cache HIT
    assert cache.get("algorithms", "embed", "my_query") == payload
    
    # 2. Halt execution to let the physical TTL (1 sec) expire
    time.sleep(1.1)
    
    # 3. Fetch should now result in a MISS (Eviction)
    assert cache.get("algorithms", "embed", "my_query") is None
    
    # 4. Verify Prometheus Telemetry
    metrics = cache.get_metrics()
    assert metrics["hits"] == 1
    assert metrics["evictions"] == 1


# ---------------------------------------------------------
# Context Builder (Safety Boundaries & Organization)
# ---------------------------------------------------------
def test_context_builder_budget_truncation(context_builder):
    """Proves Context Builder physically halts assembly if LLM API limits are breached."""
    chunks = [
        RetrievedContext("c1", 0.9, {"text_content": "A" * 200, "is_code": "false"}), # 50 tokens
        RetrievedContext("c2", 0.8, {"text_content": "B" * 300, "is_code": "false"}), # 75 tokens
        RetrievedContext("c3", 0.7, {"text_content": "C" * 100, "is_code": "true"})   # 25 tokens
    ]
    
    # Budget is 100. Chunk 1 + Chunk 2 = 125 tokens.
    # Therefore, Chunk 2 and Chunk 3 MUST be completely truncated to avoid a 400 Bad Request.
    result = context_builder.build_context(chunks, "test_query")
    
    assert "A" * 200 in result
    assert "B" * 300 not in result
    assert "C" * 100 not in result


def test_context_builder_pedagogical_ordering(context_builder):
    """Proves Python Code chunks are aggressively pushed to the bottom of the Prompt."""
    chunks = [
        RetrievedContext("c1", 0.9, {"text_content": "def main():", "is_code": "true"}),
        RetrievedContext("c2", 0.8, {"text_content": "Theory goes here.", "is_code": "false"})
    ]
    
    result = context_builder.build_context(chunks, "test_query")
    
    # Theory MUST appear before the def main block to prevent LLM confusion
    assert result.index("Theory goes here.") < result.index("def main():")


# ---------------------------------------------------------
# Reranking Service
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_reranker_difficulty_penalty(reranker):
    """Proves the Reranker mathematically buries Hard topics for Beginner videos."""
    chunks = [
        RetrievedContext("c1", 0.9, {"educational_level": "Advanced"}),
        RetrievedContext("c2", 0.8, {"educational_level": "Beginner"})
    ]
    
    # If the user is a Beginner, the Advanced chunk (0.9) must be physically penalized 
    # by a massive 40% (0.9 * 0.60 = 0.54). The Beginner chunk (0.8) wins.
    reranked = await reranker.rerank("query", chunks, "Beginner")
    
    assert reranked[0].chunk_id == "c2"
    assert reranked[1].chunk_id == "c1"


# ---------------------------------------------------------
# RAG Evaluator (MRR Math)
# ---------------------------------------------------------
def test_evaluator_mrr_calculation():
    """Proves Mean Reciprocal Rank correctly scores physical DB retrieval positions."""
    evaluator = RAGEvaluator()
    
    expected = ["chunk_a", "chunk_b"]
    
    # Perfect Retrieval (Index 0) -> MRR = 1.0
    res_perfect = evaluator.evaluate_retrieval(expected, ["chunk_a", "chunk_c"], 10)
    assert res_perfect["mrr"] == 1.0
    
    # Poor Retrieval (Index 2) -> MRR = 1/3 = 0.333
    res_poor = evaluator.evaluate_retrieval(expected, ["chunk_x", "chunk_y", "chunk_b"], 10)
    assert res_poor["mrr"] == 0.333
    
    # Total Failure -> MRR = 0.0
    res_fail = evaluator.evaluate_retrieval(expected, ["chunk_x", "chunk_y"], 10)
    assert res_fail["mrr"] == 0.0
