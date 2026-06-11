from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_index_exists():
    assert (REPO_ROOT / "dashboard" / "index.html").exists()


def test_dashboard_references_prd_json():
    html = (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert "prd.json" in html
