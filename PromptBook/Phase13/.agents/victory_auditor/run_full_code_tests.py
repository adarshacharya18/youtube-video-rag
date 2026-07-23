import ast
import asyncio
from datetime import datetime, timezone
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

def setup_environment():
    # Setup prometheus_client mock
    m = types.ModuleType('prometheus_client')
    class Counter:
        def __init__(self, name, desc, labels=None): self.name = name
        def labels(self, *args, **kwargs): return self
        def inc(self, amount=1): pass
    class Gauge:
        def __init__(self, name, desc, labels=None): self.name = name
        def labels(self, *args, **kwargs): return self
        def set(self, val): pass
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
    class Histogram:
        def __init__(self, name, desc, labels=None, buckets=None): self.name = name
        def labels(self, *args, **kwargs): return self
        def observe(self, val): pass
    m.Counter = Counter
    m.Gauge = Gauge
    m.Histogram = Histogram
    m.start_http_server = lambda port: None
    sys.modules['prometheus_client'] = m

    # Setup opentelemetry mock
    otel = types.ModuleType('opentelemetry')
    trace = types.ModuleType('opentelemetry.trace')
    trace.set_tracer_provider = lambda p: None
    trace.get_tracer = lambda *args, **kwargs: None
    otel.trace = trace
    sys.modules['opentelemetry'] = otel

    sdk = types.ModuleType('opentelemetry.sdk')
    sdk_trace = types.ModuleType('opentelemetry.sdk.trace')
    sdk_trace_export = types.ModuleType('opentelemetry.sdk.trace.export')
    
    class TracerProvider:
        def __init__(self, resource=None): pass
        def add_span_processor(self, proc): pass
    class BatchSpanProcessor:
        def __init__(self, exporter): pass

    sdk_trace.TracerProvider = TracerProvider
    sdk_trace_export.BatchSpanProcessor = BatchSpanProcessor
    sdk_trace.export = sdk_trace_export

    sdk.trace = sdk_trace
    sys.modules['opentelemetry.sdk'] = sdk
    sys.modules['opentelemetry.sdk.trace'] = sdk_trace
    sys.modules['opentelemetry.sdk.trace.export'] = sdk_trace_export

    res = types.ModuleType('opentelemetry.sdk.resources')
    class Resource:
        @staticmethod
        def create(d): return d
    res.Resource = Resource
    sys.modules['opentelemetry.sdk.resources'] = res

    exporter = types.ModuleType('opentelemetry.exporter')
    exporter_otlp = types.ModuleType('opentelemetry.exporter.otlp')
    exporter_proto = types.ModuleType('opentelemetry.exporter.otlp.proto')
    exporter_grpc = types.ModuleType('opentelemetry.exporter.otlp.proto.grpc')
    exporter_trace = types.ModuleType('opentelemetry.exporter.otlp.proto.grpc.trace_exporter')
    class OTLPSpanExporter:
        def __init__(self, endpoint=None, insecure=True): pass
    exporter_trace.OTLPSpanExporter = OTLPSpanExporter
    sys.modules['opentelemetry.exporter'] = exporter
    sys.modules['opentelemetry.exporter.otlp'] = exporter_otlp
    sys.modules['opentelemetry.exporter.otlp.proto'] = exporter_proto
    sys.modules['opentelemetry.exporter.otlp.proto.grpc'] = exporter_grpc
    sys.modules['opentelemetry.exporter.otlp.proto.grpc.trace_exporter'] = exporter_trace

    prop = types.ModuleType('opentelemetry.trace.propagation')
    prop_tc = types.ModuleType('opentelemetry.trace.propagation.tracecontext')
    class TraceContextTextMapPropagator:
        def inject(self, carrier): pass
        def extract(self, carrier): return {}
    prop_tc.TraceContextTextMapPropagator = TraceContextTextMapPropagator
    prop.tracecontext = prop_tc
    sys.modules['opentelemetry.trace.propagation'] = prop
    sys.modules['opentelemetry.trace.propagation.tracecontext'] = prop_tc

def run_tests():
    setup_environment()

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.findall(r"```python([\s\S]*?)```", content)
    print(f"Executing and testing {len(blocks)} python code blocks...\n")

    global_env = {}

    # Define fake package structure for src.media_production.spi.contracts
    src_mod = types.ModuleType('src')
    media_mod = types.ModuleType('src.media_production')
    spi_mod = types.ModuleType('src.media_production.spi')
    contracts_mod = types.ModuleType('src.media_production.spi.contracts')
    sys.modules['src'] = src_mod
    sys.modules['src.media_production'] = media_mod
    sys.modules['src.media_production.spi'] = spi_mod
    sys.modules['src.media_production.spi.contracts'] = contracts_mod

    for idx, block in enumerate(blocks, 1):
        print(f"Testing Block {idx}...")
        compiled = compile(block, filename=f"<block_{idx}>", mode="exec")
        exec(compiled, global_env)

        # If block 3 (SPI contracts), populate the mocked module
        if idx == 3:
            for item in ["AnimationProvider", "PublisherProvider", "SubtitleProvider", "ThumbnailProvider", "VoiceProvider"]:
                if item in global_env:
                    setattr(contracts_mod, item, global_env[item])

        print(f"  Block {idx}: Executed successfully.")

    print("\n--- Running Logic Verification Unit Tests ---")

    # Test 1: Retry logic (Block 5)
    retry_decorator = global_env['exponential_backoff_with_jitter']
    attempts = 0
    @retry_decorator(max_attempts=3, initial_delay=0.01, max_delay=0.05, backoff_factor=2.0)
    async def test_retry():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("Transient Error")
        return "SUCCESS"

    res = asyncio.run(test_retry())
    assert res == "SUCCESS"
    assert attempts == 3
    print("  [PASS] Exponential backoff retry logic verified.")

    # Test 2: Circuit Breaker (Block 6)
    CircuitBreaker = global_env['CircuitBreaker']
    CircuitState = global_env['CircuitState']
    CircuitOpenError = global_env['CircuitOpenError']

    cb = CircuitBreaker(name="test_cb", failure_threshold=2, reset_timeout_seconds=0.2)
    assert cb.state == CircuitState.CLOSED

    async def fail_op():
        async def _inner(): raise ValueError("Fail")
        return await cb(_inner)

    # 1st fail
    try: asyncio.run(fail_op())
    except ValueError: pass
    assert cb.state == CircuitState.CLOSED

    # 2nd fail -> OPEN
    try: asyncio.run(fail_op())
    except ValueError: pass
    assert cb.state == CircuitState.OPEN
    print("  [PASS] Circuit Breaker state transition CLOSED -> OPEN verified.")

    # Check that calling while OPEN raises CircuitOpenError
    async def try_open():
        async def _inner(): return "OK"
        return await cb(_inner)

    try:
        asyncio.run(try_open())
        assert False, "Should have raised CircuitOpenError"
    except CircuitOpenError:
        print("  [PASS] Circuit Breaker raises CircuitOpenError when OPEN.")

    # Wait reset_timeout and check HALF_OPEN recovery
    import time
    time.sleep(0.25)
    async def succeed_op():
        async def _inner(): return "OK"
        return await cb(_inner)

    # First call in HALF_OPEN
    r1 = asyncio.run(succeed_op())
    assert r1 == "OK"
    assert cb.state == CircuitState.HALF_OPEN
    print("  [PASS] Circuit Breaker probed into HALF_OPEN state.")

    # Subsequent successes transition back to CLOSED
    asyncio.run(succeed_op())
    asyncio.run(succeed_op())
    assert cb.state == CircuitState.CLOSED
    print("  [PASS] Circuit Breaker recovered from HALF_OPEN to CLOSED.")

    # Test 3: DeadLetterQueueStore (Block 7)
    DLQStore = global_env['DeadLetterQueueStore']
    DLQEnvelope = global_env['DLQEnvelope']

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_p = Path(tmp.name)

    try:
        dlq = DLQStore(db_path=db_p)
        env = DLQEnvelope(
            dlq_id="dlq_001",
            event_id="evt_001",
            correlation_id="corr_001",
            event_type="ScriptApproved",
            source_plugin="plugin_educational",
            failed_at=datetime.now(timezone.utc),
            failure_category="TRANSIENT_TIMEOUT",
            error_id="ERR_504",
            error_message="Gateway timeout",
            stack_trace="Traceback (most recent call last)...",
            retry_count=3,
            original_payload={"script_id": "scr_123", "slug": "math-calculus"}
        )
        dlq.push(env)
        unresolved = dlq.list_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].dlq_id == "dlq_001"
        assert unresolved[0].original_payload["slug"] == "math-calculus"

        fetched = dlq.get_by_id("dlq_001")
        assert fetched is not None
        assert fetched.resolved is False

        dlq.mark_resolved("dlq_001", "Manually retried")
        assert len(dlq.list_unresolved()) == 0
        fetched_after = dlq.get_by_id("dlq_001")
        assert fetched_after.resolved is True
        assert fetched_after.resolution_notes == "Manually retried"
        print("  [PASS] DeadLetterQueueStore push, query, and mark_resolved verified.")
    finally:
        if db_p.exists():
            db_p.unlink()

    # Test 4: Segment Hash (Block 8)
    compute_hash = global_env['compute_segment_hash']
    h1 = compute_hash("manim", "sec1", "Text A", {"color": "blue"}, 10.0)
    h2 = compute_hash("manim", "sec1", "Text A", {"color": "blue"}, 10.0)
    h3 = compute_hash("manim", "sec1", "Text B", {"color": "blue"}, 10.0)
    assert h1 == h2
    assert h1 != h3
    print("  [PASS] Segment hash calculation determinism verified.")

    # Test 5: Fallback Static Clip Generator (Block 9)
    gen_slide = global_env['generate_static_slide_clip']
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_mp4:
        out_path = Path(tmp_mp4.name)

    try:
        # Note: ffmpeg might not be installed, so let's test ffmpeg call exception handling or mock subprocess
        import subprocess
        old_run = subprocess.run
        def mock_run(cmd, check=True, stdout=None, stderr=None):
            # Touch out_path to simulate ffmpeg creation
            out_path.write_bytes(b"FAKE MP4")
            class Completed:
                returncode = 0
            return Completed()
        subprocess.run = mock_run
        try:
            res_path = gen_slide("Test Title", ["Point 1", "Point 2"], 2.0, out_path)
            assert res_path.exists()
            print("  [PASS] Fallback static slide generator execution verified.")
        finally:
            subprocess.run = old_run
    finally:
        if out_path.exists():
            out_path.unlink()

    # Test 6: Metrics setup (Block 10)
    assert 'RUNS_TOTAL' in global_env
    assert 'ERRORS_TOTAL' in global_env
    print("  [PASS] Prometheus metrics definitions verified.")

    # Test 7: Tracer setup (Block 11)
    assert 'inject_trace_context' in global_env
    assert 'extract_trace_context' in global_env
    print("  [PASS] OpenTelemetry tracer setup & context propagation functions verified.")

    print("\nALL FUNCTIONAL UNIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
