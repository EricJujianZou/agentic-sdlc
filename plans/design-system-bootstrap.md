---
name: design-system-bootstrap
description: Handoff for the next agent — bootstrap github.com/EricJujianZou/design-system as a harness target (React+TS+Tailwind, MIT-only, npm-published) via a thin hybrid scaffold, then dogfood the rest of the components. Records the 2026-06-20 decisions and the out-of-scope harness to-dos surfaced that session.
read_when: Picking up the design-system bootstrap, or the post-self-heal harness backlog.
sdlc_stage: build-time
---

# Design-system bootstrap — handoff

Written 2026-06-20 by the interactive session that proved automatic
self-healing (see `memory/self-healing-proven.md`). The human wants the next
agent to execute the bootstrap; this doc records the agreed decisions and the
plan so you don't re-derive them. **Read `CLAUDE.md` first** for operational
facts (no `gh` auth → REST API via `adw/github.py`; stacked branches; the
hourly `\ADW\` task mutates the tree; never push to `main`; Windows/`tzdata`).

## What we're building and why

A reusable **design system** (`EricJujianZou/design-system`, public, currently
empty) so frontend taste + primitives are shared across all future projects
instead of re-imported each time. Per first principles (engine = behavior,
target = work, shared CODE = its own library): the design system is its **own
repo, published as an npm package** — NOT folded into the SDLC engine. The
engine carries the *know-how* (a `frontend-design` skill that says "read the
target's `DESIGN.md` and follow it"); the design-system repo carries the
*code + tokens*.

## Decisions locked (2026-06-20)

- **Stack:** React + TypeScript + Tailwind.
- **Distribution:** published **npm package** (projects add it as a normal
  dependency). Name/scope = OPEN (see questions).
- **Who builds:** the **harness** builds the components (dogfood), but **only
  after a thin hybrid scaffold** lays down tooling + tokens + one reference
  primitive + a passing test — a brand-new empty repo has no test suite for the
  test-evidence gate and no pattern to imitate, which is the harness's weakest
  starting point. Scaffold first, then dogfood.
- **Component sourcing — MIT ONLY:**
  - **shadcn/ui** (MIT, designed to be copied/owned) = the primitives base.
  - **Aceternity UI** — the **free** components are MIT (human verified
    2026-06-20); usable for flair on top of the shadcn base. Still check each
    component's license before pulling; do not pull "pro"/paid ones.
  - **Refero (styles.refero.design) and Mobbin = inspiration only.** They are
    galleries of other companies' copyrighted, trademarked product designs and
    screenshots. **Do NOT copy their CSS/designs or store their screenshots in
    the repo.** A published, reused library is the worst place to bury someone
    else's IP. Taste must be ORIGINAL, merely *informed by* looking at them.
- **Taste pillar = a single `DESIGN.md`** (human-readable tokens + type scale +
  spacing + motion + do/don't), paired with the Tailwind token preset so prose
  and machine-consumed tokens stay in sync. A target can copy + tweak it to
  re-skin per project. It is content, not code.
- **PNG/screenshot references: dropped for now.** Revisit only once real
  designs have been built (then prefer a `references.md` of LINKS + the repo's
  own Storybook screenshots — never stored third-party images).

## Phase 0 — make design-system a harness target (plumbing)

Assumed clone location: `C:/Users/zouju/Coding Projects/design-system` (sibling
to this engine). Per `docs/using-on-another-repo.md`:

1. `git clone https://github.com/EricJujianZou/design-system.git` to that path.
2. Add `prd.json`: `{ "project": "design-system", "stories": [] }`.
3. Add `.claude/settings.json` wiring the **engine's** hooks by **absolute
   path**, and (cross-repo caveat below) with `uv --project` pointed at the
   engine so the `adw` package is importable. Mirror the engine's
   `.claude/settings.json` matchers (PreToolUse Bash|PowerShell + Edit|Write|
   NotebookEdit → `pretooluse_guard.py`; PostToolUse Edit|Write|NotebookEdit →
   `posttooluse_autocommit.py`; Stop → `stop_checklist.py`), but each command
   becomes (note the quotes — the engine path contains a space):

   ```
   uv run --quiet --project "C:/Users/zouju/Coding Projects/agentic-sdlc" python "C:/Users/zouju/Coding Projects/agentic-sdlc/hooks/<hook>.py"
   ```
4. Commit + push (on the target's own branch; PR per its own flow).
5. From then on, run the harness against it with `ADW_REPO` set to that path —
   issues, branches, PRs, and notifications resolve to **design-system's**
   GitHub (`repo_slug()` reads the target's remote).

> **Cross-repo hook caveat (S-011 deferred follow-up):** cross-repo hooks were
> never validated end-to-end. The engine's own hooks use *relative* paths and
> `uv run` from the project; pointed at a target they need the absolute paths +
> `--project` above. **The first cross-repo run is the real test of whether
> this holds.** If a hook fails to import `adw` or resolve the target, that's a
> legitimate self-dev finding — fix it as a harness `system-repair`.

## Phase 1 — thin hybrid scaffold (hand, or one tightly-scoped bootstrap ticket)

Goal: give the harness a green test suite + one pattern to imitate. Deliver:
- `package.json` (scoped name, `react`/`react-dom` as peerDeps, library build
  via **tsup** or Vite library mode, `exports` map, `sideEffects` for Tailwind).
- `tsconfig.json`, Tailwind **preset** that encodes the design tokens.
- **`DESIGN.md`** — original starter taste/tokens (neutral; human re-skins).
- **`references.md`** — curated LINKS only.
- **One reference primitive — `Button`** — adapted from shadcn (MIT), with a
  passing **vitest** + Testing Library test and (optional v1) a Storybook story.
- CI mirroring the engine's intent (lint + typecheck + test on PR).

A green `npm test` (or `uv`-equivalent) is the gate the harness's test-evidence
re-run needs; `Button` is the pattern subsequent components copy.

## Phase 2 — dogfood the rest (harness builds, via GitHub issues on design-system)

File one `adw`-labeled issue per primitive on **design-system's** GitHub
(`feat`, `GH-<n>: <title>` per the naming convention), run the harness with
`ADW_REPO` at the clone, `--max-tickets 1` first:
- `Input`, `Card`, `Typography` (the agreed v1 core primitives).
Each should follow the `Button` pattern, ship a test + story, keep the suite
green. Watch the phone for the stage trail + PR, review/merge per component.

## Decisions resolved 2026-06-20 (follow-up)

- **Aesthetic:** *simple SaaS — blue & white, minimalist.* A ready starter
  `DESIGN.md` (original values + Inter/OFL, conventional token structure, NOT
  the brand spec it was discussed against) is in
  `plans/design-system-DESIGN.starter.md` — drop it into the repo root as
  `DESIGN.md` and refine.
- **Publishing is deferrable.** Use **git-install** (`npm i
  github:EricJujianZou/design-system`) during bootstrap — no registry setup
  needed. When ready to publish: a **public scoped** package
  `@<npm-username>/design-system` (`npm publish --access public`, free). Truly
  *private* packages need a paid npm plan or a private repo; not needed for a
  design system. So the package **name is not blocking Phase 1**.

## Still open (pick at publish time, not before)

- Final npm name/scope (only when you publish) and registry (public npm vs GitHub Packages).
- Storybook in v1 or v2.

## Out-of-scope to-dos discussed this session (record, don't lose)

Harness (`agentic-sdlc`) `system-repair` candidates:
- **Self-heal routing + lighter gating (refined goal).** Today the observer's
  harness-level proposal is only a *comment* on the **target's** source issue
  (human re-types it elsewhere). The point of self-healing is the human
  *doesn't* file manually. Target behavior: on a harness-level classification
  the agent **files a `system-repair` issue in the ENGINE repo**, in a gated
  state, and the human just **reviews + attaches an approval label** to release
  it into the backlog (easy, still gated). Cross-repo makes this sharper: a
  harness bug found while building `design-system` must land in `agentic-sdlc`,
  not on a `design-system` issue.
- **Don't load `CLAUDE.md` into stage-agent invocations** — filed as a GH issue
  this session to dogfood (stage agents are `claude -p` in the repo cwd, so they
  auto-load operator-only `CLAUDE.md`; suppress for stage agents, keep it for the
  interactive assistant).
- **Cross-repo hook wiring** (the S-011 deferred gap above) — promote to a real
  fix once the first cross-repo run exposes its shape.
- **Done-but-open issues re-pulled every poll** (`plans/open_loose_ends.md`).

Engine asset:
- **`frontend-design` skill** that instructs stage agents to read the target's
  `DESIGN.md` and apply it — so taste propagates to every project automatically.

Ops / human (out of agent scope):
- GitHub Projects board mapping `stage:*`/`blocked` labels to columns.
- Regain admin of the ACL-locked `\ADW\` scheduled task; overnight
  sleep/`-WakeToRun`.

Merge gate:
- **PR #37** (CLAUDE.md) was still open at handoff — merge it so its operating
  notes (and the deduped `AGENTS.md` split) land on `main`.
