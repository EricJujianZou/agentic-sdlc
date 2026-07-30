"""Locked tests for T49 - single-file archive export / import."""
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

REPORT_COMMANDS = [
    ("report", "stock"),
    ("report", "history", "WID-1"),
    ("report", "monthly", "2026-01"),
    ("report", "summary"),
]


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


def build(data_dir):
    for args in [
        ("add-supplier", "ACME", "Acme Supply", "orders@acme.example"),
        ("add-item", "WID-1", "Widget", "--qty", "5", "--price", "2.50",
         "--category", "tools", "--supplier", "ACME"),
        ("add-item", "GAD-1", "Gadget", "--qty", "3", "--price", "0.10",
         "--category", "parts", "--supplier", "ACME"),
        ("place-order", "WID-1", "4", "--date", "2026-01-05"),
        ("receive-order", "1"),
        ("ship", "WID-1", "2"),
        ("place-order", "GAD-1", "2", "--date", "2026-02-03"),
    ]:
        r = run_cli(data_dir, *args)
        assert r.returncode == 0, (args, r.stderr)


def test_archive_roundtrip_reproduces_every_report(tmp_path):
    a = tmp_path / "A"
    a.mkdir()
    build(a)
    archive = tmp_path / "arch.json"
    r = run_cli(a, "export-archive", str(archive))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert archive.exists()
    parsed = json.loads(archive.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)

    b = tmp_path / "B"
    b.mkdir()
    r = run_cli(b, "import-archive", str(archive))
    assert r.returncode == 0, (r.stdout, r.stderr)

    for cmd in REPORT_COMMANDS:
        ra = run_cli(a, *cmd)
        rb = run_cli(b, *cmd)
        assert ra.returncode == 0, (cmd, ra.stderr)
        assert rb.returncode == 0, (cmd, rb.stderr)
        assert ra.stdout == rb.stdout, f"{cmd} differs after archive roundtrip"


def test_import_refuses_nonempty_directory(tmp_path):
    a = tmp_path / "A"
    a.mkdir()
    build(a)
    archive = tmp_path / "arch.json"
    assert run_cli(a, "export-archive", str(archive)).returncode == 0
    before = snapshot(a)
    r = run_cli(a, "import-archive", str(archive))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert snapshot(a) == before, "refused import still changed the data dir"
