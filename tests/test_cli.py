import inspect
import json
from pathlib import Path
import urllib.request

import optical_transfer.cli as cli_module
import pytest

from optical_transfer.cli import build_parser, build_preview_url, build_sender_config, handle_send, main
from optical_transfer.config import DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_PORT
from optical_transfer.receiver.report import SessionStats, build_session_report
from optical_transfer.sender.player_server import create_player_app
from optical_transfer.sender.session import build_session_payloads


def test_parser_accepts_send_and_receive_subcommands():
    parser = build_parser()
    assert parser.parse_args(["send"]).command == "send"
    assert parser.parse_args(["receive", "recording.mp4"]).command == "receive"


def test_receive_command_accepts_multiple_videos():
    parser = build_parser()
    args = parser.parse_args(["receive", "recording1.mp4", "recording2.mp4", "--password", "secret"])

    assert args.videos == ["recording1.mp4", "recording2.mp4"]
    assert args.password == "secret"


def test_send_command_builds_default_sender_config(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["send", "--source", str(source_dir), "--password", "secret"])

    config = build_sender_config(args)

    assert config.source_dir == source_dir
    assert config.password == "secret"
    assert config.player_host == DEFAULT_PLAYER_HOST
    assert config.player_port == DEFAULT_PLAYER_PORT
    assert config.chunk_size == 1536


def test_send_command_rejects_ipv6_player_hosts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    parser = build_parser()
    args = parser.parse_args(
        [
            "send",
            "--source",
            str(source_dir),
            "--password",
            "secret",
            "--player-host",
            "::1",
        ]
    )

    with pytest.raises(ValueError):
        build_sender_config(args)


def test_build_preview_url_normalizes_wildcard_and_ipv6_hosts():
    assert build_preview_url("0.0.0.0", 8765) == "http://127.0.0.1:8765/"
    assert build_preview_url("::", 8765) == "http://127.0.0.1:8765/"
    assert build_preview_url("::1", 8765) == "http://[::1]:8765/"
    assert build_preview_url("example.com", 8765) == "http://example.com:8765/"


def test_handle_send_starts_session_player_and_launches_url(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["send", "--source", str(source_dir), "--password", "secret"])

    calls: list[tuple[str, object]] = []

    class DummyPayloads:
        def __init__(self) -> None:
            self.session_id = b"session"
            self.packet_sequence = [b"packet-1", b"packet-2"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def __init__(self) -> None:
            self.shutdown_called = False
            self.server_close_called = False
            self.player_root = None

        def shutdown(self) -> None:
            self.shutdown_called = True

        def server_close(self) -> None:
            self.server_close_called = True

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append(("build_session_payloads", (source_dir_arg, password_arg, chunk_size_arg)))
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, host, port, player_root=None):
        calls.append(("create_player_app", (payloads_arg, host, port, player_root)))
        return DummyServer()

    def fake_launch_player(url_arg):
        calls.append(("launch_player", url_arg))

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_send(args)

    assert result == 0
    assert calls[0][0] == "build_session_payloads"
    assert calls[1][0] == "create_player_app"
    assert calls[2][0] == "launch_player"
    assert calls[2][1] == "http://127.0.0.1:8765/"
    assert calls[3][0] == "wait_forever"


def test_handle_send_waits_for_preview_and_closes_server(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["send", "--source", str(source_dir), "--password", "secret"])

    calls: list[str] = []

    class DummyPayloads:
        session_id = b"session"
        packet_sequence = [b"packet-1", b"packet-2"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def __init__(self) -> None:
            self.shutdown_called = False
            self.server_close_called = False

        def shutdown(self) -> None:
            self.shutdown_called = True

        def server_close(self) -> None:
            self.server_close_called = True

    server = DummyServer()

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append("build_session_payloads")
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, host, port, player_root=None):
        calls.append("create_player_app")
        return server

    def fake_launch_player(url_arg):
        calls.append("launch_player")

    def fake_wait_forever():
        calls.append("wait_forever")

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_send(args)

    assert result == 0
    assert calls == ["build_session_payloads", "create_player_app", "launch_player", "wait_forever"]
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_handle_send_prints_preview_url_when_browser_launch_fails(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["send", "--source", str(source_dir), "--password", "secret"])

    class DummyPayloads:
        session_id = b"session"
        packet_sequence = [b"packet-1"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, host, port, player_root=None):
        return DummyServer()

    def fake_launch_player(url_arg):
        return False

    def fake_wait_forever():
        return None

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_send(args)

    captured = capsys.readouterr()

    assert result == 0
    assert "http://127.0.0.1:8765/" in captured.out


def test_handle_send_prints_preview_url_when_browser_launch_raises(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["send", "--source", str(source_dir), "--password", "secret"])

    calls: list[str] = []

    class DummyPayloads:
        session_id = b"session"
        packet_sequence = [b"packet-1"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def __init__(self) -> None:
            self.shutdown_called = False
            self.server_close_called = False

        def shutdown(self) -> None:
            self.shutdown_called = True

        def server_close(self) -> None:
            self.server_close_called = True

    server = DummyServer()

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append("build_session_payloads")
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, host, port, player_root=None):
        calls.append("create_player_app")
        return server

    def fake_launch_player(url_arg):
        calls.append("launch_player")
        raise RuntimeError("browser unavailable")

    def fake_wait_forever():
        calls.append("wait_forever")

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_send(args)

    captured = capsys.readouterr()

    assert result == 0
    assert calls == ["build_session_payloads", "create_player_app", "launch_player", "wait_forever"]
    assert "http://127.0.0.1:8765/" in captured.out
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_handle_receive_runs_pipeline_and_prints_session_report(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    packet_iter = iter(session.packet_sequence)
    video_one = tmp_path / "recording1.mp4"
    video_two = tmp_path / "recording2.mp4"
    frame_paths = [tmp_path / f"frame-{index}.png" for index in range(len(session.packet_sequence))]
    restored_dirs: list[Path] = []

    real_restore_archive_bytes = cli_module.restore_archive_bytes

    def fake_extract_frames(video_path, *, output_dir=None, runner=None, ffmpeg_bin="ffmpeg"):
        if Path(video_path) == video_one:
            return frame_paths[:1]
        if Path(video_path) == video_two:
            return frame_paths[1:]
        raise AssertionError(f"unexpected video path: {video_path}")

    def fake_preprocess_frame(frame_path):
        return frame_path

    def fake_decode_qr_payload(image):
        return next(packet_iter)

    def fake_restore_archive_bytes(archive_bytes, output_root):
        restored_dir = real_restore_archive_bytes(archive_bytes, output_root)
        restored_dirs.append(restored_dir)
        return restored_dir

    monkeypatch.setattr(cli_module, "extract_frames", fake_extract_frames, raising=False)
    monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
    monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)
    monkeypatch.setattr(cli_module, "restore_archive_bytes", fake_restore_archive_bytes, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "receive",
            str(video_one),
            str(video_two),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    result = cli_module.handle_receive(args)
    captured = capsys.readouterr()

    assert result == 0
    assert "input video count: 2" in captured.out
    assert f"total extracted frame count: {len(session.packet_sequence)}" in captured.out
    assert f"successfully decoded frame count: {len(session.packet_sequence)}" in captured.out
    assert f"raw packet count: {len(session.packet_sequence)}" in captured.out
    assert f"deduplicated valid chunk count: {session.total_chunks}" in captured.out
    assert "final archive hash result: match" in captured.out
    assert restored_dirs and restored_dirs[0].exists()
    assert (restored_dirs[0] / "message.txt").read_text(encoding="utf-8") == "hello"


def test_session_report_includes_required_summary_fields():
    report = build_session_report(
        SessionStats(
            input_video_count=2,
            total_extracted_frame_count=12,
            successfully_decoded_frame_count=9,
            raw_packet_count=8,
            deduplicated_valid_chunk_count=4,
            missing_chunk_count=0,
            authentication_failure_count=1,
            final_archive_hash_result="match",
            stage_timings={"extract_frames": 1.234, "restore": 0.456},
            restored_directory=Path("/tmp/restored-abc"),
        )
    )

    assert "input video count: 2" in report
    assert "total extracted frame count: 12" in report
    assert "successfully decoded frame count: 9" in report
    assert "raw packet count: 8" in report
    assert "deduplicated valid chunk count: 4" in report
    assert "missing chunk count: 0" in report
    assert "authentication failure count: 1" in report
    assert "final archive hash result: match" in report
    assert "restored directory: /tmp/restored-abc" in report
    assert "per-stage timing:" in report
    assert "extract_frames: 1.234s" in report
    assert "restore: 0.456s" in report


def test_player_server_defaults_to_sender_port():
    assert inspect.signature(create_player_app).parameters["port"].default == DEFAULT_PLAYER_PORT


def test_player_server_serves_assets_without_repo_files(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    payloads = build_session_payloads(source_dir, password="secret", chunk_size=32)
    server = create_player_app(payloads, port=0, player_root=Path("/does/not/exist"))

    try:
        base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"
        with urllib.request.urlopen(f"{base_url}/") as response:
            index_html = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{base_url}/player.js") as response:
            player_js = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()

    assert "Optical Transfer" in index_html
    assert "loadPayload" in player_js


def test_player_server_exposes_packet_sequence_json(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    payloads = build_session_payloads(source_dir, password="secret", chunk_size=32)
    server = create_player_app(payloads, port=0)

    try:
        with urllib.request.urlopen(f"http://{server.server_address[0]}:{server.server_address[1]}/payload.json") as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert payload["session_id"]
    assert payload["packet_sequence"]
    assert len(payload["packet_sequence"]) == len(payloads.packet_sequence)


def test_main_requires_a_subcommand():
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code != 0
