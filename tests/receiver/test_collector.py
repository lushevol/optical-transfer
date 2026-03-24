from __future__ import annotations

from optical_transfer.receiver.collector import PacketCollector, VerifiedChunk


def test_collector_deduplicates_chunks_by_session_and_index() -> None:
    collector = PacketCollector()
    session_a = b"0123456789abcdef"
    session_b = b"fedcba9876543210"
    chunk_a = VerifiedChunk(
        session_id=session_a,
        chunk_index=0,
        total_chunks=2,
        data=b"alpha",
    )
    chunk_a_duplicate = VerifiedChunk(
        session_id=session_a,
        chunk_index=0,
        total_chunks=2,
        data=b"alpha",
    )
    chunk_b = VerifiedChunk(
        session_id=session_b,
        chunk_index=0,
        total_chunks=1,
        data=b"bravo",
    )

    collector.add_chunk(chunk_a)
    collector.add_chunk(chunk_a_duplicate)
    collector.add_chunk(chunk_b)

    assert collector.chunks(session_a) == [chunk_a]
    assert collector.chunks(session_b) == [chunk_b]
