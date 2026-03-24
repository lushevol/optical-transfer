from __future__ import annotations

import tarfile

from optical_transfer.sender.archive import archive_directory


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
        assert tar.getmember("nested/empty").isdir()
