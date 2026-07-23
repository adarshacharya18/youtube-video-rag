import types
import sys
import re
from run_full_code_tests import setup_environment, TARGET_FILE

def test_event_schemas():
    setup_environment()

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.findall(r"```python([\s\S]*?)```", content)

    global_env = {}
    # Exec Block 1 & Block 2
    exec(compile(blocks[0], "<b1>", "exec"), global_env)
    exec(compile(blocks[1], "<b2>", "exec"), global_env)

    EventMetadata = global_env['EventMetadata']
    meta = EventMetadata(
        event_id="evt_100",
        timestamp="2026-07-23T12:00:00Z",
        correlation_id="corr_100",
        trace_id="trace_100",
        pipeline_id="pipe_100",
        plugin_id="plugin_voice"
    )
    assert meta.priority == 5

    payloads = [
        "ScriptApprovedPayload",
        "VoiceSynthesisStartedPayload",
        "AudioSectionManifest",
        "AudioRenderedPayload",
        "AnimationRenderStartedPayload",
        "RenderCompletePayload",
        "SubtitleCompletePayload",
        "VideoAssembledPayload",
        "ThumbnailCompletePayload",
        "YoutubePublishedPayload",
        "PipelineCompletedPayload",
        "PipelineFailedPayload",
    ]

    for p in payloads:
        assert p in global_env, f"Payload {p} missing!"
        cls = global_env[p]
        print(f"  [PASS] Dataclass {p} exists with fields: {list(cls.__dataclass_fields__.keys())}")

    print("[PASS] All Event Bus Payload Dataclasses verified.")

if __name__ == "__main__":
    test_event_schemas()
