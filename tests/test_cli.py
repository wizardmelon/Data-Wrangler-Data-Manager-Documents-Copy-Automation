from dm_backup.__main__ import build_parser


def test_still_parser_flags():
    p = build_parser()
    assert p.parse_args(["still"]).drx is False
    assert p.parse_args(["still", "--drx"]).drx is True


def test_files_notification_format():
    from dm_backup.workflows import format_files_notification
    title, sub, body = format_files_notification(
        "DAY012_20251122", [("04_DRP+ALE", 12), ("05_STILLS", 30)],
        [("TQCC_Work01", 140, True), ("TQCC_TRAVELER01", 140, True)])
    assert title == "DAY012_20251122 · Backup completato"
    assert sub == "Verificato su 2 volumi"
    assert body.splitlines() == [
        "Cartelle: 04_DRP+ALE (12), 05_STILLS (30)",
        "✓ TQCC_Work01 (140 file)",
        "✓ TQCC_TRAVELER01 (140 file)",
    ]


def test_still_and_files_new_options():
    p = build_parser()
    a = p.parse_args(["still", "--mode", "minutes", "--minutes", "10"])
    assert a.mode == "minutes" and a.minutes == 10
    assert p.parse_args(["still"]).mode is None and p.parse_args(["still"]).minutes is None
    assert p.parse_args(["files", "--day-offset", "9"]).day_offset == 9
    assert p.parse_args(["files"]).day_offset is None
