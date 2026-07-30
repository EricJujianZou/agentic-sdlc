"""T16 — backup / list-backups / restore round-trip."""

import pathlib
import re
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


def _backup_name_from_listing(data_dir):
    result = ok(run_cli(data_dir, "list-backups"))
    lines = [line.strip() for line in result.stdout.splitlines()
             if ".bak-" in line]
    assert lines, "list-backups should name the backup"
    return lines[-1]


def test_backup_creates_named_snapshot(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    result = ok(run_cli(tmp_path, "backup"))
    assert ".bak-" in result.stdout
    matches = [p.name for p in tmp_path.glob("state.json.bak-*")]
    assert matches, "backup should live next to the state file"
    for name in matches:
        assert ":" not in name


def test_list_backups(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    ok(run_cli(tmp_path, "list-backups"))  # none yet is not an error
    ok(run_cli(tmp_path, "backup"))
    result = ok(run_cli(tmp_path, "list-backups"))
    assert ".bak-" in result.stdout


def test_restore_round_trip(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    ok(run_cli(tmp_path, "backup"))
    name = _backup_name_from_listing(tmp_path)
    ok(run_cli(tmp_path, "receive", "AAA-1", "5"))
    assert load_store(tmp_path).get_item("AAA-1").qty == 10
    ok(run_cli(tmp_path, "restore", name))
    assert load_store(tmp_path).get_item("AAA-1").qty == 5


def test_restore_unknown_backup_rejected(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "5"))
    result = run_cli(tmp_path, "restore", "state.json.bak-nope")
    assert result.returncode == 1
    assert load_store(tmp_path).get_item("AAA-1").qty == 5


def test_backup_prints_a_restorable_name(tmp_path):
    ok(run_cli(tmp_path, "add-item", "AAA-1", "Thing", "--qty", "7"))
    result = ok(run_cli(tmp_path, "backup"))
    match = re.search(r"(\S+\.bak-\S+)", result.stdout)
    assert match is not None
    printed = pathlib.Path(match.group(1)).name
    listed = _backup_name_from_listing(tmp_path)
    assert pathlib.Path(listed).name == printed
