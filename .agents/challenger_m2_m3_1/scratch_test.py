import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, "/home/adarsh/Documents/Youtube-Channel")

from src.assembly.assembler import VideoAssembler
from src.core.exceptions import AssemblyError
from src.pipeline.nodes.video_assembly_node import VideoAssemblyNode
from src.core.orchestrator.state_ledger import StateLedger

def test_cleanup_empirically():
    with tempfile.TemporaryDirectory() as tmp_workspace:
        tmp_p = Path(tmp_workspace)
        v1 = tmp_p / "seg1.mp4"
        v1.write_bytes(b"0" * 300)

        out_path = tmp_p / "final.mp4"
        tmp_dest = tmp_p / f"final.mp4.tmp_{os.getpid()}"

        custom_temp = tmp_p / "temp_scratch"
        assembler = VideoAssembler(temp_dir=custom_temp)

        # 1. Success case: verify temp_dir cleaned up, temp_dest renamed to final.mp4
        def mock_run_cmd_success(args, timeout=None, cwd=None):
            # Assert cwd is inside custom_temp
            assert str(custom_temp) in str(cwd)
            # Write dummy data to output file (which is tmp_dest)
            tmp_out = Path(args[-1])
            tmp_out.write_bytes(b"V" * 500)

        assembler.run_command = mock_run_cmd_success
        result = assembler.assemble(
            video_segments=[v1],
            subtitle_text="1\n00:00:00,000 --> 00:00:01,000\nTest\n\n",
            output_path=out_path
        )
        assert result.exists()
        assert not tmp_dest.exists()
        # Assert no leftover assembly_ directories in custom_temp
        leftover = list(custom_temp.glob("assembly_*"))
        assert len(leftover) == 0, f"Leftover temp dirs found: {leftover}"

        # 2. Failure case: verify partial file cleaned up and temp dir deleted
        out_path_fail = tmp_p / "fail.mp4"
        tmp_dest_fail = tmp_p / f"fail.mp4.tmp_{os.getpid()}"

        def mock_run_cmd_fail(args, timeout=None, cwd=None):
            tmp_out = Path(args[-1])
            tmp_out.write_bytes(b"PARTIAL_DATA")
            raise AssemblyError("Simulated failure")

        assembler.run_command = mock_run_cmd_fail
        try:
            assembler.assemble(
                video_segments=[v1],
                subtitle_text="1\n00:00:00,000 --> 00:00:01,000\nTest\n\n",
                output_path=out_path_fail
            )
            assert False, "Should have raised AssemblyError"
        except AssemblyError:
            pass

        assert not out_path_fail.exists()
        assert not tmp_dest_fail.exists()
        leftover = list(custom_temp.glob("assembly_*"))
        assert len(leftover) == 0, f"Leftover temp dirs found on failure: {leftover}"

        print("Empirical cleanup test PASSED successfully!")

if __name__ == "__main__":
    test_cleanup_empirically()
