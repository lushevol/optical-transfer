from __future__ import annotations

from atlasx.bar.restore import restore_archive_bytes
from atlasx.foo.archive import archive_directory


def test_restore_archive_extracts_into_fresh_directory(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")
    archive_result = archive_directory(source_dir, tmp_path / "payload.tar.gz")
    output_root = tmp_path / "restored"

    first_output = restore_archive_bytes(archive_result.archive_path.read_bytes(), output_root)
    second_output = restore_archive_bytes(archive_result.archive_path.read_bytes(), output_root)

    assert first_output.exists()
    assert second_output.exists()
    assert first_output != output_root
    assert second_output != output_root
    assert first_output != second_output
    assert (first_output / "data.txt").read_text(encoding="utf-8") == "hello world\n"
    assert (second_output / "data.txt").read_text(encoding="utf-8") == "hello world\n"


def test_restore_archive_succeeds_with_symlinked_output_root(tmp_path) -> None:
    source_dir = tmp_path / "payload"
    source_dir.mkdir()
    (source_dir / "data.txt").write_text("hello world\n", encoding="utf-8")
    archive_result = archive_directory(source_dir, tmp_path / "payload.tar.gz")

    real_root = tmp_path / "real-output"
    real_root.mkdir()
    symlink_root = tmp_path / "linked-output"
    symlink_root.symlink_to(real_root, target_is_directory=True)
    output_root = symlink_root / "restored"

    restored_dir = restore_archive_bytes(archive_result.archive_path.read_bytes(), output_root)

    assert restored_dir.exists()
    assert restored_dir.is_dir()
    assert (restored_dir / "data.txt").read_text(encoding="utf-8") == "hello world\n"
