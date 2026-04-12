"""Tests unitarios del motor ROCE FFmpeg (sin encadenar todo el stack de auth)."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from services.roce_video_ffmpeg import (
    apply_operations,
    ffmpeg_binary,
    resolve_safe_under_uploads,
)


def _ffmpeg_available() -> bool:
    return shutil.which(ffmpeg_binary()) is not None


def test_resolve_rejects_traversal():
    with pytest.raises(ValueError):
        resolve_safe_under_uploads("video_roce/../../../etc/passwd")


def test_resolve_rejects_bad_prefix():
    with pytest.raises(ValueError):
        resolve_safe_under_uploads("video_roce_jobs/job.json")


def test_resolve_accepts_video_roce():
    # Solo valida forma; el fichero puede no existir.
    p = resolve_safe_under_uploads("video_roce/dummy.mp4")
    assert p.name == "dummy.mp4"
    assert "video_roce" in p.as_posix()


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg no está en PATH")
def test_apply_operations_trim_generates_output():
    tmp = Path(tempfile.mkdtemp(prefix="roce_ut_"))
    try:
        src = tmp / "in.mp4"
        ff = ffmpeg_binary()
        r = subprocess.run(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=2:size=64x64:rate=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(src),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        wd = tmp / "work"
        wd.mkdir()
        ok, out, err = apply_operations(
            src,
            [{"op": "trim", "start_time": 0, "duration": 1}],
            wd,
            budget_sec=25,
        )
        assert ok, err
        assert out.exists() and out.stat().st_size > 100
        assert err == ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
