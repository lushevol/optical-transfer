from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable


def extract_frames(
    video_path: Path,
    *,
    output_dir: Path | None = None,
    runner: Callable[..., object] = subprocess.run,
    ffmpeg_bin: str = "ffmpeg",
) -> list[Path]:
    video_path = Path(video_path)
    output_dir = Path(output_dir) if output_dir is not None else video_path.with_name(f"{video_path.stem}_frames")
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_frame in output_dir.glob("frame_*.png"):
        stale_frame.unlink()

    output_pattern = output_dir / "frame_%06d.png"
    command = [
        ffmpeg_bin,
        "-i",
        str(video_path),
        "-fps_mode",
        "passthrough",
        str(output_pattern),
    ]
    runner(command, check=True)

    return sorted(output_dir.glob("frame_*.png"))
