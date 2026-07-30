"""T20 — turnover: units shipped per category per month."""

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
    ok(run_cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "50",
               "--price", "2.5", "--category", "widgets"))
    ok(run_cli(tmp_path, "add-item", "GAD-1", "Gadget", "--qty", "50",
               "--price", "1.5", "--category", "gadgets"))


def _turnover(data_dir):
    from stockroom import reports

    return reports.turnover(load_store(data_dir))


def test_turnover_by_category_and_month(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "WID-1", "3", "--date", "2026-03-05"))
    ok(run_cli(tmp_path, "ship", "WID-1", "2", "--date", "2026-04-01"))
    ok(run_cli(tmp_path, "ship", "GAD-1", "4", "--date", "2026-03-10"))
    turnover = _turnover(tmp_path)
    assert turnover["widgets"]["2026-03"] == 3
    assert turnover["widgets"]["2026-04"] == 2
    assert turnover["gadgets"]["2026-03"] == 4


def test_same_month_shipments_accumulate(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "WID-1", "3", "--date", "2026-03-05"))
    ok(run_cli(tmp_path, "ship", "WID-1", "4", "--date", "2026-03-20"))
    turnover = _turnover(tmp_path)
    assert turnover["widgets"]["2026-03"] == 7


def test_transfers_are_not_shipments(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "WID-1", "3", "--date", "2026-03-05"))
    ok(run_cli(tmp_path, "transfer", "WID-1", "5", "main", "east"))
    turnover = _turnover(tmp_path)
    assert sum(turnover["widgets"].values()) == 3


def test_receiving_does_not_count(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "GAD-1", "4", "--date", "2026-03-10"))
    ok(run_cli(tmp_path, "receive", "GAD-1", "25"))
    turnover = _turnover(tmp_path)
    assert sum(turnover["gadgets"].values()) == 4


def test_cli_report_turnover(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "WID-1", "7", "--date", "2026-03-05"))
    result = ok(run_cli(tmp_path, "report", "turnover"))
    assert "widgets" in result.stdout
    assert "2026-03" in result.stdout
    assert "7" in result.stdout


def test_ship_without_date_still_recorded(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "ship", "WID-1", "6"))
    turnover = _turnover(tmp_path)
    assert sum(turnover["widgets"].values()) == 6
