from __future__ import annotations

from atlasx.foo.chunker import Chunk, chunk_bytes


def test_chunk_bytes_yields_stable_chunk_indexes() -> None:
    chunks = chunk_bytes(b"abcdefgh", chunk_size=3)

    assert chunks == [
        Chunk(chunk_index=0, data=b"abc"),
        Chunk(chunk_index=1, data=b"def"),
        Chunk(chunk_index=2, data=b"gh"),
    ]
