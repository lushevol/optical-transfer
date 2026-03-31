from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_outbound_setup_script_exists_with_outbound_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-outbound-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-outbound" in content
    assert "pip install -e ." in content
    assert "atlasx foo --source ./payload --password \"secret\"" in content
    assert "ffmpeg" not in content


def test_inbound_setup_script_exists_with_inbound_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-inbound-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-inbound" in content
    assert "-e '.[inbound]'" in content
    assert "atlasx bar recording.mp4 --password \"secret\" --output-root restored" in content
    assert "ffmpeg" in content
    assert "PIP_INDEX_URL" in content
    assert "--only-binary=opencv-python" in content
