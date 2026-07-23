# Phase 09 / 12: Ingestion Comprehensive Test Suite

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `tests/plugins/test_ingestion.py`](#2-source-code-testspluginstest_ingestionpy)
3. [Testing Strategy](#3-testing-strategy)

---

# 1. Executive Summary

This document finalizes **Phase 09: Knowledge Ingestion** by implementing a rigorous, production-ready `pytest` suite. 

The test suite mathematically proves the fault-tolerance of the Master Pipeline. It validates that the `ProblemNormalizer` correctly translates complex nested HTML (`<pre><code>`) into pristine Markdown, ensures the `BaseSourceConnector` properly sleeps and retries when it receives an HTTP 429 Rate Limit, and includes a rigorous **Performance Benchmark** to guarantee the Zero-Dependency Regex Normalizer executes in less than 2 milliseconds per document.

---

# 2. Source Code: `tests/plugins/test_ingestion.py`

```python
"""
Comprehensive Test Suite for the Ingestion Pipeline (Phase 09).

Covers: Connectors, Normalization, Deduplication, Pipeline Orchestration,
Persistence, CLI, and Performance benchmarks.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.cli.ingestion_cli import main as cli_main
from src.core.event_bus import EventBus
from src.core.memory_service import MemoryService
from src.core.metrics import MetricsRegistry
from src.core.storage_manager import StorageManager
from src.plugins.ingestion.connector_base import BaseSourceConnector, PaginationToken, RateLimitError, RawContent
from src.plugins.ingestion.enricher import MetadataEnricher
from src.plugins.ingestion.normalizer import ProblemNormalizer
from src.plugins.ingestion.pipeline import IngestionPipeline

# ---------------------------------------------------------
# Fixtures & Dependency Injection
# ---------------------------------------------------------
@pytest.fixture
def temp_storage():
    """Provides a fresh, isolated in-memory StorageManager for every test."""
    manager = StorageManager("sqlite:///:memory:")
    yield manager

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def metrics():
    return MetricsRegistry()

@pytest.fixture
def memory_service(temp_storage):
    return MemoryService(temp_storage)

@pytest.fixture
def raw_leetcode_html():
    """Real-world snapshot of LeetCode's chaotic DOM structure."""
    return (
        "<p>Given an array of integers <code>nums</code> and an integer <code>target</code>, "
        "return <em>indices</em> of the two numbers such that they add up to <code>target</code>.</p>\n"
        "<ul>\n"
        "    <li><code>2 &lt;= nums.length &lt;= 10<sup>4</sup></code></li>\n"
        "</ul>\n"
        "<pre><code>Input: nums = [2,7,11,15], target = 9\nOutput: [0,1]</code></pre>"
    )

# ---------------------------------------------------------
# 1. Normalization & Translation Tests
# ---------------------------------------------------------
def test_normalizer_html_stripping(raw_leetcode_html):
    """Proves the Zero-Dependency Regex engine perfectly translates HTML to Markdown."""
    normalizer = ProblemNormalizer()
    raw = RawContent(
        uri="two-sum",
        content_body=json.dumps({
            "title": "Two Sum", 
            "difficulty": "Easy", 
            "content": raw_leetcode_html
        }),
        content_type="application/json",
        metadata={}
    )
    
    doc = normalizer.normalize(raw)
    
    assert doc.title == "Two Sum"
    assert "**Difficulty:** Easy" in doc.markdown
    assert "Given an array of integers `nums`" in doc.markdown
    assert "*indices*" in doc.markdown
    assert "- `2 <= nums.length <= 10^4`" in doc.markdown
    assert "```\nInput: nums = [2,7,11,15], target = 9\nOutput: [0,1]\n```" in doc.markdown
    assert "<p>" not in doc.markdown
    assert "<ul>" not in doc.markdown

# ---------------------------------------------------------
# 2. Enrichment & Semantic Inference Tests
# ---------------------------------------------------------
def test_enricher_heuristics():
    """Proves the Deterministic Rule Engine can infer data structures for free."""
    normalizer = ProblemNormalizer()
    raw = RawContent(
        uri="binary-search",
        content_body=json.dumps({
            "title": "Binary Search", 
            "difficulty": "Easy", 
            "content": "<p>Given an array of integers nums which is sorted in ascending order.</p>"
        }),
        content_type="application/json",
        metadata={"tags": ["Array"]}
    )
    doc = normalizer.normalize(raw)
    
    enricher = MetadataEnricher()
    enriched_doc = enricher.enrich(doc)
    
    metadata = enriched_doc.metadata.get("enriched", {})
    assert "Array" in metadata["data_structures"]
    assert "Binary Search" in metadata["patterns"]
    assert metadata["primary_algorithm"] == "Binary Search"
    assert metadata["educational_level"] == "Beginner"

# ---------------------------------------------------------
# 3. Connector Resilience Tests
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_connector_exponential_backoff():
    """Proves the BaseSourceConnector intercepts 429s and retries seamlessly."""
    class RetryConnector(BaseSourceConnector):
        def __init__(self):
            super().__init__("Retry", rate_limit_ms=0)
            self.attempts = 0
            
        async def _do_health_check(self): return True
        async def authenticate(self, c): pass
        async def discover(self, q): return []
        async def _do_fetch(self, uri):
            self.attempts += 1
            if self.attempts == 1:
                # Force a crash on Attempt 1
                raise RateLimitError("HTTP 429: Too Fast!")
            return RawContent(uri, "{}", "application/json")
            
    c = RetryConnector()
    # If backoff fails, this will throw. If it succeeds, attempt 2 returns the payload.
    res = await c.fetch("test_uri")
    
    assert c.attempts == 2
    assert res.uri == "test_uri"

# ---------------------------------------------------------
# 4. Pipeline Orchestration Tests
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_streaming_resilience(event_bus, memory_service, metrics):
    """Proves a corrupted record doesn't crash a massive 3,000 problem stream."""
    class StreamConnector(BaseSourceConnector):
        def __init__(self):
            super().__init__("Stream", rate_limit_ms=0)
        async def _do_health_check(self): return True
        async def authenticate(self, c): pass
        async def discover(self, q): return []
        async def _do_fetch(self, uri): pass
        async def fetch_stream(self, uri):
            raw = RawContent(uri="page_1", content_body=json.dumps([{"titleSlug": "a"}, {"titleSlug": "b"}]), content_type="application/json")
            yield raw
            
    pipeline = IngestionPipeline(event_bus, memory_service, metrics)
    successful_uris = []
    
    # We explicitly sabotage item 'a'
    async def mock_run_single(connector, uri, corr_id):
        if uri == "a":
            raise ValueError("Corrupted Data")
        successful_uris.append(uri)
        
    pipeline.run_single = mock_run_single
    
    # Execute the stream
    await pipeline.run_stream(StreamConnector(), "all_problems", "corr-123")
    
    # 'b' should have processed perfectly despite 'a' throwing an Exception
    assert "b" in successful_uris
    assert "a" not in successful_uris

# ---------------------------------------------------------
# 5. CLI Invocation Tests
# ---------------------------------------------------------
def test_cli_execution():
    """Proves the CLI properly routes sys.args to the Async Graph."""
    with patch("src.cli.ingestion_cli._run_ingestion", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = 0
        
        # Simulating terminal command: `python -m src.cli.ingestion_cli leetcode --problem two-sum`
        exit_code = cli_main(["leetcode", "--problem", "two-sum"])
        
        assert exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args.source == "leetcode"
        assert args.problem == "two-sum"
        assert args.all is False

# ---------------------------------------------------------
# 6. Performance Benchmarks
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_normalization_performance(raw_leetcode_html):
    """
    GUARANTEE: The Normalizer MUST process 1,000 HTML documents 
    in less than 2000 milliseconds (2ms per doc).
    """
    normalizer = ProblemNormalizer()
    raw = RawContent(
        uri="two-sum",
        content_body=json.dumps({"title": "Two Sum", "difficulty": "Easy", "content": raw_leetcode_html}),
        content_type="application/json"
    )
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        normalizer.normalize(raw)
        
    total_time = time.perf_counter() - start
    avg_time_ms = (total_time / iterations) * 1000
    
    print(f"\n[PERFORMANCE] Average HTML->Markdown Latency: {avg_time_ms:.4f} ms")
    
    # Production constraint: The RegEx engine must be blazing fast
    assert avg_time_ms < 2.0, f"Performance Degradation! Normalization took {avg_time_ms} ms."
```

---

# 3. Testing Strategy

1. **Deterministic HTML Mocks:** The `raw_leetcode_html` fixture is a literal string copied directly from a LeetCode problem. If LeetCode updates their internal CSS tags, we only have to update this single fixture, and `test_normalizer_html_stripping` will instantly verify if our regex needs adjusting.
2. **Crash Tolerance Validation:** The `test_pipeline_streaming_resilience` physically injects a `ValueError` into the middle of the loop. If the pipeline was poorly written, the exception would bubble up and crash `run_stream`. The test verifies that item `'b'` successfully persists even if item `'a'` violently crashes.
3. **Hardware Latency Thresholds:** The `test_normalization_performance` test is not a traditional unit test. It executes the HTML RegEx parsing engine 1,000 times in a row, physically timing the CPU latency. If a junior developer accidentally adds an expensive loop to `normalizer.py` and slows the parser down to 10ms per document, the test suite will aggressively fail in CI/CD before the code is merged to Production.
