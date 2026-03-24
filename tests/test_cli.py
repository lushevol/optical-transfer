import inspect
import json
import urllib.request

import optical_transfer.cli as cli_module
import pytest

from optical_transfer.cli import build_parser, build_sender_config, handle_send, main
from optical_transfer.config import DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_PORT
from optical_transfer.sender.player_server import create_player_app
from optical_transfer.sender.session import build_session_payloads


def test_parser_accepts_send_and_receive_subcommands():
    parser = build_parser()
    assert parser.parse_args(["send"]).command == "send"
    assert parser.parse_args(["receive"]).command == "receive"


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
    assert config.chunk_size > 0


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


def test_player_server_defaults_to_sender_port():
    assert inspect.signature(create_player_app).parameters["port"].default == DEFAULT_PLAYER_PORT


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
