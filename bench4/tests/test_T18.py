"""T18 — supplier catalogues; place-order infers the supplier."""

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


def _setup(tmp_path, item_supplier=None):
    ok(run_cli(tmp_path, "add-supplier", "acme", "Acme Supply",
               "orders@acme.example"))
    ok(run_cli(tmp_path, "add-supplier", "globex", "Globex Industrial",
               "purchasing@globex.example"))
    args = ["add-item", "WID-1", "Widget", "--qty", "1"]
    if item_supplier:
        args += ["--supplier", item_supplier]
    ok(run_cli(tmp_path, *args))


def test_unique_catalogue_supplier_is_inferred(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "catalog-add", "acme", "WID-1"))
    ok(run_cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-04-01"))
    store = load_store(tmp_path)
    assert store.get_order(1).supplier_id == "acme"


def test_ambiguous_catalogue_requires_explicit_supplier(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "catalog-add", "acme", "WID-1"))
    ok(run_cli(tmp_path, "catalog-add", "globex", "WID-1"))
    result = run_cli(tmp_path, "place-order", "WID-1", "5", "--date",
                     "2026-04-01")
    assert result.returncode == 1
    assert len(load_store(tmp_path).orders) == 0
    ok(run_cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-04-01",
               "--supplier", "globex"))
    store = load_store(tmp_path)
    assert len(store.orders) == 1
    assert store.orders[0].supplier_id == "globex"


def test_no_catalogue_falls_back_to_item_supplier(tmp_path):
    _setup(tmp_path, item_supplier="acme")
    ok(run_cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-04-01"))
    store = load_store(tmp_path)
    assert store.get_order(1).supplier_id == "acme"


def test_unknown_supplier_flag_rejected(tmp_path):
    _setup(tmp_path)
    result = run_cli(tmp_path, "place-order", "WID-1", "5", "--date",
                     "2026-04-01", "--supplier", "nosuch")
    assert result.returncode == 1
    assert len(load_store(tmp_path).orders) == 0


def test_catalogue_persists_and_lists(tmp_path):
    _setup(tmp_path)
    ok(run_cli(tmp_path, "catalog-add", "acme", "WID-1"))
    result = ok(run_cli(tmp_path, "catalog-list", "acme"))
    assert "WID-1" in result.stdout
    store = load_store(tmp_path)
    assert store.suppliers_for("WID-1") == ["acme"]
