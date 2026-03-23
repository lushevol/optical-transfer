from optical_transfer.cli import build_parser


def test_parser_exposes_send_and_receive_commands():
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    assert "send" in subcommands
    assert "receive" in subcommands
