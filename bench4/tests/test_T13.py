"""T13 — transfer stock between warehouses; overdraw rejected atomically."""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
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


def test_api_transfer_moves_stock(tmp_path):
    from stockroom.store import Store

    store = Store(str(tmp_path / "state.json"))
    store.add_item("AAA-1", "Thing", qty=10)
    store.transfer("AAA-1", 4, "main", "east")
    item = store.get_item("AAA-1")
    assert item.qty_in("main") == 6
    assert item.qty_in("east") == 4
    assert item.qty == 10


def test_cli_transfer(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "10"))
    result = ok(run_cli(tmp_path, "transfer", "AAA-1", "4", "main", "east"))
    assert "AAA-1" in result.stdout
    store = load_store(tmp_path)
    item = store.get_item("AAA-1")
    assert item.qty_in("main") == 6
    assert item.qty_in("east") == 4
    assert item.qty == 10


def test_cli_overdraw_rejected_and_state_untouched(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "10"))
    result = run_cli(tmp_path, "transfer", "AAA-1", "99", "main", "east")
    assert result.returncode == 1
    assert "error" in result.stderr.lower()
    store = load_store(tmp_path)
    item = store.get_item("AAA-1")
    assert item.qty_in("main") == 10
    assert item.qty_in("east") == 0
    assert item.qty == 10


def test_transfer_unknown_sku_rejected(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    result = run_cli(tmp_path, "transfer", "ZZZ-9", "1", "main", "east")
    assert result.returncode == 1


def test_transfer_from_empty_warehouse_rejected(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    result = run_cli(tmp_path, "transfer", "AAA-1", "1", "west", "east")
    assert result.returncode == 1
    store = load_store(tmp_path)
    item = store.get_item("AAA-1")
    assert item.qty_in("main") == 5
    assert item.qty == 5
