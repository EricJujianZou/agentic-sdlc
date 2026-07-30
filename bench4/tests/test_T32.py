"""T32: all stored dates normalized to ISO YYYY-MM-DD (schema v5)."""

import json
import pathlib
import re
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def test_legacy_unpadded_dates_normalize_on_load(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    store = _store(tmp_path)
    dates = {order.id: order.date for order in store.orders}
    assert dates[1] == "2026-01-05"
    assert dates[3] == "2026-02-03"
    assert all(ISO_RE.match(d) for d in dates.values())


def test_every_prior_schema_version_loads_normalized(tmp_path):
    names = [f"state_v{k}.json" for k in (1, 2, 3, 4)]
    present = [n for n in names if (FIXTURES / n).exists()]
    assert "state_v1.json" in present
    for name in present:
        sub = tmp_path / name.replace(".json", "")
        sub.mkdir()
        shutil.copy(FIXTURES / name, sub / "state.json")
        store = _store(sub)
        assert store.items, name
        for order in store.orders:
            assert ISO_RE.match(order.date), (name, order.date)
        store.save()
        again = _store(sub)
        for order in again.orders:
            assert ISO_RE.match(order.date), (name, order.date)


def test_normalized_dates_written_back_on_save(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    store = _store(tmp_path)
    store.save()
    # load-level: a fresh store sees only normalized dates
    again = _store(tmp_path)
    assert {o.id: o.date for o in again.orders}[1] == "2026-01-05"
    # file-level (migration task): saved file is versioned and ISO-dated
    state_file = tmp_path / "state.json"
    if state_file.exists():
        raw = json.loads(state_file.read_text(encoding="utf-8"))
        assert raw.get("version", 0) >= 5
        for order in raw.get("orders", []):
            assert ISO_RE.match(order["date"]), order["date"]


def test_cli_normalizes_unpadded_date_input(tmp_path):
    _cli(tmp_path, "add-item", "WID-9", "Thing", "--qty", "1")
    result = _cli(tmp_path, "place-order", "WID-9", "3", "--date", "2026-7-4")
    assert result.returncode == 0, result.stderr
    store = _store(tmp_path)
    assert [o.date for o in store.orders] == ["2026-07-04"]
    report = _cli(tmp_path, "report", "monthly", "2026-07")
    assert report.returncode == 0
    assert "2026-07-04" in report.stdout


def test_cli_rejects_impossible_dates(tmp_path):
    _cli(tmp_path, "add-item", "WID-9", "Thing", "--qty", "1")
    for bad in ("not-a-date", "2026-13-01", "2026-02-30"):
        result = _cli(tmp_path, "place-order", "WID-9", "1", "--date", bad)
        assert result.returncode == 1, (bad, result.returncode, result.stdout)
    store = _store(tmp_path)
    assert len(store.orders) == 0


def test_monthly_report_includes_legacy_unpadded_orders(tmp_path):
    shutil.copy(FIXTURES / "state_v1.json", tmp_path / "state.json")
    result = _cli(tmp_path, "report", "monthly", "2026-01")
    assert result.returncode == 0, result.stderr
    assert "2026-01-05" in result.stdout
    assert "2026-01-20" in result.stdout
    assert "2 orders" in result.stdout
