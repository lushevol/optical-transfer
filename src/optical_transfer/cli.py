from __future__ import annotations

import argparse
from pathlib import Path

from optical_transfer.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_PLAYER_HOST,
    DEFAULT_PLAYER_PORT,
    SenderConfig,
)


def build_sender_config(args: argparse.Namespace) -> SenderConfig:
    return SenderConfig(
        source_dir=Path(args.source),
        password=args.password,
        chunk_size=args.chunk_size,
        player_host=args.player_host,
        player_port=args.player_port,
    )


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
    build_sender_config(args)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "send":
        return handle_send(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
