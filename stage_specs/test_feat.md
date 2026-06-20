---
name: test-spec-feat
description: Contract for the test stage on feat tickets — which checks, in what order, what artifacts.
read_when: Testing a feat ticket (test stage), or checking test evidence (review stage).
sdlc_stage: test
---

# Test spec — feat

Use the project's own toolchain — infer it from its manifest/README
(`pyproject.toml`/`package.json`/…), don't assume Python.

## Checks, in order (stop early only on a hard error, not a failure)

1. **Build/import sanity** — the project still loads: e.g.
   `uv run python -c "import adw"`, or `npm run typecheck`/`build` for a JS/TS
   repo.
2. **Full unit suite** — the project's test command (e.g. `uv run pytest -q`
   or `npm test`; it should match `test_evidence_command` in configs). Record
   the pass/fail count.
3. **Targeted verification** — for each acceptance criterion, the
   smallest command or scenario that proves it (a specific test, a CLI
   invocation, a grep for the expected wiring). Name what you ran.
4. **Frontend only:** Playwright smoke — load the affected page,
   screenshot, confirm the changed element is visible and interactive.

## Evidence format (in your reply, before the status block)

```
- criterion: "<text>"
  ran: <command or test name>
  result: pass | fail — <one line of output that proves it>
```

## Rules

- Never weaken, skip, or delete a test to make the suite pass; that is a
  `failure` with `failure_reason` saying the implementation conflicts
  with an existing test.
- A flaky result counts as a failure — rerun once to confirm, then report.
- You cannot edit files; produce findings, not fixes.
