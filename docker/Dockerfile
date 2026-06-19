# adw-sandbox: the container image stage sessions run in when ADW_ISOLATION=1
# (plans/safety_plan.md §5). The repo is bind-mounted at /workspace at run
# time (NOT copied in), so this image holds only the toolchain a stage needs:
# Node (the Claude CLI is an npm package), Python + uv (hooks run `uv run
# python hooks/*.py`), and git (the autocommit hook commits work).
#
# Build:   docker build -t adw-sandbox:latest -f docker/Dockerfile .
# Used by: adw/isolation.py build_run_command (image name ADW_SANDBOX_IMAGE,
#          default adw-sandbox:latest).
#
# This image deliberately contains NO credentials. At run time adw passes
# only ANTHROPIC_API_KEY and a scoped git token via `-e`; the host credential
# store, ~/.claude session, and ~/.gitconfig are never mounted or copied.
FROM node:20-bookworm-slim

# Toolchain: python3 + git + ca-certs (HTTPS to the API and GitHub). curl is
# only needed to fetch uv during the build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-venv git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# uv (the project's runner): pin the install dir on PATH.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Claude Code CLI, installed globally so `claude` is on PATH for the bare-name
# invocation adw uses inside the container (build_command claude_bin="claude").
RUN npm install -g @anthropic-ai/claude-code

# The autocommit hook (hooks/posttooluse_autocommit.py) commits inside the
# container, so git needs an identity. A neutral one; the real author trail
# is the human merge gate. Mark the mount as a safe directory so git does not
# refuse to operate on a bind-mount it sees as foreign-owned.
RUN git config --system user.name "adw-sandbox" \
    && git config --system user.email "adw-sandbox@localhost" \
    && git config --system --add safe.directory /workspace

WORKDIR /workspace

# No ENTRYPOINT: adw appends the full `claude -p ...` argv to `docker run`,
# so the container's command is supplied per stage by build_run_command.
