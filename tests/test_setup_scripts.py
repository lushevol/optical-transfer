from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_foo_setup_script_exists_with_foo_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-foo-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-foo" in content
    assert "pip install -e ." in content
    assert "atlasx foo --source ./payload --password \"secret\"" in content
    assert "ffmpeg" not in content


def test_bar_setup_script_exists_with_bar_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-bar-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-bar" in content
    assert "-e '.[bar]'" in content
    assert "atlasx bar recording.mp4 --password \"secret\" --output-root restored" in content
    assert "ffmpeg" in content
    assert "PIP_INDEX_URL" in content
    assert "--only-binary=opencv-python" in content
