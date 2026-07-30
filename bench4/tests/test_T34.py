"""T34: event log — every mutating operation appends one entry."""

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


def _events(tmp):
    events = getattr(_store(tmp), "events", None)
    assert isinstance(events, list), "store.events should be a list"
    return events


def _setup(tmp):
    _cli(tmp, "add-supplier", "acme", "Acme Supply", "orders@acme.example")
    _cli(tmp, "add-item", "WID-1", "Widget", "--qty", "10", "--price", "2.0")


def test_add_commands_log_events_with_actor(tmp_path):
    _cli(tmp_path, "add-supplier", "acme", "Acme", "a@x.example",
         "--actor", "alice")
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "5",
         "--price", "1.0", "--actor", "alice")
    events = _events(tmp_path)
    assert len(events) == 2
    ops = [event.get("op") for event in events]
    assert "add-supplier" in ops
    assert "add-item" in ops
    for event in events:
        assert event.get("actor") == "alice"


def test_receive_and_ship_log_ordered_events_with_args(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "receive", "WID-1", "4", "--actor", "bob")
    _cli(tmp_path, "ship", "WID-1", "2", "--actor", "bob")
    events = _events(tmp_path)
    assert [event.get("op") for event in events[-2:]] == ["receive", "ship"]
    received = events[-2]
    assert received.get("actor") == "bob"
    args = received.get("args") or {}
    assert args.get("sku") == "WID-1"
    assert args.get("qty") in (4, "4")


def test_order_lifecycle_logs_events(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "place-order", "WID-1", "5", "--date", "2026-07-01",
         "--actor", "alice")
    _cli(tmp_path, "receive-order", "1", "--actor", "alice")
    _cli(tmp_path, "place-order", "WID-1", "2", "--date", "2026-07-02",
         "--actor", "alice")
    _cli(tmp_path, "cancel-order", "2", "--actor", "alice")
    ops = [event.get("op") for event in _events(tmp_path)]
    for op in ("place-order", "receive-order", "cancel-order"):
        assert op in ops, op


def test_actor_defaults_to_empty(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "receive", "WID-1", "1")
    last = _events(tmp_path)[-1]
    assert last.get("op") == "receive"
    assert last.get("actor") in (None, "")


def test_reports_do_not_log(tmp_path):
    _setup(tmp_path)
    _cli(tmp_path, "receive", "WID-1", "2")
    count = len(_events(tmp_path))
    _cli(tmp_path, "report", "stock")
    _cli(tmp_path, "report", "low")
    assert len(_events(tmp_path)) == count


def test_library_mutations_log_too(tmp_path):
    _setup(tmp_path)
    store = _store(tmp_path)
    store.receive("WID-1", 3)
    store.save()
    last = _events(tmp_path)[-1]
    assert last.get("op") == "receive"
    assert last.get("actor") in (None, "")


def test_one_event_per_change_in_order(tmp_path):
    _cli(tmp_path, "add-supplier", "acme", "Acme", "a@x.example")
    _cli(tmp_path, "add-item", "WID-1", "Widget", "--qty", "10",
         "--price", "1.0")
    _cli(tmp_path, "receive", "WID-1", "5")
    _cli(tmp_path, "ship", "WID-1", "2")
    _cli(tmp_path, "place-order", "WID-1", "3", "--date", "2026-07-01")
    events = _events(tmp_path)
    assert [event.get("op") for event in events] == [
        "add-supplier", "add-item", "receive", "ship", "place-order",
    ]
