import os

from dm_backup import workflows, diskutils


def test_find_day_folder_on_disk_present(tmp_path):
    disk = tmp_path / "ISIDE_MASTER01"
    (disk / "DAY023_20260525").mkdir(parents=True)
    found = workflows.find_day_folder_on_disk(str(disk), "023")
    assert found is not None
    assert found.endswith("DAY023_20260525")


def test_find_day_folder_on_disk_missing(tmp_path):
    disk = tmp_path / "ISIDE_MASTER01"
    (disk / "DAY099_20260525").mkdir(parents=True)
    assert workflows.find_day_folder_on_disk(str(disk), "023") is None


def test_find_day_folder_nonexistent_disk(tmp_path):
    assert workflows.find_day_folder_on_disk(str(tmp_path / "nope"), "023") is None


def test_find_spola_disks(tmp_path):
    volumes = tmp_path / "Volumes"
    (volumes / "ISIDE_SHUTTLE13").mkdir(parents=True)
    (volumes / "ISIDE_SHUTTLE14").mkdir()
    (volumes / "ISIDE_MASTER01").mkdir()
    (volumes / "Macintosh HD").mkdir()
    found = diskutils.find_spola_disks("ISIDE_SHUTTLE", str(volumes))
    assert found == ["ISIDE_SHUTTLE13", "ISIDE_SHUTTLE14"]


def test_has_enough_space(tmp_path):
    assert diskutils.has_enough_space(str(tmp_path), 10) is True


def test_resolve_fixed_disk_exact_match(tmp_path):
    volumes = tmp_path / "Volumes"
    (volumes / "TQCC_MASTER01").mkdir(parents=True)
    assert workflows.resolve_fixed_disk("TQCC_MASTER01", str(volumes)) == "TQCC_MASTER01"


def test_resolve_fixed_disk_prefix_match(tmp_path):
    # Il nome del disco WORK cambia ogni giorno (TQCC_Work01, TQCC_Work02, ...):
    # il config usa un prefisso, risolto per contenuto come la spola.
    volumes = tmp_path / "Volumes"
    (volumes / "TQCC_Work02").mkdir(parents=True)
    assert workflows.resolve_fixed_disk("TQCC_Work", str(volumes)) == "TQCC_Work02"


def test_resolve_fixed_disk_not_mounted(tmp_path):
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    try:
        workflows.resolve_fixed_disk("TQCC_MASTER01", str(volumes))
        assert False, "doveva sollevare RuntimeError"
    except RuntimeError:
        pass
