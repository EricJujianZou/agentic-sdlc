"""Multi-repo sweep driver (GH-56): discover every account repo with an open
`adw` issue, auto-clone any missing one, sync each, then work tickets
round-robin one-per-repo until every backlog empties or a quota halt fires.

Usage: uv run python workflows/poll_all.py [--max-iterations N]

Reuses `sync_issues.pull_and_sync`, `workflow_runner.run_one_story`/
`reap_stale_in_progress`, `tickets.pick_next_story`, and the per-repo circuit
breaker (`adw/safety.py`) UNCHANGED. The one new mechanism is an account-wide
cooldown store, kept entirely OUTSIDE every repo: a `quotad` outcome in any
repo copies that repo's already-parsed `state.cooldown_until` into the global
store and halts the whole sweep; the next scheduled firing re-checks the
global store before doing any work. `safety.py`/`CircuitBreaker` are never
touched — this driver only reads what they already persist.

Self-hosting: when this engine checkout is itself one of the discovered
targets, `ensure_clone` maps it straight to `paths.engine_root()` with no
clone — auto-discover means ANY repo ever labeled `adw` joins the sweep,
including the engine's own.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent  # engine root, for imports
sys.path.insert(0, str(REPO_ROOT))

from adw import paths
from adw.github import (
    GitHubError,
    engine_repo_slug,
    get_token,
    in_flight_ref,
    list_account_repos,
    list_adw_issues,
    repo_slug,
)
from adw.locks import DEFAULT_STALE_SECONDS, LockHeld, single_flight
from adw.state import load_state
from adw.tickets import load_prd, pick_next_story
from adw.workflow_runner import STAGE_ORDER_BY_TYPE, reap_stale_in_progress, run_one_story
from workflows.sync_issues import pull_and_sync


@dataclass(frozen=True)
class RepoDescriptor:
    owner: str
    name: str
    clone_url: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


def _resolve_engine_slug() -> tuple[str, str] | None:
    try:
        return repo_slug(paths.engine_root())
    except GitHubError:
        return None


# Resolved once at import time (a single real git call against the engine's
# OWN checkout — not the target repo, never mocked away by a test's per-test
# fixtures) so `ensure_clone`'s self-host short-circuit never depends on
# whatever happens to be patching `subprocess` at call time.
_ENGINE_SLUG = _resolve_engine_slug()


# --- out-of-repo paths (mirrors workflows/poll_once.py's idiom) -------------


def managed_repos_dir() -> Path:
    """Where auto-cloned repos live: `ADW_REPOS_DIR`, else
    `%LOCALAPPDATA%/adw/repos`, else `~/.adw/repos` — always outside any repo."""
    env = os.environ.get("ADW_REPOS_DIR")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "adw" / "repos"
    return Path.home() / ".adw" / "repos"


def global_breaker_path() -> Path:
    """Where the account-wide cooldown store lives: `ADW_GLOBAL_BREAKER`, else
    `%LOCALAPPDATA%/adw/breaker.json`, else `~/.adw/breaker.json`."""
    env = os.environ.get("ADW_GLOBAL_BREAKER")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "adw" / "breaker.json"
    return Path.home() / ".adw" / "breaker.json"


def sweep_lock_path() -> Path:
    """Single-flight lock for the whole sweep (one process at a time,
    account-wide — unlike `poll_once`'s per-repo lock, there is only one)."""
    env = os.environ.get("ADW_SWEEP_LOCK")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) / "adw" if local else Path.home() / ".adw"
    return root / "locks" / "poll-all.lock"


# --- global cooldown ---------------------------------------------------------


def read_global_cooldown(now: _dt.datetime | None = None) -> str | None:
    """Refusal message if the global cooldown is still active, else None.
    Mirrors `safety.check_cooldown`: any read error (missing/unreadable file)
    fails OPEN — it never blocks a sweep on a malformed store."""
    path = global_breaker_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        until = _dt.datetime.fromisoformat(raw["cooldown_until"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if until.tzinfo is None:
        until = until.replace(tzinfo=_dt.timezone.utc)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if until <= now:
        return None
    minutes = int((until - now).total_seconds() // 60) + 1
    return f"global cooldown active for ~{minutes} more minute(s) (until {raw['cooldown_until']}); reason: {raw.get('reason')}"


def write_global_cooldown(until_iso: str, reason: str) -> None:
    """Atomically write the account-wide cooldown store (temp-file + replace,
    same idiom as `tickets._atomic_write_text`) so a crashed write never leaves
    a half file that later parses as a bogus far-future cooldown."""
    path = global_breaker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cooldown_until": until_iso,
        "reason": reason,
        "written_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- discovery ---------------------------------------------------------------


def discover_targets(token: str, owner: str) -> list[RepoDescriptor]:
    """Every account repo with >=1 open `adw` issue. A per-repo issue-listing
    error is logged and skipped — never aborts discovery for the rest."""
    targets: list[RepoDescriptor] = []
    for repo_owner, name, clone_url in list_account_repos(token, owner):
        try:
            issues = list_adw_issues(repo_owner, name, token)
        except GitHubError as exc:
            print(f"discover: skipping {repo_owner}/{name}: {exc}")
            continue
        if issues:
            targets.append(RepoDescriptor(repo_owner, name, clone_url))
    return targets


# --- clone management ---------------------------------------------------------


def ensure_clone(descriptor: RepoDescriptor) -> Path | None:
    """Resolve `descriptor`'s local working tree, cloning/fetching as needed.
    The engine's own repo short-circuits to `paths.engine_root()` (self-host —
    no clone, no network). Any git failure is logged and returns None (isolated
    — the caller skips this repo, the rest of the sweep continues)."""
    if _ENGINE_SLUG is not None and (descriptor.owner, descriptor.name) == _ENGINE_SLUG:
        return paths.engine_root()
    repo_path = managed_repos_dir() / descriptor.owner / descriptor.name
    try:
        if repo_path.exists():
            subprocess.run(
                ["git", "fetch", "--prune", "origin"],
                cwd=str(repo_path), capture_output=True, text=True, check=True,
            )
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=str(repo_path), capture_output=True, text=True, check=True,
            )
            subprocess.run(
                ["git", "merge", "--ff-only", "origin/main"],
                cwd=str(repo_path), capture_output=True, text=True, check=True,
            )
        else:
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", descriptor.clone_url, str(repo_path)],
                capture_output=True, text=True, check=True,
            )
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"ensure_clone: skipping {descriptor.slug}: {exc}")
        return None
    return repo_path


# --- per-repo ADW_REPO context -------------------------------------------------


@contextmanager
def _target(repo_path: Path) -> Iterator[None]:
    """Point `paths.target_root()` at `repo_path` for the block, restoring the
    prior `ADW_REPO` (or unsetting it) and clearing the cache on both entry and
    exit — even on exception — so a crash mid-turn never leaks the wrong
    target into the next repo's turn."""
    prior = os.environ.get(paths.ADW_REPO_ENV)
    os.environ[paths.ADW_REPO_ENV] = str(repo_path)
    paths.target_root.cache_clear()
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(paths.ADW_REPO_ENV, None)
        else:
            os.environ[paths.ADW_REPO_ENV] = prior
        paths.target_root.cache_clear()


# --- sweep --------------------------------------------------------------------


@dataclass
class SweepResult:
    tickets_run: int
    stop_reason: str


def sweep(*, max_iterations: int | None = None, stale_seconds: float = 2 * 60 * 60) -> SweepResult:
    """One sweep: discover -> clone -> sync every repo, then work tickets
    round-robin one-per-repo until every backlog empties or a quota halt fires.
    No ticket cap — the global cooldown (or empty backlogs) is the only stop.
    Every per-repo step is isolated: a clone/sync/ticket failure in one repo
    never aborts the others."""
    cooldown = read_global_cooldown()
    if cooldown is not None:
        return SweepResult(0, cooldown)

    try:
        token = get_token()
        owner, _ = engine_repo_slug()
    except GitHubError as exc:
        return SweepResult(0, f"discovery failed: {exc}")

    try:
        descriptors = discover_targets(token, owner)
    except GitHubError as exc:
        return SweepResult(0, f"discovery failed: {exc}")

    active_repos: list[Path] = []
    repo_slugs: dict[Path, tuple[str, str]] = {}
    for descriptor in descriptors:
        repo_path = ensure_clone(descriptor)
        if repo_path is None:
            continue
        try:
            with _target(repo_path):
                pull_and_sync()
        except GitHubError as exc:
            print(f"sync: skipping {descriptor.slug}: {exc}")
            continue
        active_repos.append(repo_path)
        repo_slugs[repo_path] = (descriptor.owner, descriptor.name)

    if not active_repos:
        return SweepResult(0, "no repos with open adw issues to work")

    models = json.loads(paths.models_path().read_text(encoding="utf-8"))
    budgets = json.loads(paths.budgets_path().read_text(encoding="utf-8"))
    iterations = max_iterations or budgets["max_iterations_default"]

    tickets_run = 0
    in_flight_skips: dict[Path, set[str]] = {}
    while active_repos:
        repo_path = active_repos.pop(0)
        with _target(repo_path):
            try:
                reap_stale_in_progress(stale_seconds=stale_seconds)
                story = pick_next_story(
                    load_prd(paths.prd_path()), exclude=in_flight_skips.get(repo_path)
                )
                if story is None:
                    continue  # backlog empty here — drop from rotation
                owner, repo = repo_slugs[repo_path]
                ref = in_flight_ref(owner, repo, story.id, token, repo_path)
                if ref is not None:
                    print(f"skipped: {story.id} already in flight ({ref})")
                    in_flight_skips.setdefault(repo_path, set()).add(story.id)
                    active_repos.append(repo_path)
                    continue
                stage_order = STAGE_ORDER_BY_TYPE.get(story.type)
                if stage_order is None:
                    continue  # defensive: schema restricts type, but never dispatch blind
                outcome = run_one_story(
                    story, stage_order,
                    models=models, budgets=budgets, max_iterations=iterations,
                )
            except Exception as exc:  # noqa: BLE001 — one repo's crash must not kill the sweep
                print(f"sweep: {repo_path} raised {exc.__class__.__name__}: {exc}")
                continue
            tickets_run += 1
            if outcome.outcome == "quotad":
                cooldown_until = load_state(paths.state_path()).cooldown_until
                if cooldown_until:
                    write_global_cooldown(cooldown_until, f"{repo_path.name}/{story.id} quotad")
                return SweepResult(tickets_run, f"quotad at {repo_path.name}/{story.id}")
        active_repos.append(repo_path)  # still has work (or might later) — keep in rotation

    return SweepResult(tickets_run, "no open stories remain in any repo")


# --- CLI ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="per-ticket plan->review cap (default from budgets.json)",
    )
    args = parser.parse_args()

    try:
        with single_flight(sweep_lock_path(), stale_seconds=DEFAULT_STALE_SECONDS):
            result = sweep(max_iterations=args.max_iterations)
    except LockHeld as exc:
        print(f"skipped: {exc}")
        return 0

    print(f"sweep: ran {result.tickets_run} ticket(s); {result.stop_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
