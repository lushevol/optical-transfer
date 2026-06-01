from __future__ import annotations

import tarfile

import atlasx.outbound.archive as archive_module
from atlasx.outbound.archive import archive_directory


def test_archive_directory_creates_tar_gz_with_relative_paths(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    empty_dir = nested_dir / "empty"
    empty_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")
    (nested_dir / "child.txt").write_text("nested file\n", encoding="utf-8")
    output_path = tmp_path / "payload.tar.gz"

    result = archive_directory(source_dir, output_path)

    assert result.archive_path == output_path
    assert output_path.exists()
    assert result.archive_byte_length == output_path.stat().st_size
    assert len(result.archive_hash) == 64
    assert result.original_directory_name == "payload"

    with tarfile.open(output_path, mode="r:gz") as tar:
        assert tar.getnames() == ["root.txt", "nested/child.txt", "nested/empty"]
        assert all("\\" not in name for name in tar.getnames())
        assert tar.extractfile("root.txt").read() == b"root file\n"
        assert tar.extractfile("nested/child.txt").read() == b"nested file\n"
        empty_member = tar.getmember("nested/empty")
        assert empty_member.isdir()
        assert empty_member.mode & 0o777 == 0o755


def test_archive_directory_uses_maximum_gzip_compression_level(tmp_path, monkeypatch) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")

    seen = {}
    real_compress = archive_module.gzip.compress

    def fake_compress(data, compresslevel=9, *, mtime=None):
        seen["compresslevel"] = compresslevel
        seen["mtime"] = mtime
        return real_compress(data, compresslevel=compresslevel, mtime=mtime)

    monkeypatch.setattr(archive_module.gzip, "compress", fake_compress)

    archive_directory(source_dir, tmp_path / "payload.tar.gz")

    assert seen == {"compresslevel": 9, "mtime": 0}


def test_archive_directory_excludes_outbound_session_bundle(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "root.txt").write_text("root file\n", encoding="utf-8")
    cache_dir = source_dir / ".atlasx-outbound"
    cache_dir.mkdir()
    (cache_dir / "session.json").write_text('{"cached":true}', encoding="utf-8")

    output_path = tmp_path / "payload.tar.gz"

    archive_directory(source_dir, output_path)

    with tarfile.open(output_path, mode="r:gz") as tar:
        member_names = tar.getnames()

    assert "root.txt" in member_names
    assert ".atlasx-outbound/session.json" not in member_names
