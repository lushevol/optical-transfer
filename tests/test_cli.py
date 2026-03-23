from optical_transfer.cli import build_parser, main


def test_parser_accepts_send_and_receive_subcommands():
    parser = build_parser()
    assert parser.parse_args(["send"]).command == "send"
    assert parser.parse_args(["receive"]).command == "receive"


def test_main_is_exposed_for_console_scripts():
    assert main([]) == 0
