"""T14 — per-warehouse stock report variant."""

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


def _setup(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Alpha", "--qty", "3",
               "--price", "2.5"))
    ok(run_cli(tmp_path, "add-item", "BBB-2", "Beta", "--qty", "4",
               "--price", "1.5"))
    ok(run_cli(tmp_path, "receive", "AAA-1", "2", "--warehouse", "east"))


def test_api_single_warehouse_report(tmp_path):
    from stockroom import reports

    _setup(tmp_path)
    store = load_store(tmp_path)
    report = reports.stock_report(store, warehouse="east")
    skus = [row["sku"] for row in report["rows"]]
    assert skus == ["AAA-1"]
    assert report["rows"][0]["qty"] == 2
    assert round(report["rows"][0]["value"], 2) == 5.0
    assert round(report["total_value"], 2) == 5.0


def test_api_default_report_unchanged(tmp_path):
    from stockroom import reports

    _setup(tmp_path)
    store = load_store(tmp_path)
    report = reports.stock_report(store)
    by_sku = {row["sku"]: row for row in report["rows"]}
    assert by_sku["AAA-1"]["qty"] == 5
    assert by_sku["BBB-2"]["qty"] == 4
    assert round(report["total_value"], 2) == 18.5


def test_cli_warehouse_stock_report(tmp_path):
    _setup(tmp_path)
    result = ok(run_cli(tmp_path, "report", "stock", "--warehouse", "east"))
    assert "AAA-1" in result.stdout
    assert "BBB-2" not in result.stdout


def test_empty_warehouse_gives_empty_report(tmp_path):
    from stockroom import reports

    _setup(tmp_path)
    store = load_store(tmp_path)
    report = reports.stock_report(store, warehouse="west")
    assert report["rows"] == []
    assert round(report["total_value"], 2) == 0.0
