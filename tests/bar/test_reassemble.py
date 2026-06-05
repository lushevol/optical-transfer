from __future__ import annotations

import pytest

from atlasx.bar.collector import VerifiedChunk
from atlasx.bar.reassemble import reassemble_archive


def test_reassembler_requires_complete_logical_chunk_set() -> None:
    chunks = [
        VerifiedChunk(
            session_id=b"0123456789abcdef",
            chunk_index=0,
            total_chunks=3,
            data=b"alpha",
        ),
        VerifiedChunk(
            session_id=b"0123456789abcdef",
            chunk_index=2,
            total_chunks=3,
            data=b"charlie",
        ),
    ]

    with pytest.raises(ValueError, match="complete"):
        reassemble_archive(chunks, expected_total=3)
