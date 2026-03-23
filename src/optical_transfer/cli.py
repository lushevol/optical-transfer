from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optical-transfer")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("send")
    subparsers.add_parser("receive")
    return parser
