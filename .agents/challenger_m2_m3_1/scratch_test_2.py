import os
import sys
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, "/home/adarsh/Documents/Youtube-Channel")

from src.assembly.assembler import VideoAssembler
from src.assembly.ffmpeg_commands import build_assembly_command, build_concat_filter_graph
from src.core.exceptions import AssemblyError

def test_fd_and_binary_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        v1 = tmp_p / "seg1.mp4"
        v1.write_bytes(b"0" * 300)
        out = tmp_p / "assembled.mp4"

        mock_py = tmp_p / "mock_ffmpeg.py"
        mock_py.write_text(
            "import sys, os\n"
            "out = sys.argv[-1]\n"
            "os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)\n"
            "with open(out, 'wb') as f:\n"
            "    f.write(b'MOCK_DATA_' * 20)\n"
            "sys.exit(0)\n",
            encoding="utf-8"
        )

        assembler = VideoAssembler(ffmpeg_binary=str(mock_py))

        # Check FD count before and after
        if os.path.exists("/proc/self/fd"):
            fds_before = len(os.listdir("/proc/self/fd"))

        res = assembler.assemble(video_segments=[v1], output_path=out)
        assert res.exists()
        assert res.stat().st_size >= 100

        if os.path.exists("/proc/self/fd"):
            fds_after = len(os.listdir("/proc/self/fd"))
            assert fds_after == fds_before, f"FD leak detected! Before: {fds_before}, After: {fds_after}"

        print("FD leak and Mock Python binary test PASSED!")

if __name__ == "__main__":
    test_fd_and_binary_execution()
