"""Container isolation for stage invocations (plans/safety_plan.md §5).

The safety floor wants unattended runs to execute in a container: the host
filesystem outside the repo is unreachable, no host credentials cross the
boundary beyond a scoped git token (and the API key the CLI needs), and
`--dangerously-skip-permissions` becomes defensible because it is confined.

This module is the *plumbing*: it decides whether isolation is on (an env
flag, off by default — the host path stays the documented fallback) and
wraps an inner `claude -p ...` argv in a `docker run` that mounts only the
repo and passes only the scoped env. It never spawns anything itself; the
caller (adw/invoke.py) runs the argv this builds. Building real container
behavior (the image, in-container auth, an egress allowlist) is documented
in README "Container isolation" and verified by hand, not by the offline
test suite — pytest can only assert the argv this module shapes.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

# Off by default: a bare-host run must behave exactly as before when this is
# unset (the documented fallback). Truthy values: 1/true/yes/on.
ISOLATION_ENV = "ADW_ISOLATION"
IMAGE_ENV = "ADW_SANDBOX_IMAGE"
NETWORK_ENV = "ADW_SANDBOX_NETWORK"

DEFAULT_IMAGE = "adw-sandbox:latest"
# Stages need outbound HTTPS (api.anthropic.com, github.com), so the default
# is normal bridged egress — NOT `none`. Tightening this to an allowlist
# proxy is a documented limit, not part of this plumbing.
DEFAULT_NETWORK = "bridge"
CONTAINER_WORKDIR = "/workspace"

# The ONLY host environment variables allowed across the boundary: the API
# key the CLI authenticates with, and a scoped git push token. The host's
# credential store, ~/.claude session, and ~/.gitconfig are deliberately
# never mounted (AC: no host credentials beyond the scoped git token).
_PASSTHROUGH_ENV = ("ANTHROPIC_API_KEY", "ADW_GIT_TOKEN", "GH_TOKEN")

_TRUTHY = {"1", "true", "yes", "on"}


def isolation_enabled(env: Mapping[str, str] | None = None) -> bool:
    """True when ADW_ISOLATION is set to a truthy value."""
    env = os.environ if env is None else env
    return env.get(ISOLATION_ENV, "").strip().lower() in _TRUTHY


def _docker_bin() -> str:
    return os.environ.get("ADW_DOCKER_BIN", "docker")


def build_run_command(
    inner_cmd: list[str],
    *,
    repo_dir: str | Path,
    stage: str,
    image: str | None = None,
    network: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Wrap `inner_cmd` (a bare `claude -p ...` argv) in a `docker run` that
    isolates the host: only the repo is mounted (at CONTAINER_WORKDIR), only
    the scoped env crosses, and no extra mounts/privileges are granted.

    The prompt still reaches the CLI on stdin, so `-i` is set and the caller
    keeps piping the prompt exactly as on the host path. Returns the full
    docker argv; this function runs nothing.
    """
    env = os.environ if env is None else env
    image = image or env.get(IMAGE_ENV) or DEFAULT_IMAGE
    network = network or env.get(NETWORK_ENV) or DEFAULT_NETWORK
    repo = Path(repo_dir).resolve()

    cmd = [
        _docker_bin(), "run", "--rm", "--init", "-i",
        f"--network={network}",
        # Bind-mount the repo only. `--mount` (not `-v`) parses Windows
        # absolute paths unambiguously (the drive-letter colon breaks `-v`).
        f"--mount=type=bind,source={repo},target={CONTAINER_WORKDIR}",
        f"--workdir={CONTAINER_WORKDIR}",
        # The hooks key off these inside the container exactly as on the host.
        "-e", "ADW_TICKET_RUN=1",
        "-e", f"ADW_STAGE={stage}",
    ]
    # Forward only the allowlisted secrets, and only when actually present.
    # `-e NAME` (no value) tells docker to read NAME from this process's env,
    # so the value never appears in the argv (no leak into logs/ps).
    for name in _PASSTHROUGH_ENV:
        if env.get(name):
            cmd += ["-e", name]
    cmd.append(image)
    cmd += inner_cmd
    return cmd
