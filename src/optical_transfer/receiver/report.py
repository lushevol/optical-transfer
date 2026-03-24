from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SessionStats:
    input_video_count: int
    total_extracted_frame_count: int
    successfully_decoded_frame_count: int
    raw_packet_count: int
    deduplicated_valid_chunk_count: int
    missing_chunk_count: int
    authentication_failure_count: int
    final_archive_hash_result: str
    stage_timings: dict[str, float] = field(default_factory=dict)
    restored_directory: Path | None = None


def build_session_report(stats: SessionStats) -> str:
    lines = [
        f"input video count: {stats.input_video_count}",
        f"total extracted frame count: {stats.total_extracted_frame_count}",
        f"successfully decoded frame count: {stats.successfully_decoded_frame_count}",
        f"raw packet count: {stats.raw_packet_count}",
        f"deduplicated valid chunk count: {stats.deduplicated_valid_chunk_count}",
        f"missing chunk count: {stats.missing_chunk_count}",
        f"authentication failure count: {stats.authentication_failure_count}",
        f"final archive hash result: {stats.final_archive_hash_result}",
    ]

    if stats.restored_directory is not None:
        lines.append(f"restored directory: {stats.restored_directory}")

    if stats.stage_timings:
        lines.append("per-stage timing:")
        for name in sorted(stats.stage_timings):
            lines.append(f"  {name}: {stats.stage_timings[name]:.3f}s")

    return "\n".join(lines)
