import inspect
import json
import urllib.request

import pytest

from optical_transfer.cli import build_parser, build_sender_config, main
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
