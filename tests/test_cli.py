import pytest

from optical_transfer.cli import build_parser, main


def test_parser_accepts_send_and_receive_subcommands():
    parser = build_parser()
    assert parser.parse_args(["send"]).command == "send"
    assert parser.parse_args(["receive"]).command == "receive"


def test_main_requires_a_subcommand():
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code != 0
