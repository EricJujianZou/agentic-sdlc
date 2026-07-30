"""Locked tests for T25 - per-category discount rules (CRUD)."""

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_cli(data_dir, *args):
    return subprocess.run(
        [sys.executable, "-m", "stockroom.cli", "--data", str(data_dir), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def _load(tmp):
    from stockroom.store import Store
    store = Store(str(tmp / "state.json"))
    store.load()
    return store


def test_set_and_list_discount_persists(tmp_path):
    r = run_cli(tmp_path, "set-discount", "widgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "list-discounts")
    assert r.returncode == 0, r.stderr
    assert "widgets" in r.stdout
    assert "10" in r.stdout


def test_set_discount_overwrites(tmp_path):
    r = run_cli(tmp_path, "set-discount", "widgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "set-discount", "widgets", "15")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "list-discounts")
    assert r.returncode == 0, r.stderr
    assert "15" in r.stdout
    assert "10" not in r.stdout


def test_remove_discount(tmp_path):
    r = run_cli(tmp_path, "set-discount", "widgets", "10")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "remove-discount", "widgets")
    assert r.returncode == 0, r.stderr
    r = run_cli(tmp_path, "list-discounts")
    assert r.returncode == 0, r.stderr
    assert "widgets" not in r.stdout


def test_remove_unknown_discount_is_user_error(tmp_path):
    r = run_cli(tmp_path, "remove-discount", "ghosts")
    assert r.returncode == 1


def test_out_of_range_percent_rejected(tmp_path):
    r = run_cli(tmp_path, "set-discount", "widgets", "150")
    assert r.returncode == 1
    store = _load(tmp_path)
    with pytest.raises(ValueError):
        store.set_discount("widgets", -5)


def test_get_discount_api(tmp_path):
    r = run_cli(tmp_path, "set-discount", "widgets", "12.5")
    assert r.returncode == 0, r.stderr
    store = _load(tmp_path)
    assert store.get_discount("widgets") == 12.5
    assert store.get_discount("nothing-here") == 0
