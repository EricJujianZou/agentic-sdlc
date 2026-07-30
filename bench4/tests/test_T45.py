"""Locked tests for T45 - the fsck consistency check."""
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def snapshot(data_dir):
    data_dir = pathlib.Path(data_dir)
    return {
        str(p.relative_to(data_dir)): p.read_bytes()
        for p in sorted(data_dir.rglob("*"))
        if p.is_file()
    }


def item_dict(sku, qty):
    return {"sku": sku, "name": f"Item {sku}", "qty": qty,
            "unit_price": 1.0, "supplier_id": None}


def write_state(data_dir, items, orders):
    """Write a legacy single-file state (always loadable) with given rows."""
    raw = {
        "items": {sku: item_dict(sku, qty) for sku, qty in items.items()},
        "suppliers": {},
        "orders": orders,
    }
    (pathlib.Path(data_dir) / "state.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8")


def order_dict(order_id, sku, status="pending"):
    return {"id": order_id, "sku": sku, "qty": 2,
            "date": "2026-01-05", "status": status}


def test_clean_state_passes(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for args in [
        ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
        ("add-item", "WID-1", "Widget", "--qty", "5", "--price", "1.00",
         "--supplier", "ACME"),
        ("place-order", "WID-1", "3", "--date", "2026-01-05"),
        ("receive-order", "1"),
    ]:
        r = run_cli(data, *args)
        assert r.returncode == 0, (args, r.stderr)
    r = run_cli(data, "fsck")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "ok" in r.stdout


def test_orphan_order_is_reported(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    write_state(data, {"WID-1": 3}, [
        order_dict(1, "GHOST-9"),
        order_dict(2, "WID-1"),
    ])
    r = run_cli(data, "fsck")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "GHOST-9" in r.stdout
    assert r.stdout.count("problem:") == 1


def test_negative_quantity_is_reported(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    write_state(data, {"WID-1": -3}, [])
    r = run_cli(data, "fsck")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "WID-1" in r.stdout
    assert "negative" in r.stdout.lower()
    assert r.stdout.count("problem:") == 1


def test_fsck_reports_everything_and_never_writes(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    write_state(data, {"WID-1": -3, "GAD-1": 4}, [
        order_dict(1, "GHOST-9"),
    ])
    before = snapshot(data)
    r = run_cli(data, "fsck")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert r.stdout.count("problem:") == 2
    assert "GHOST-9" in r.stdout
    assert "WID-1" in r.stdout
    assert snapshot(data) == before, "fsck modified the data directory"
