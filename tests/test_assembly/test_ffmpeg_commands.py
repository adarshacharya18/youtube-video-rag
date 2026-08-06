import pytest
from pathlib import Path
from src.assembly.ffmpeg_commands import build_assembly_command, build_demuxer_assembly_command

def test_build_assembly_command_uses_duration_instead_of_shortest():
    cmd = build_assembly_command(
        video_inputs=["v1.mp4", "v2.mp4"],
        audio_inputs="audio.wav",
        output_duration=123.5,
    )
    assert "-t" in cmd
    assert str(123.5) in cmd
    assert "-shortest" not in cmd

def test_build_demuxer_assembly_command_uses_duration_instead_of_shortest():
    cmd = build_demuxer_assembly_command(
        video_manifest_path="v_list.txt",
        audio_manifest_path="audio.wav",
        output_duration=45.1,
    )
    assert "-t" in cmd
    assert str(45.1) in cmd
    assert "-shortest" not in cmd
