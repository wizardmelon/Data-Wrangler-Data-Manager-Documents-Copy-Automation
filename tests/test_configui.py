import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import yaml

from dm_backup import configui
from dm_backup.config import ConfigError, ProjectConfig


def _base(tmp_path):
    d = configui.merge_defaults({})
    d["project"]["film"] = "Film"
    d["paths"]["project_root"] = str(tmp_path)
    return d


def test_merge_defaults_keeps_unknown_keys():
    d = configui.merge_defaults({"project": {"film": "X"}, "custom": {"a": 1}})
    assert d["project"]["film"] == "X" and d["project"]["dit"] == ""
    assert d["custom"] == {"a": 1}


def test_save_roundtrip_and_backup(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("project:\n  film: Old\npaths:\n  project_root: /x\n")
    data = _base(tmp_path)
    data["still"]["mode"] = "drx"
    data["disks"]["fixed_disks"] = ["A", "B"]
    data["extra_unknown"] = {"k": "v"}
    res = configui.save_config(str(path), data)
    assert os.path.isfile(res["backup"])
    assert "film: Old" in open(res["backup"]).read()
    cfg = ProjectConfig.load(str(path))
    assert cfg.film == "Film" and cfg.still_mode == "drx" and cfg.fixed_disks == ["A", "B"]
    assert yaml.safe_load(open(path))["extra_unknown"] == {"k": "v"}


def test_invalid_config_writes_nothing(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("keep: me\n")
    data = _base(tmp_path)
    data["project"]["film"] = ""
    with pytest.raises(ConfigError):
        configui.save_config(str(path), data)
    data = _base(tmp_path)
    data["still_rename"]["fields"] = ["nonsense"]
    with pytest.raises(ConfigError):
        configui.save_config(str(path), data)
    data = _base(tmp_path)
    data["still"]["mode"] = "boh"
    with pytest.raises(ConfigError):
        configui.save_config(str(path), data)
    assert path.read_text() == "keep: me\n"
    assert not (tmp_path / ".backups").exists()


def test_server_requires_token(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("project:\n  film: F\npaths:\n  project_root: /x\n")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), configui.make_handler(str(path), "tok", lambda: None))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with pytest.raises(Exception):
            urllib.request.urlopen(base + "/api/config")  # 403 senza token
        req = urllib.request.Request(base + "/api/config", headers={"X-Token": "tok"})
        assert json.load(urllib.request.urlopen(req))["config"]["project"]["film"] == "F"
        assert b"tok" in urllib.request.urlopen(base + "/").read()
    finally:
        srv.shutdown()
        srv.server_close()


def test_new_film_flow_save_then_init(tmp_path):
    path = tmp_path / "config.yaml"
    data = configui.load_raw(str(path))  # file assente -> default di film nuovo
    assert data["structure"]["files_folders"] and data["project_folders"]
    data["project"]["film"] = "Nuovo"
    data["paths"]["project_root"] = str(tmp_path / "FILM")
    configui.save_config(str(path), data)
    out = configui.create_structure(str(path))
    assert os.path.isdir(tmp_path / "FILM" / "TODAY_FILES" / "05_STILL")
    assert os.path.isfile(tmp_path / "FILM" / "RESOLVE_still_pattern.txt")
    cfg = ProjectConfig.load(str(path))
    assert cfg.today_files == str(tmp_path / "FILM" / "TODAY_FILES")
    assert out["folders"] == 5
