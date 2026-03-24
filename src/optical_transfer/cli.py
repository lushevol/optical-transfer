from __future__ import annotations

import argparse
import webbrowser
from contextlib import suppress
import ipaddress
from pathlib import Path
from threading import Event

from optical_transfer.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PLAYER_HOST,
    DEFAULT_PLAYER_PORT,
    SenderConfig,
)
from optical_transfer.sender.player_server import create_player_app
from optical_transfer.sender.session import build_session_payloads


def build_sender_config(args: argparse.Namespace) -> SenderConfig:
    player_host = _validate_player_host(args.player_host)
    return SenderConfig(
        source_dir=Path(args.source),
        password=args.password,
        chunk_size=args.chunk_size,
        player_host=player_host,
        player_port=args.player_port,
    )


def launch_player(url: str) -> bool:
    return webbrowser.open(url)


def build_preview_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    else:
        with suppress(ValueError):
            if ipaddress.ip_address(host).version == 6:
                host = f"[{host}]"
    return f"http://{host}:{port}/"


def _validate_player_host(host: str) -> str:
    normalized = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        parsed_host = ipaddress.ip_address(normalized)
    except ValueError:
        return host
    if parsed_host.version == 6:
        raise ValueError("IPv6 player hosts are not supported by the sender preview server")
    return host


def wait_forever() -> None:
    with suppress(KeyboardInterrupt):
        Event().wait()


def run_preview_session(
    server,
    *,
    launch_fn=launch_player,
    wait_fn=wait_forever,
) -> None:
    preview_url = build_preview_url(server.server_address[0], server.server_address[1])
    try:
        try:
            launched = launch_fn(preview_url)
        except Exception:
            launched = False
        if not launched:
            print(f"Preview URL: {preview_url}")
        wait_fn()
    finally:
        server.shutdown()
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optical-transfer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--source", default=".")
    send_parser.add_argument("--password", default="")
    send_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    send_parser.add_argument("--player-host", default=DEFAULT_PLAYER_HOST)
    send_parser.add_argument("--player-port", type=int, default=DEFAULT_PLAYER_PORT)

    subparsers.add_parser("receive")
    return parser


def handle_send(args: argparse.Namespace) -> int:
    config = build_sender_config(args)
    payloads = build_session_payloads(config.source_dir, config.password, config.chunk_size)
    server = create_player_app(
        payloads,
        host=config.player_host,
        port=config.player_port,
        player_root=config.player_root,
    )
    run_preview_session(server, launch_fn=launch_player, wait_fn=wait_forever)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "send":
        return handle_send(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
