"""T35: undo reverses the most recent change."""

import pathlib
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


def _qty(tmp, sku):
    return _store(tmp).get_item(sku).qty


def _setup(tmp):
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "10", "--price", "4.2")


def test_undo_receive(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "receive", "WID-1", "5")
    assert _qty(tmp_path, "WID-1") == 15
    result = _cli(tmp_path, "undo")
    assert result.returncode == 0, result.stderr
    assert _qty(tmp_path, "WID-1") == 10


def test_undo_ship(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "ship", "WID-1", "3")
    assert _qty(tmp_path, "WID-1") == 7
    assert _cli(tmp_path, "undo").returncode == 0
    assert _qty(tmp_path, "WID-1") == 10


def test_undo_add_item(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "add-item", "TMP-1", "Temporary", "--qty", "1")
    assert _cli(tmp_path, "undo").returncode == 0
    store = _store(tmp_path)
    assert "TMP-1" not in store.items
    assert "WID-1" in store.items


def test_undo_place_order(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-07-01")
    assert len(_store(tmp_path).orders) == 1
    assert _cli(tmp_path, "undo").returncode == 0
    assert len(_store(tmp_path).orders) == 0


def test_undo_cancel_order(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-07-01")
    _cli(tmp_path, "cancel-order", "1")
    assert _store(tmp_path).get_order(1).status == "cancelled"
    assert _cli(tmp_path, "undo").returncode == 0
    assert _store(tmp_path).get_order(1).status == "pending"


def test_undo_set_price(tmp_path):
    _setup(tmp_path)
    result = _cli(tmp_path, "set-price", "WID-1", "2.5",
                  "--date", "2026-07-02")
    assert result.returncode == 0, result.stderr
    assert round(_store(tmp_path).get_item("WID-1").unit_price, 2) == 2.5
    assert _cli(tmp_path, "undo").returncode == 0
    assert round(_store(tmp_path).get_item("WID-1").unit_price, 2) == 4.2


def test_double_undo_steps_back_twice(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "receive", "WID-1", "5")
    _cli(tmp_path, "ship", "WID-1", "2")
    assert _qty(tmp_path, "WID-1") == 13
    assert _cli(tmp_path, "undo").returncode == 0
    assert _qty(tmp_path, "WID-1") == 15
    assert _cli(tmp_path, "undo").returncode == 0
    assert _qty(tmp_path, "WID-1") == 10


def test_undo_with_no_history_is_user_error(tmp_path):
    result = _cli(tmp_path, "undo")
    assert result.returncode == 1
