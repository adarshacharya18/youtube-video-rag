import ast
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

TARGET_FILE = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase13/01_Media_Production_Architecture.md"

# Setup mocks for uninstalled external libraries if needed
def setup_mocks():
    # Mock prometheus_client
    if 'prometheus_client' not in sys.modules:
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

    # Mock opentelemetry
    if 'opentelemetry' not in sys.modules:
        otel = types.ModuleType('opentelemetry')
        trace = types.ModuleType('opentelemetry.trace')
        trace.set_tracer_provider = lambda p: None
        trace.get_tracer = lambda name: None
        otel.trace = trace
        sys.modules['opentelemetry'] = otel

        sdk = types.ModuleType('opentelemetry.sdk')
        sdk_trace = types.ModuleType('opentelemetry.sdk.trace')
        class TracerProvider:
            def __init__(self, resource=None): pass
            def add_span_processor(self, proc): pass
        class BatchSpanProcessor:
            def __init__(self, exporter): pass
        sdk_trace.TracerProvider = TracerProvider
        sdk_trace.BatchSpanProcessor = BatchSpanProcessor
        sdk.trace = sdk_trace
        sys.modules['opentelemetry.sdk'] = sdk
        sys.modules['opentelemetry.sdk.trace'] = sdk_trace

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
        prop_baggage = types.ModuleType('opentelemetry.trace.propagation.w3c_baggage')
        class W3CBaggagePropagator: pass
        prop_baggage.W3CBaggagePropagator = W3CBaggagePropagator
        sys.modules['opentelemetry.trace.propagation'] = prop
        sys.modules['opentelemetry.trace.propagation.w3c_baggage'] = prop_baggage

def run_tests():
    setup_mocks()

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.findall(r"```python([\s\S]*?)```", content)
    print(f"Testing execution of {len(blocks)} python code blocks...\n")

    executed_env = {}

    for idx, block in enumerate(blocks, 1):
        print(f"--- Block {idx} ---")
        # Compile test
        try:
            compiled = compile(block, filename=f"<string_block_{idx}>", mode="exec")
            print(f"  Compile: SUCCESS")
        except Exception as e:
            print(f"  Compile: FAILED -> {e}")
            continue

        # Execute in combined/isolated scope
        try:
            exec(compiled, executed_env)
            print(f"  Exec: SUCCESS")
        except Exception as e:
            print(f"  Exec: FAILED -> {e}")

    # Now run specific behavioural unit tests on executed environment objects
    print("\n--- Functional Logic Unit Tests ---")

    # 1. Test Retry with Jitter
    if 'exponential_backoff_with_jitter' in executed_env:
        try:
            fn = executed_env['exponential_backoff_with_jitter']
            calls = 0
            @fn(max_attempts=3, initial_delay=0.01, max_delay=0.1, backoff_factor=2.0)
            async def failing_func():
                nonlocal calls
                calls += 1
                if calls < 3:
                    raise ValueError("Temporary error")
                return "SUCCESS"

            import asyncio
            res = asyncio.run(failing_func())
            print(f"  Retry Decorator: PASS (Result={res}, Attempts={calls})")
        except Exception as e:
            print(f"  Retry Decorator: FAIL -> {e}")
    else:
        print("  Retry Decorator: NOT FOUND in exec environment")

    # 2. Test Circuit Breaker
    if 'CircuitBreaker' in executed_env:
        try:
            CB = executed_env['CircuitBreaker']
            cb = CB(failure_threshold=2, recovery_timeout=0.2)
            assert cb.state.value == "CLOSED"

            async def fail():
                async with cb:
                    raise RuntimeError("Error")

            import asyncio
            # 1st failure
            try: asyncio.run(fail())
            except RuntimeError: pass
            assert cb.state.value == "CLOSED"

            # 2nd failure -> transition to OPEN
            try: asyncio.run(fail())
            except RuntimeError: pass
            assert cb.state.value == "OPEN"
            print("  Circuit Breaker State Transition (CLOSED -> OPEN): PASS")

            # Try execution while OPEN -> should raise CircuitOpenError
            CircuitOpenError = executed_env['CircuitOpenError']
            async def test_open():
                async with cb:
                    pass

            try:
                asyncio.run(test_open())
                print("  Circuit Breaker Open Block: FAIL (did not raise)")
            except CircuitOpenError:
                print("  Circuit Breaker Open Block: PASS (raised CircuitOpenError)")

        except Exception as e:
            print(f"  Circuit Breaker: FAIL -> {e}")
    else:
        print("  Circuit Breaker: NOT FOUND in exec environment")

    # 3. Test DLQ SQLite Persistence
    if 'SQLiteDLQRepository' in executed_env and 'DLQEnvelope' in executed_env:
        try:
            Repo = executed_env['SQLiteDLQRepository']
            Envelope = executed_env['DLQEnvelope']

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmpdb:
                db_path = tmpdb.name

            try:
                repo = Repo(db_path)
                env_obj = Envelope(
                    dlq_id="dlq_123",
                    event_id="evt_456",
                    correlation_id="corr_789",
                    event_type="ScriptApproved",
                    source_plugin="plugin_script",
                    failed_at="2026-07-23T12:00:00Z",
                    payload={"slug": "test_slug"},
                    error_message="Test failure",
                    error_stacktrace="Traceback...",
                    retry_count=3,
                    status="DEAD"
                )
                repo.enqueue(env_obj)
                res = repo.get_by_id("dlq_123")
                assert res is not None
                assert res.event_type == "ScriptApproved"
                assert res.payload == {"slug": "test_slug"}
                print("  DLQ Persistence & Serialization: PASS")
            finally:
                if os.path.exists(db_path):
                    os.remove(db_path)
        except Exception as e:
            print(f"  DLQ Persistence: FAIL -> {e}")
    else:
        print("  DLQ Persistence: NOT FOUND in exec environment")

    # 4. Test Segment Hash Calculation
    if 'compute_segment_hash' in executed_env:
        try:
            fn = executed_env['compute_segment_hash']
            h1 = fn("manim_v1", "sec_1", "Hello world", {"bg": "black"}, 5.0)
            h2 = fn("manim_v1", "sec_1", "Hello world", {"bg": "black"}, 5.0)
            h3 = fn("manim_v1", "sec_1", "Hello world!", {"bg": "black"}, 5.0)
            assert h1 == h2
            assert h1 != h3
            assert len(h1) == 64 # SHA256 hex length
            print(f"  Segment Hash Calculation: PASS (sha256={h1[:8]}...)")
        except Exception as e:
            print(f"  Segment Hash Calculation: FAIL -> {e}")
    else:
        print("  Segment Hash Calculation: NOT FOUND in exec environment")

if __name__ == "__main__":
    run_tests()
