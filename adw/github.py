"""GitHub REST API helpers: token retrieval, issue/PR/comment operations.

All network I/O is stdlib urllib only (zero new dependencies).
Credentials are read from the local git credential store via `git credential fill`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from adw import paths

API_BASE = "https://api.github.com"

ENGINE_REPO_ENV = "ADW_ENGINE_REPO"


class GitHubError(RuntimeError):
    """Raised for any GitHub API or credential failure."""


def get_token(host: str = "github.com") -> str:
    """Retrieve stored OAuth token via `git credential fill`."""
    inp = f"protocol=https\nhost={host}\n\n"
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input=inp,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitHubError("git not found in PATH") from exc
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise GitHubError(
        f"no stored {host} credential; run `git credential fill` or push once to cache the token"
    )


def repo_slug(repo_root: Path | str | None = None) -> tuple[str, str]:
    """Return (owner, repo) by parsing `git remote get-url origin` of the
    target repo (adw/paths.py), so a cross-repo run reads the target's remote."""
    if repo_root is None:
        repo_root = paths.target_root()
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GitHubError("could not read git remote origin") from exc
    url = proc.stdout.strip()
    # SSH: git@github.com:owner/repo.git  or  HTTPS: https://github.com/owner/repo.git
    m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not m:
        raise GitHubError(f"cannot parse owner/repo from remote URL: {url!r}")
    return m.group(1), m.group(2)


def engine_repo_slug() -> tuple[str, str]:
    """Return (owner, repo) for the *engine* repo (where upstream system-repair
    reports get filed): `ADW_ENGINE_REPO` (owner/repo) if set, else the engine
    checkout's own git remote (self-hosting: same as `repo_slug()`)."""
    env = os.environ.get(ENGINE_REPO_ENV)
    if env:
        parts = env.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise GitHubError(f"{ENGINE_REPO_ENV} must be 'owner/repo', got {env!r}")
        return parts[0], parts[1]
    return repo_slug(paths.engine_root())


def api_request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Perform a single GitHub REST API call; return parsed JSON body."""
    url = API_BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "adw",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise GitHubError(f"HTTP {exc.code} from {method} {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"offline: cannot reach api.github.com: {exc.reason}") from exc


def list_account_repos(token: str, owner: str) -> list[tuple[str, str, str]]:
    """Page through the account's own (non-fork-irrelevant) repos and return
    `(owner, name, clone_url)` for every active one owned by `owner`.

    Filters out archived/disabled repos (dead weight for a sweep) and any
    result whose `owner.login` doesn't match `owner` (a token can also see
    org/collaborator repos we don't want auto-clone-and-worked here). Pages
    until a response shorter than `per_page` signals the last page."""
    repos: list[tuple[str, str, str]] = []
    page = 1
    per_page = 100
    while True:
        batch = api_request(
            "GET", f"/user/repos?per_page={per_page}&affiliation=owner&page={page}", token
        )
        if not batch:
            break
        for repo in batch:
            if (
                repo.get("owner", {}).get("login") == owner
                and not repo.get("archived")
                and not repo.get("disabled")
            ):
                repos.append((owner, repo["name"], repo["clone_url"]))
        if len(batch) < per_page:
            break
        page += 1
    return repos


def list_adw_issues(owner: str, repo: str, token: str) -> list[dict]:
    """Return open Issues labeled 'adw', excluding pull requests."""
    path = f"/repos/{owner}/{repo}/issues?state=open&labels=adw&per_page=100"
    issues = api_request("GET", path, token)
    return [i for i in issues if "pull_request" not in i]


def create_issue(
    owner: str, repo: str, token: str, title: str, body: str, labels: list[str] | None = None
) -> dict:
    """Open a new issue. `labels` is included only when non-empty, so a plain
    issue payload matches what a human filing one by hand would send."""
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = list(labels)
    return api_request("POST", f"/repos/{owner}/{repo}/issues", token, payload)


def list_open_issues(owner: str, repo: str, token: str, label: str | None = None) -> list[dict]:
    """Return open Issues, optionally filtered to one label, excluding pull requests."""
    path = f"/repos/{owner}/{repo}/issues?state=open&per_page=100"
    if label:
        path += f"&labels={urllib.parse.quote(label, safe='')}"
    issues = api_request("GET", path, token)
    return [i for i in issues if "pull_request" not in i]


def open_or_update_pr(
    owner: str,
    repo: str,
    token: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> dict:
    """Open a PR for head→base; on 422 (already exists) PATCH the existing one."""
    try:
        return api_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            token,
            {"title": title, "head": head, "base": base, "body": body},
        )
    except GitHubError as exc:
        if "HTTP 422" not in str(exc):
            raise
    # PR already exists — find and update it
    existing = api_request(
        "GET",
        f"/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head}",
        token,
    )
    if not existing:
        raise GitHubError(f"got 422 creating PR but no open PR found for head {owner}:{head}")
    pr = existing[0]
    return api_request(
        "PATCH",
        f"/repos/{owner}/{repo}/pulls/{pr['number']}",
        token,
        {"title": title, "body": body},
    )


def in_flight_ref(
    owner: str, repo: str, ticket_id: str, token: str, repo_root: Path | str | None = None
) -> str | None:
    """Human-readable reason (`"PR #6"` / `"branch adw/GH-2"`) when `ticket_id`'s
    work is already in flight (open PR or existing origin branch), else None.

    Fails open on any GitHub/git error — a failed check must never block a
    sweep from picking a ticket it would otherwise have picked."""
    head = f"adw/{ticket_id}"
    try:
        prs = api_request(
            "GET", f"/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head}", token
        )
        if prs:
            return f"PR #{prs[0]['number']}"
    except GitHubError:
        pass
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", head],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True, text=True, check=True,
        )
        if proc.stdout.strip():
            return f"branch {head}"
    except (subprocess.CalledProcessError, OSError):
        pass
    return None


def comment_on_issue(owner: str, repo: str, token: str, number: int, body: str) -> dict:
    """Post a comment on an issue."""
    return api_request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{number}/comments",
        token,
        {"body": body},
    )


def add_labels(owner: str, repo: str, token: str, number: int, labels: list[str]) -> Any:
    """Add labels to an issue. GitHub creates any label that doesn't exist yet,
    so a fresh repo needs no label setup. Idempotent — re-adding is a no-op."""
    return api_request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{number}/labels",
        token,
        {"labels": list(labels)},
    )


def remove_label(owner: str, repo: str, token: str, number: int, label: str) -> None:
    """Remove one label from an issue. A 404 (the label isn't on the issue) is
    not an error — relabeling must be safe to call from any prior state."""
    quoted = urllib.parse.quote(label, safe="")
    try:
        api_request(
            "DELETE", f"/repos/{owner}/{repo}/issues/{number}/labels/{quoted}", token
        )
    except GitHubError as exc:
        if "HTTP 404" not in str(exc):
            raise


def source_issue_number(story_id: str) -> int | None:
    """Return the GitHub issue number for a GH-<n> story id, else None."""
    if story_id.startswith("GH-") and story_id[3:].isdigit():
        return int(story_id[3:])
    return None


def pr_body(story: Any, outcome: str, pr_description: str | None = None) -> str:
    if pr_description:
        body = f"{pr_description}\n"
    else:
        reason = getattr(story, "description", "")
        body = (
            f"## Outcome: {outcome}\n\n"
            f"**Ticket:** {story.id} — {story.title}\n\n"
            f"{reason}\n"
        )
    # On a done ticket, link the source issue so merging this PR closes it —
    # that is the human merge gate doubling as the issue's close event, which
    # lets the harness leave the issue OPEN (only relabeled) until work lands.
    number = source_issue_number(story.id)
    if number is not None and outcome == "done":
        body += f"\nCloses #{number}\n"
    return body


def outcome_comment_body(
    story: Any, outcome: str, reason: str = "", test_evidence: str | None = None
) -> str:
    lines = [f"**{outcome.upper()}** — {story.id}: {story.title}"]
    if test_evidence:
        lines.append(f"\nLocal tests: {test_evidence} — cross-check against CI.")
    if reason:
        lines.append(f"\nReason: {reason}")
    return "\n".join(lines)
