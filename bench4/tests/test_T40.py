"""T40: events move to a sidecar <state>.events.json file (schema v6)."""

import json
import pathlib
import re
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

FIXTURE_OPS = ["add-item", "receive", "ship", "place-order", "receive-order"]


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


def _events(tmp):
    events = getattr(_store(tmp), "events", None)
    assert isinstance(events, list), "store.events should be a list"
    return events


def test_v6_state_and_sidecar_load_together(tmp_path):
    shutil.copy(FIXTURES / "state_v6.json", tmp_path / "state.json")
    shutil.copy(FIXTURES / "state_v6.events.json",
                tmp_path / "state.events.json")
    store = _store(tmp_path)
    assert "WID-1" in store.items
    assert [event.get("op") for event in store.events] == FIXTURE_OPS


def test_v5_embedded_events_still_load(tmp_path):
    shutil.copy(FIXTURES / "state_v5.json", tmp_path / "state.json")
    assert [event.get("op") for event in _events(tmp_path)] == FIXTURE_OPS


def test_save_moves_embedded_events_to_sidecar(tmp_path):
    shutil.copy(FIXTURES / "state_v5.json", tmp_path / "state.json")
    store = _store(tmp_path)
    store.save()
    sidecar = tmp_path / "state.events.json"
    assert sidecar.exists()
    # events survive a fresh load
    assert [event.get("op") for event in _events(tmp_path)] == FIXTURE_OPS
    # and the main file no longer embeds them
    state_file = tmp_path / "state.json"
    if state_file.exists():
        raw = json.loads(state_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            assert not raw.get("events")


def test_missing_sidecar_means_empty_log(tmp_path):
    shutil.copy(FIXTURES / "state_v6.json", tmp_path / "state.json")
    store = _store(tmp_path)
    assert "WID-1" in store.items
    assert list(getattr(store, "events", [])) == []


def test_cli_mutations_write_sidecar(tmp_path):
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "3",
         "--price", "1.0")
    _cli(tmp_path, "receive", "WID-1", "2")
    assert (tmp_path / "state.events.json").exists()
    assert [event.get("op") for event in _events(tmp_path)] == [
        "add-item", "receive",
    ]


def test_all_prior_schema_versions_still_load(tmp_path):
    names = [f"state_v{k}.json" for k in (1, 2, 3, 4, 5)]
    present = [n for n in names if (FIXTURES / n).exists()]
    assert "state_v1.json" in present
    assert "state_v5.json" in present
    for name in present:
        sub = tmp_path / name.replace(".json", "")
        sub.mkdir()
        shutil.copy(FIXTURES / name, sub / "state.json")
        store = _store(sub)
        assert store.items, name
        for order in store.orders:
            assert ISO_RE.match(order.date), (name, order.date)
