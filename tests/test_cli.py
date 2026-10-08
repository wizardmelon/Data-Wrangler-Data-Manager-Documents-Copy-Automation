from dm_backup.__main__ import build_parser


def test_still_parser_flags():
    p = build_parser()
    assert p.parse_args(["still"]).drx is False
    assert p.parse_args(["still", "--drx"]).drx is True
