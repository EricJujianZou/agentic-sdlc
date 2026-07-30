"""T37: shipments aggregated per ISO week."""

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _cli(tmp, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(tmp), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _store(tmp):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def _weekly(tmp):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from stockroom import reports
    return reports.weekly_shipments(_store(tmp))


def _build(tmp):
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "100", "--price", "1.0")
    _cli(tmp, "add-item", "GAD-1", "Gadget", "--qty", "100", "--price", "1.0")
    _cli(tmp, "ship", "WID-1", "3", "--date", "2026-07-06")   # W28 (Mon)
    _cli(tmp, "ship", "WID-1", "4", "--date", "2026-07-12")   # W28 (Sun)
    _cli(tmp, "ship", "GAD-1", "5", "--date", "2026-07-08")   # W28
    _cli(tmp, "ship", "WID-1", "2", "--date", "2026-07-13")   # W29 (Mon)
    _cli(tmp, "ship", "GAD-1", "1", "--date", "2026-06-30")   # W27


def test_ship_accepts_date_flag(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "10",
         "--price", "1.0")
    result = _cli(tmp_path, "ship", "WID-1", "1", "--date", "2026-07-06")
    assert result.returncode == 0, result.stderr


def test_units_grouped_by_iso_week(tmp_path):
    _build(tmp_path)
    weekly = _weekly(tmp_path)
    assert weekly == {"2026-W27": 1, "2026-W28": 12, "2026-W29": 2}


def test_single_digit_weeks_zero_padded(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "10",
         "--price", "1.0")
    _cli(tmp_path, "ship", "WID-1", "2", "--date", "2026-01-05")  # ISO W02
    weekly = _weekly(tmp_path)
    assert weekly == {"2026-W02": 2}
    assert all(re.match(r"^\d{4}-W\d{2}$", label) for label in weekly)


def test_cli_report_weekly(tmp_path):
    _build(tmp_path)
    result = _cli(tmp_path, "report", "weekly")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "2026-W28" in out
    assert "12" in out
    # oldest week first
    assert out.index("2026-W27") < out.index("2026-W28") < out.index("2026-W29")
