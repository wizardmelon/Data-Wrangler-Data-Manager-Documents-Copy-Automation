import os

from dm_backup import workflows, diskutils


def test_find_day_folder_on_disk_present(tmp_path):
    disk = tmp_path / "ODC_BACKUP_01"
    (disk / "DAY010_20251122").mkdir(parents=True)
    found = workflows.find_day_folder_on_disk(str(disk), "DAY010")
    assert found is not None
    assert found.endswith("DAY010_20251122")


def test_find_day_folder_on_disk_missing(tmp_path):
    disk = tmp_path / "ODC_BACKUP_01"
    (disk / "DAY099_20251122").mkdir(parents=True)
    assert workflows.find_day_folder_on_disk(str(disk), "DAY010") is None


def test_find_day_folder_nonexistent_disk(tmp_path):
    assert workflows.find_day_folder_on_disk(str(tmp_path / "nope"), "DAY010") is None


def test_find_spola_disks(tmp_path):
    volumes = tmp_path / "Volumes"
    (volumes / "ODC_SPOLA_03").mkdir(parents=True)
    (volumes / "ODC_SPOLA_04").mkdir()
    (volumes / "Macintosh HD").mkdir()
    found = diskutils.find_spola_disks("ODC_SPOLA", str(volumes))
    assert found == ["ODC_SPOLA_03", "ODC_SPOLA_04"]


def test_has_enough_space(tmp_path):
    # La cartella tmp ha sicuramente spazio per 10 byte.
    assert diskutils.has_enough_space(str(tmp_path), 10) is True
