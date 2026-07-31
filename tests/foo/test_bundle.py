from __future__ import annotations

from atlasx.foo.bundle import build_bundle_chunks, restore_bundle_chunks


def test_bundle_restores_complete_files_when_an_unrelated_chunk_is_missing(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "complete.txt").write_text("complete", encoding="utf-8")
    (source / "large.bin").write_bytes(b"abcdefgh")

    chunks = build_bundle_chunks(source, chunk_size=4)
    chunks_without_last_segment = chunks[:-1]
    result = restore_bundle_chunks(
        [chunk.data for chunk in chunks_without_last_segment],
        tmp_path / "restored",
    )

    assert (result.restored_directory / "complete.txt").read_text(encoding="utf-8") == "complete"
    assert not (result.restored_directory / "large.bin").exists()
    assert result.restored_file_count == 1
    assert result.partial_fragment_count == 1
    partials = list((result.restored_directory / ".atlasx-partial").rglob("*.part-*"))
    assert [path.read_bytes() for path in partials] == [b"abcd"]


def test_bundle_restores_empty_files_and_directories(tmp_path) -> None:
    source = tmp_path / "source"
    (source / "empty-dir").mkdir(parents=True)
    (source / "empty.txt").write_bytes(b"")

    chunks = build_bundle_chunks(source, chunk_size=4)
    result = restore_bundle_chunks(
        [chunk.data for chunk in chunks],
        tmp_path / "restored",
    )

    assert (result.restored_directory / "empty-dir").is_dir()
    assert (result.restored_directory / "empty.txt").read_bytes() == b""
