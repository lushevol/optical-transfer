from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sender_setup_script_exists_with_sender_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-sender-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-sender" in content
    assert "pip install -e ." in content
    assert "ffmpeg" not in content


def test_receiver_setup_script_exists_with_receiver_specific_steps() -> None:
    script_path = REPO_ROOT / "scripts" / "setup-receiver-macos.sh"

    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert ".venv-receiver" in content
    assert "pip install -e ." in content
    assert "ffmpeg" in content
