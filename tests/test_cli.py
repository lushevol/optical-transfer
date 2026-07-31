import inspect
import json
from pathlib import Path
from typing import List, Tuple
import urllib.request

import atlasx.cli as cli_module
import pytest

from atlasx.cli import build_parser, build_preview_url, build_foo_config, handle_foo, main
from atlasx.config import DEFAULT_CHUNK_SIZE, DEFAULT_FRAME_INTERVAL_MS, DEFAULT_PLAYER_HOST, DEFAULT_PLAYER_PORT
from atlasx.bar.report import SessionStats, build_session_report
from atlasx.foo.player_server import create_player_app
from atlasx.foo.session import build_session_payloads


@pytest.fixture(autouse=True)
def _default_noop_session_bundle_save(monkeypatch):
    monkeypatch.setattr(cli_module, "save_session_bundle", lambda source_dir, payloads: None, raising=False)


def test_parser_accepts_foo_and_bar_subcommands():
    parser = build_parser()
    assert parser.parse_args(["foo"]).command == "foo"
    assert parser.parse_args(["bar", "recording.mp4"]).command == "bar"


def test_bar_command_accepts_multiple_videos():
    parser = build_parser()
    args = parser.parse_args(["bar", "recording1.mp4", "recording2.mp4", "--password", "secret"])

    assert args.videos == ["recording1.mp4", "recording2.mp4"]
    assert args.password == "secret"


def test_bar_command_accepts_decode_workers_override():
    parser = build_parser()
    args = parser.parse_args(["bar", "recording.mp4", "--decode-workers", "1"])

    assert args.decode_workers == 1


def test_foo_command_builds_default_foo_config(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret"])

    config = build_foo_config(args)

    assert config.source_dir == source_dir
    assert config.password == "secret"
    assert config.player_host == DEFAULT_PLAYER_HOST
    assert config.player_port == DEFAULT_PLAYER_PORT
    assert config.frame_interval_ms == DEFAULT_FRAME_INTERVAL_MS
    assert config.chunk_size == DEFAULT_CHUNK_SIZE
    assert config.chunk_size >= 256


def test_foo_command_does_not_open_browser_by_default():
    parser = build_parser()
    args = parser.parse_args(["foo"])

    assert args.open_browser is False


def test_foo_command_accepts_frame_interval_override():
    parser = build_parser()
    args = parser.parse_args(["foo", "--frame-interval-ms", "450"])

    assert args.frame_interval_ms == 450


def test_foo_command_accepts_missing_chunks_option():
    parser = build_parser()
    args = parser.parse_args(
        [
            "foo",
            "--session-id",
            "00112233445566778899aabbccddeeff",
            "--missing-chunks",
            "3, 7,9",
        ]
    )

    assert args.missing_chunks == "3, 7,9"
    assert args.session_id == "00112233445566778899aabbccddeeff"
    assert cli_module.parse_missing_chunk_indexes(args.missing_chunks) == [3, 7, 9]


@pytest.mark.parametrize("value", ["", " ", "1,,2", "-1", "1,a", "2,1,2"])
def test_parse_missing_chunk_indexes_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        cli_module.parse_missing_chunk_indexes(value)


def test_foo_command_rejects_ipv6_player_hosts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    parser = build_parser()
    args = parser.parse_args(
        [
            "foo",
            "--source",
            str(source_dir),
            "--password",
            "secret",
            "--player-host",
            "::1",
        ]
    )

    with pytest.raises(ValueError):
        build_foo_config(args)


def test_build_preview_url_normalizes_wildcard_and_ipv6_hosts():
    assert build_preview_url("0.0.0.0", 8765) == "http://127.0.0.1:8765/"
    assert build_preview_url("::", 8765) == "http://127.0.0.1:8765/"
    assert build_preview_url("::1", 8765) == "http://[::1]:8765/"
    assert build_preview_url("example.com", 8765) == "http://example.com:8765/"


def test_handle_foo_prints_preview_url_without_opening_browser_by_default(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret"])

    calls: List[Tuple[str, object]] = []

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

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append(("create_player_app", (payloads_arg, frame_interval_ms, host, port, player_root)))
        return DummyServer()

    def fake_launch_player(url_arg):
        calls.append(("launch_player", url_arg))

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_foo(args)
    captured = capsys.readouterr()

    assert result == 0
    assert calls[0][0] == "build_session_payloads"
    assert calls[1][0] == "create_player_app"
    assert "http://127.0.0.1:8765/" in captured.out
    assert ("launch_player", "http://127.0.0.1:8765/") not in calls
    assert calls[2][0] == "wait_forever"


def test_handle_foo_opens_browser_when_requested(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret", "--open-browser"])

    calls: List[Tuple[str, object]] = []

    class DummyPayloads:
        session_id = b"session"
        packet_sequence = [b"packet-1", b"packet-2"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append(("build_session_payloads", (source_dir_arg, password_arg, chunk_size_arg)))
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append(("create_player_app", (payloads_arg, frame_interval_ms, host, port, player_root)))
        return DummyServer()

    def fake_launch_player(url_arg):
        calls.append(("launch_player", url_arg))
        return True

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_foo(args)

    assert result == 0
    assert calls[0][0] == "build_session_payloads"
    assert calls[1][0] == "create_player_app"
    assert calls[2] == ("launch_player", "http://127.0.0.1:8765/")
    assert calls[3][0] == "wait_forever"


def test_handle_foo_passes_frame_interval_to_player_server(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        ["foo", "--source", str(source_dir), "--password", "secret", "--frame-interval-ms", "450"]
    )

    calls: List[Tuple[str, object]] = []

    class DummyPayloads:
        session_id = b"session"
        packet_sequence = [b"packet-1", b"packet-2"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append(("build_session_payloads", (source_dir_arg, password_arg, chunk_size_arg)))
        return DummyPayloads()

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append(("create_player_app", (payloads_arg, frame_interval_ms, host, port, player_root)))
        return DummyServer()

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_foo(args)

    assert result == 0
    assert calls[1][0] == "create_player_app"
    assert calls[1][1][1] == 450


def test_handle_foo_waits_for_preview_and_closes_server(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret"])

    calls: List[str] = []

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

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append("create_player_app")
        return server

    def fake_wait_forever():
        calls.append("wait_forever")

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_foo(args)

    assert result == 0
    assert calls == ["build_session_payloads", "create_player_app", "wait_forever"]
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_handle_foo_saves_session_bundle_after_full_build(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret"])

    calls: List[Tuple[str, object]] = []

    class DummyPayloads:
        session_id = b"session"
        chunk_size = 64
        total_chunks = 2
        manifest_packet = b"manifest"
        data_packets = [b"chunk-0", b"chunk-1"]
        packet_sequence = [b"manifest", b"chunk-0", b"chunk-1"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    def fake_build_session_payloads(source_dir_arg, password_arg, chunk_size_arg):
        calls.append(("build_session_payloads", (source_dir_arg, password_arg, chunk_size_arg)))
        return DummyPayloads()

    def fake_save_session_bundle(source_dir_arg, payloads_arg):
        calls.append(("save_session_bundle", (source_dir_arg, payloads_arg)))

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append(("create_player_app", payloads_arg))
        return DummyServer()

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "save_session_bundle", fake_save_session_bundle, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    assert handle_foo(args) == 0

    assert calls[0][0] == "build_session_payloads"
    assert calls[1][0] == "save_session_bundle"
    assert calls[1][1][0] == source_dir
    assert calls[2][0] == "create_player_app"


def test_handle_foo_uses_saved_bundle_for_missing_chunks(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    parser = build_parser()
    args = parser.parse_args(
        [
            "foo",
            "--source",
            str(source_dir),
            "--session-id",
            "00112233445566778899aabbccddeeff",
            "--missing-chunks",
            "1,3",
        ]
    )

    calls: List[Tuple[str, object]] = []

    class DummyPayloads:
        session_id = bytes.fromhex("00112233445566778899aabbccddeeff")
        total_chunks = 4
        packet_sequence = [b"full"]

    class FilteredPayloads:
        session_id = b"session"
        packet_sequence = [b"manifest", b"chunk-1", b"chunk-3"]

    class DummyServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self) -> None:
            pass

        def server_close(self) -> None:
            pass

    def fake_load_session_bundle(source_dir_arg):
        calls.append(("load_session_bundle", source_dir_arg))
        return DummyPayloads()

    def fake_filter_session_payloads(payloads_arg, missing_indexes_arg):
        calls.append(("filter_session_payloads", (payloads_arg, missing_indexes_arg)))
        return FilteredPayloads()

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        calls.append(("create_player_app", payloads_arg))
        return DummyServer()

    def fake_wait_forever():
        calls.append(("wait_forever", None))

    monkeypatch.setattr(cli_module, "load_session_bundle", fake_load_session_bundle, raising=False)
    monkeypatch.setattr(cli_module, "filter_session_payloads", fake_filter_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    assert handle_foo(args) == 0

    assert calls[0] == ("load_session_bundle", source_dir)
    assert calls[1][0] == "filter_session_payloads"
    assert calls[1][1][1] == [1, 3]
    assert calls[2][0] == "create_player_app"
    assert isinstance(calls[2][1], FilteredPayloads)


def test_handle_foo_rejects_missing_chunks_from_a_different_saved_session(
    tmp_path, monkeypatch
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    class SavedPayloads:
        session_id = bytes.fromhex("ffeeddccbbaa99887766554433221100")

    monkeypatch.setattr(
        cli_module,
        "load_session_bundle",
        lambda _source_dir: SavedPayloads(),
        raising=False,
    )

    args = build_parser().parse_args(
        [
            "foo",
            "--source",
            str(source_dir),
            "--session-id",
            "00112233445566778899aabbccddeeff",
            "--missing-chunks",
            "1,3",
        ]
    )

    with pytest.raises(ValueError, match="does not match the bar recovery request"):
        handle_foo(args)


def test_handle_foo_requires_session_id_for_missing_chunk_playback():
    args = build_parser().parse_args(["foo", "--missing-chunks", "1,3"])

    with pytest.raises(ValueError, match="requires --session-id"):
        handle_foo(args)


def test_handle_foo_prints_preview_url_when_open_browser_requested_but_launch_fails(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret", "--open-browser"])

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

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
        return DummyServer()

    def fake_launch_player(url_arg):
        return False

    def fake_wait_forever():
        return None

    monkeypatch.setattr(cli_module, "build_session_payloads", fake_build_session_payloads, raising=False)
    monkeypatch.setattr(cli_module, "create_player_app", fake_create_player_app, raising=False)
    monkeypatch.setattr(cli_module, "launch_player", fake_launch_player, raising=False)
    monkeypatch.setattr(cli_module, "wait_forever", fake_wait_forever, raising=False)

    result = handle_foo(args)

    captured = capsys.readouterr()

    assert result == 0
    assert "http://127.0.0.1:8765/" in captured.out


def test_handle_foo_prints_preview_url_when_open_browser_requested_but_launch_raises(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["foo", "--source", str(source_dir), "--password", "secret", "--open-browser"])

    calls: List[str] = []

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

    def fake_create_player_app(payloads_arg, *, frame_interval_ms, host, port, player_root=None):
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

    result = handle_foo(args)

    captured = capsys.readouterr()

    assert result == 0
    assert calls == ["build_session_payloads", "create_player_app", "launch_player", "wait_forever"]
    assert "http://127.0.0.1:8765/" in captured.out
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_handle_bar_runs_pipeline_and_prints_session_report(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    packet_iter = iter(session.packet_sequence)
    video_one = tmp_path / "recording1.mp4"
    video_two = tmp_path / "recording2.mp4"
    frame_tokens = [f"frame-{index}" for index in range(len(session.packet_sequence))]
    def fake_iter_video_frames(video_path):
        if Path(video_path) == video_one:
            yield frame_tokens[0]
            return
        if Path(video_path) == video_two:
            yield from frame_tokens[1:]
            return
        raise AssertionError(f"unexpected video path: {video_path}")

    def fake_preprocess_frame(frame_path):
        return frame_path

    def fake_decode_qr_payload(image):
        return next(packet_iter)

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
    monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
    monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(video_one),
            str(video_two),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    result = cli_module.handle_bar(args)
    captured = capsys.readouterr()

    assert result == 0
    assert "bar: starting decode for 2 video(s)" in captured.out
    assert "bar: reading video 1/2:" in captured.out
    assert "bar: restoring independent bundle records from" in captured.out
    assert "bar: complete, restored directory:" in captured.out
    assert "input video count: 2" in captured.out
    assert f"total extracted frame count: {len(session.packet_sequence)}" in captured.out
    assert f"successfully decoded frame count: {len(session.packet_sequence)}" in captured.out
    assert f"raw packet count: {len(session.packet_sequence)}" in captured.out
    assert f"deduplicated valid chunk count: {session.total_chunks}" in captured.out
    assert "final archive hash result: match" in captured.out
    restored_dirs = [
        path
        for path in (tmp_path / "restored").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    assert len(restored_dirs) == 1
    assert (restored_dirs[0] / "message.txt").read_text(encoding="utf-8") == "hello"


def test_handle_bar_reports_session_ids_for_incompatible_recordings(
    tmp_path, monkeypatch
):
    source_one = tmp_path / "source-one"
    source_two = tmp_path / "source-two"
    source_one.mkdir()
    source_two.mkdir()
    (source_one / "message.txt").write_text("one", encoding="utf-8")
    (source_two / "message.txt").write_text("two", encoding="utf-8")
    session_one = build_session_payloads(source_one, password="secret", chunk_size=64)
    session_two = build_session_payloads(source_two, password="secret", chunk_size=64)
    packets = iter([session_one.manifest_packet, session_two.manifest_packet])

    monkeypatch.setattr(
        cli_module,
        "iter_video_frames",
        lambda _video_path: iter(["frame-one", "frame-two"]),
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "preprocess_frame",
        lambda frame_path: frame_path,
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "decode_qr_payload",
        lambda _image: next(packets),
        raising=False,
    )

    args = build_parser().parse_args(
        [
            "bar",
            str(tmp_path / "recording.mp4"),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        cli_module.handle_bar(args)

    message = str(exc_info.value)
    assert "different sessions and cannot be merged" in message
    assert session_one.session_id.hex() in message
    assert session_two.session_id.hex() in message
    assert f"({session_one.total_chunks} chunks)" in message
    assert f"({session_two.total_chunks} chunks)" in message


def test_handle_bar_passes_decode_workers_to_frame_decoder(tmp_path, monkeypatch):
    from atlasx.bar.frame_decode import FrameDecodeResult

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    video_path = tmp_path / "recording.mp4"
    frame_tokens = [f"frame-{index}" for index in range(len(session.packet_sequence))]
    observed_worker_counts: list[int] = []

    real_restore_archive_bytes = cli_module.restore_archive_bytes

    def fake_iter_video_frames(_video_path):
        yield from frame_tokens

    def fake_iter_decoded_frames(frames, preprocess_frame, decode_qr_payload, *, worker_count):
        observed_worker_counts.append(worker_count)
        for frame_number, (_frame, packet_bytes) in enumerate(zip(frames, session.packet_sequence), start=1):
            yield FrameDecodeResult(frame_number=frame_number, packet_bytes=packet_bytes)

    def fake_restore_archive_bytes(archive_bytes, output_root):
        return real_restore_archive_bytes(archive_bytes, output_root)

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
    monkeypatch.setattr(cli_module, "iter_decoded_frames", fake_iter_decoded_frames, raising=False)
    monkeypatch.setattr(cli_module, "restore_archive_bytes", fake_restore_archive_bytes, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(video_path),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
            "--decode-workers",
            "3",
        ]
    )

    result = cli_module.handle_bar(args)

    assert result == 0
    assert observed_worker_counts == [3]


def test_handle_bar_skips_unparseable_frame_without_losing_progress(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    packet_iter = iter(session.packet_sequence)
    frame_tokens = ["bad-frame"] + [f"frame-{index}" for index in range(len(session.packet_sequence))]

    def fake_iter_video_frames(_video_path):
        yield from frame_tokens

    def fake_preprocess_frame(frame_path):
        return frame_path

    def fake_decode_qr_payload(image):
        if image == "bad-frame":
            raise ValueError("cannot parse QR payload")
        return next(packet_iter)

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
    monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
    monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(tmp_path / "recording.mp4"),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    result = cli_module.handle_bar(args)

    restored_dirs = [
        path
        for path in (tmp_path / "restored").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    assert result == 0
    assert len(restored_dirs) == 1
    assert (restored_dirs[0] / "message.txt").read_text(encoding="utf-8") == "hello"


def test_handle_bar_restores_archive_when_first_manifest_frame_is_missing(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    packet_iter = iter(session.packet_sequence[1:])
    frame_tokens = [f"frame-{index}" for index in range(len(session.packet_sequence) - 1)]

    def fake_iter_video_frames(video_path):
        yield from frame_tokens

    def fake_preprocess_frame(frame_path):
        return frame_path

    def fake_decode_qr_payload(image):
        return next(packet_iter)

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
    monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
    monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(tmp_path / "recording.mp4"),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    result = cli_module.handle_bar(args)

    restored_dirs = [
        path
        for path in (tmp_path / "restored").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    assert result == 0
    assert len(restored_dirs) == 1
    assert (restored_dirs[0] / "message.txt").read_text(encoding="utf-8") == "hello"


def test_handle_bar_restores_bundle_when_all_manifest_frames_are_missing(
    tmp_path,
    monkeypatch,
    capsys,
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_text("hello", encoding="utf-8")

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    packets = [
        packet
        for packet in session.packet_sequence
        if packet != session.manifest_packet
    ]
    packet_iter = iter(packets)

    monkeypatch.setattr(
        cli_module,
        "iter_video_frames",
        lambda _video_path: iter(["frame"] * len(packets)),
        raising=False,
    )
    monkeypatch.setattr(cli_module, "preprocess_frame", lambda frame: frame, raising=False)
    monkeypatch.setattr(
        cli_module,
        "decode_qr_payload",
        lambda _image: next(packet_iter),
        raising=False,
    )

    args = build_parser().parse_args(
        [
            "bar",
            str(tmp_path / "recording.mp4"),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    assert cli_module.handle_bar(args) == 0
    captured = capsys.readouterr()
    assert "final archive hash result: incomplete" in captured.out
    restored_dirs = [
        path
        for path in (tmp_path / "restored").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    assert len(restored_dirs) == 1
    assert (restored_dirs[0] / "message.txt").read_text(encoding="utf-8") == "hello"


def test_handle_bar_partially_restores_when_chunk_is_missing(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_bytes(b"x" * 4096)

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    missing_packet = session.data_packets[-1]
    packet_stream = iter(
        packet
        for packet in session.packet_sequence
        if packet != missing_packet
    )
    frame_tokens = ["frame"] * (len(session.packet_sequence) - session.packet_sequence.count(missing_packet))

    def fake_iter_video_frames(_video_path):
        yield from frame_tokens

    def fake_preprocess_frame(frame_path):
        return frame_path

    def fake_decode_qr_payload(_image):
        return next(packet_stream)

    monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
    monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
    monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)

    parser = build_parser()
    args = parser.parse_args(
        [
            "bar",
            str(tmp_path / "recording.mp4"),
            "--password",
            "secret",
            "--output-root",
            str(tmp_path / "restored"),
        ]
    )

    assert cli_module.handle_bar(args) == 0
    captured = capsys.readouterr()
    assert "partial recovery complete; missing chunk indexes:" in captured.out
    assert (
        f"recovery playback arguments: --session-id {session.session_id.hex()}"
        in captured.out
    )
    assert "final archive hash result: incomplete" in captured.out
    restored_dirs = [
        path
        for path in (tmp_path / "restored").iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    assert len(restored_dirs) == 1
    assert not (restored_dirs[0] / "message.txt").exists()
    assert any((restored_dirs[0] / ".atlasx-partial").rglob("*.part-*"))


def test_handle_bar_resumes_from_saved_progress_after_missing_chunk(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "message.txt").write_bytes(b"x" * 4096)

    session = build_session_payloads(source_dir, password="secret", chunk_size=64)
    missing_packet = session.data_packets[-1]
    output_root = tmp_path / "restored"
    parser = build_parser()

    def run_with_packets(packets):
        packet_iter = iter(packets)
        frame_tokens = ["frame"] * len(packets)

        def fake_iter_video_frames(_video_path):
            yield from frame_tokens

        def fake_preprocess_frame(frame_path):
            return frame_path

        def fake_decode_qr_payload(_image):
            return next(packet_iter)

        monkeypatch.setattr(cli_module, "iter_video_frames", fake_iter_video_frames, raising=False)
        monkeypatch.setattr(cli_module, "preprocess_frame", fake_preprocess_frame, raising=False)
        monkeypatch.setattr(cli_module, "decode_qr_payload", fake_decode_qr_payload, raising=False)

        args = parser.parse_args(
            [
                "bar",
                str(tmp_path / "recording.mp4"),
                "--password",
                "secret",
                "--output-root",
                str(output_root),
            ]
        )
        return cli_module.handle_bar(args)

    first_run_packets = [
        packet
        for packet in session.packet_sequence
        if packet != missing_packet
    ]

    assert run_with_packets(first_run_packets) == 0

    assert run_with_packets([missing_packet]) == 0

    restored_dirs = [path for path in output_root.iterdir() if path.is_dir() and not path.name.startswith(".")]
    assert len(restored_dirs) == 2
    completed_dirs = [path for path in restored_dirs if (path / "message.txt").exists()]
    assert len(completed_dirs) == 1
    assert (completed_dirs[0] / "message.txt").read_bytes() == b"x" * 4096


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


def test_player_server_defaults_to_foo_port():
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
        with urllib.request.urlopen(f"{base_url}/player.css") as response:
            player_css = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()

    assert "AtlasX" in index_html
    assert "loadPayload" in player_js
    assert "width: min(90vmin, 80rem);" in player_css
    assert "32rem" not in player_css


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
    assert payload["frame_interval_ms"] == DEFAULT_FRAME_INTERVAL_MS
    assert payload["packet_sequence"]
    assert payload["frame_sequence"]
    assert len(payload["packet_sequence"]) == len(payloads.packet_sequence)
    assert len(payload["frame_sequence"]) == len(payloads.packet_sequence)


def test_main_requires_a_subcommand():
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code != 0


def test_main_accepts_bar_password_after_videos(monkeypatch):
    captured_args = []

    def fake_handle_bar(args):
        captured_args.append(args)
        return 0

    monkeypatch.setattr(cli_module, "handle_bar", fake_handle_bar, raising=False)

    result = main(["bar", "IMG_7595.MOV", "--password", "secret"])

    assert result == 0
    assert captured_args[0].videos == ["IMG_7595.MOV"]
    assert captured_args[0].password == "secret"
