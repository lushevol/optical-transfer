from __future__ import annotations

from typing import Dict, List

from atlasx.bar.collector import VerifiedChunk


def reassemble_archive(chunks: List[VerifiedChunk], expected_total: int) -> bytes:
    if expected_total <= 0:
        raise ValueError("expected_total must be positive")
    if not chunks:
        raise ValueError("cannot reassemble an empty chunk set")

    session_ids = {chunk.session_id for chunk in chunks}
    if len(session_ids) != 1:
        raise ValueError("chunks must belong to exactly one session")

    total_chunks = {chunk.total_chunks for chunk in chunks}
    if total_chunks != {expected_total}:
        raise ValueError("chunks do not describe the expected logical chunk set")

    by_index: Dict[int, VerifiedChunk] = {}
    for chunk in chunks:
        existing = by_index.get(chunk.chunk_index)
        if existing is not None and existing != chunk:
            raise ValueError("conflicting chunk data for the same chunk index")
        by_index[chunk.chunk_index] = chunk

    expected_indexes = set(range(expected_total))
    found_indexes = set(by_index)
    if found_indexes != expected_indexes:
        missing = sorted(expected_indexes - found_indexes)
        extra = sorted(found_indexes - expected_indexes)
        raise ValueError(
            "chunk set is incomplete"
            + (f"; missing indexes {missing}" if missing else "")
            + (f"; unexpected indexes {extra}" if extra else "")
        )

    return b"".join(by_index[index].data for index in range(expected_total))
