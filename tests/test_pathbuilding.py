import datetime
import os

from dm_backup import workflows
from dm_backup.config import shoot_date


def test_shoot_date_offset():
    # Con offset 0 la data è quella di oggi; con offset grande può tornare a ieri.
    today = datetime.datetime.now().strftime("%Y%m%d")
    assert shoot_date(0) == today
    # 26 ore fa è sempre un giorno diverso da oggi.
    assert shoot_date(26) != today


def test_build_folder_name():
    name = workflows.build_folder_name("023", offset_hours=0)
    today = datetime.datetime.now().strftime("%Y%m%d")
    assert name == f"DAY023_{today}"


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
