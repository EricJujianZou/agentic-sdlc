"""T11 — state file schema versioning (v2), legacy v1 files keep loading."""

import json
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir)]
        + [str(a) for a in args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def load_store(data_dir):
    from stockroom.store import Store

    store = Store(str(pathlib.Path(data_dir) / "state.json"))
    store.load()
    return store


def read_state(data_dir):
    path = pathlib.Path(data_dir) / "state.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_new_store_saves_with_version(tmp_path):
    ok(run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3",
               "--price", "1.25"))
    data = read_state(tmp_path)
    assert isinstance(data, dict)
    assert "version" in data, "saved state file must declare its version"
    assert isinstance(data["version"], int)
    assert data["version"] >= 2


def test_legacy_unversioned_file_still_loads(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    result = ok(run_cli(tmp_path, "report", "stock"))
    assert "WID-1" in result.stdout
    assert "SCR-2" in result.stdout
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 3
    assert store.get_supplier("globex").name == "Globex Industrial"
    assert len(store.orders) == 5


def test_legacy_file_upgraded_on_next_save(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    ok(run_cli(tmp_path, "receive", "WID-1", "2"))
    data = read_state(tmp_path)
    assert "version" in data
    assert isinstance(data["version"], int)
    assert data["version"] >= 2
    store = load_store(tmp_path)
    assert store.get_item("WID-1").qty == 5


def test_load_save_roundtrip_preserves_everything(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    store = load_store(tmp_path)
    store.save()
    data = read_state(tmp_path)
    assert "version" in data
    again = load_store(tmp_path)
    assert len(again.items) == 7
    assert len(again.suppliers) == 2
    assert len(again.orders) == 5
    assert again.get_item("GAD-2").qty == 7
    assert round(again.get_item("GAD-2").unit_price, 2) == 1.15
    assert again.get_supplier("acme").email == "orders@acme.example"
    statuses = sorted(order.status for order in again.orders)
    assert statuses == ["cancelled", "pending", "pending", "received",
                       "received"]


def test_versioned_v2_file_loads(tmp_path):
    shutil.copy(FIXTURES / "state_v2.json", tmp_path / "state.json")
    store = load_store(tmp_path)
    assert len(store.items) == 3
    assert store.get_item("WID-1").qty == 4
    assert store.get_item("SCR-1").name == "Screws, box of 100"
    assert store.get_supplier("acme").name == "Acme Supply Co"
    assert len(store.orders) == 3
    result = ok(run_cli(tmp_path, "report", "stock"))
    assert "SCR-1" in result.stdout
