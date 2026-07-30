"""T39: export the event log to CSV with --op / --since filters."""

import csv
import json
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

FIXTURE_OPS = ["add-item", "receive", "ship", "place-order", "receive-order"]


def _cli(tmp, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(tmp), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _fixture_store(tmp):
    shutil.copy(FIXTURES / "state_v5.json", tmp / "state.json")


def _export(tmp, name, *extra):
    out = tmp / name
    result = _cli(tmp, "export-events", str(out), *extra)
    return result, out


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def test_export_all_events(tmp_path):
    _fixture_store(tmp_path)
    result, out = _export(tmp_path, "all.csv")
    assert result.returncode == 0, result.stderr
    header, rows = _read(out)
    assert header == ["ts", "op", "actor", "args"]
    assert [row[1] for row in rows] == FIXTURE_OPS
    assert "5" in result.stdout
    # the "ship" event has no actor: empty cell
    assert rows[2][2] == ""


def test_filter_by_op_is_exact(tmp_path):
    _fixture_store(tmp_path)
    result, out = _export(tmp_path, "receive.csv", "--op", "receive")
    assert result.returncode == 0, result.stderr
    _, rows = _read(out)
    # "receive" must not match "receive-order"
    assert [row[1] for row in rows] == ["receive"]
    args = json.loads(rows[0][3])
    assert args["sku"] == "WID-1"
    assert args["qty"] == 6


def test_filter_since_is_inclusive(tmp_path):
    _fixture_store(tmp_path)
    result, out = _export(tmp_path, "since3.csv", "--since", "2026-07-03")
    assert result.returncode == 0, result.stderr
    _, rows = _read(out)
    assert [row[1] for row in rows] == ["ship", "place-order", "receive-order"]
    result, out = _export(tmp_path, "since1.csv", "--since", "2026-07-01")
    assert result.returncode == 0
    _, rows = _read(out)
    assert len(rows) == 5


def test_filters_combine(tmp_path):
    _fixture_store(tmp_path)
    result, out = _export(tmp_path, "combo1.csv",
                          "--op", "place-order", "--since", "2026-07-04")
    assert result.returncode == 0, result.stderr
    _, rows = _read(out)
    assert [row[1] for row in rows] == ["place-order"]
    result, out = _export(tmp_path, "combo0.csv",
                          "--op", "ship", "--since", "2026-07-04")
    assert result.returncode == 0
    header, rows = _read(out)
    assert header == ["ts", "op", "actor", "args"]
    assert rows == []


def test_export_of_live_events(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3",
         "--price", "1.0", "--actor", "carol")
    _cli(tmp_path, "receive", "WID-1", "2", "--actor", "carol")
    result, out = _export(tmp_path, "live.csv")
    assert result.returncode == 0, result.stderr
    _, rows = _read(out)
    assert [row[1] for row in rows] == ["add-item", "receive"]
    assert all(row[2] == "carol" for row in rows)
    receive_args = json.loads(rows[1][3])
    assert receive_args.get("sku") == "WID-1"
