import os

from dm_backup import workflows


def test_list_day_folders(tmp_path):
    daily = tmp_path / "DAILY_FILES"
    (daily / "DAY023_20260525").mkdir(parents=True)
    (daily / "DAY024_20260526").mkdir()
    (daily / "ISIDE_SHUTTLE13").mkdir()   # cartella spola, NON un DAY
    (daily / "note.txt").write_text("x")
    assert workflows.list_day_folders(str(daily)) == ["DAY023_20260525", "DAY024_20260526"]


def test_day_number():
    assert workflows.day_number("DAY023_20260525") == "023"
    assert workflows.day_number("qualcosa") == ""


def test_detect_day_from_stills(tmp_path):
    still_dir = tmp_path / "05_STILL"
    still_dir.mkdir()
    (still_dir / "SC1_A092C002_260525_RPJ2.mxf_DAY023_1.2.1.dpx").write_text("x")
    (still_dir / "SC9_B092C003_260525_ROYQ.mxf_DAY023_1.104.3.drx").write_text("x")
    (still_dir / "SC1_x_DAY024_1.1.jpg").write_text("x")
    (still_dir / "ignore.txt").write_text("x")
    assert workflows.detect_day_from_stills(str(still_dir)) == ["023", "024"]


def test_detect_day_empty_folder(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert workflows.detect_day_from_stills(str(d)) == []
