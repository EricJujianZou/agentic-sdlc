"""S-009: pin the CI gate so it cannot be silently removed or defanged.

The workflow runs the suite on every PR to main, outside the harness's
trust boundary - the agent-proof correctness gate. These checks assert it
lives in GitHub's directory (never the repo-root workflows/ that holds the
harness orchestrators) and still runs the real suite on pull_request.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_lives_in_github_dir():
    assert CI_WORKFLOW.exists(), "CI workflow must be .github/workflows/ci.yml"
    # never in the repo-root workflows/ dir, which holds harness orchestrators
    assert not (REPO_ROOT / "workflows" / "ci.yml").exists()


def test_ci_workflow_runs_suite_on_pr_to_main():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request" in text
    assert "branches: [main]" in text
    assert "uv sync" in text
    assert "uv run pytest" in text
