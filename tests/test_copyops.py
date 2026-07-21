import os

from odc_backup import copyops


def _make_tree(root, files):
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)


def test_copy_into_merges_without_nesting(tmp_path):
    src = tmp_path / "DRP"
    dest_day = tmp_path / "disk" / "DAY010_20251122"
    _make_tree(str(src), {"a.txt": "A", "sub/b.txt": "B"})
    # Il DAY esiste già con dentro un file video simulato.
    os.makedirs(dest_day)
    (dest_day / "video.mov").write_text("VIDEO")

    copyops.copy_into(str(src), str(dest_day / "DRP"))

    assert (dest_day / "video.mov").is_file()          # dailies intatti
    assert (dest_day / "DRP" / "a.txt").is_file()       # documenti aggiunti
    assert (dest_day / "DRP" / "sub" / "b.txt").is_file()
    # Nessun annidamento tipo DRP/DRP
    assert not (dest_day / "DRP" / "DRP").exists()


def test_verify_copy_ok(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    _make_tree(str(src), {"a.txt": "A", "sub/b.txt": "B"})
    copyops.copy_into(str(src), str(dest))
    result = copyops.verify_copy(str(src), str(dest))
    assert result.ok
    assert result.checked == 2


def test_verify_copy_detects_mismatch(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    _make_tree(str(src), {"a.txt": "A"})
    copyops.copy_into(str(src), str(dest))
    # Corrompe la destinazione.
    (dest / "a.txt").write_text("CORROTTO")
    result = copyops.verify_copy(str(src), str(dest))
    assert not result.ok
    assert "a.txt" in result.mismatched


def test_verify_copy_detects_missing(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    _make_tree(str(src), {"a.txt": "A", "b.txt": "B"})
    os.makedirs(dest)
    (dest / "a.txt").write_text("A")  # manca b.txt
    result = copyops.verify_copy(str(src), str(dest))
    assert not result.ok
    assert "b.txt" in result.missing


def test_write_mhl(tmp_path):
    src = tmp_path / "src"
    _make_tree(str(src), {"a.txt": "hello"})
    mhl = str(tmp_path / "out.mhl")
    copyops.write_mhl(str(src), mhl)
    content = open(mhl, encoding="utf-8").read()
    assert "<hashlist" in content
    assert "<file>a.txt</file>" in content
    assert "<sha1>" in content


def test_recreate_folder_empties(tmp_path):
    d = tmp_path / "src"
    _make_tree(str(d), {"a.txt": "A", "b.txt": "B"})
    copyops.recreate_folder(str(d))
    assert os.path.isdir(d)
    assert os.listdir(d) == []
