# SA-v2 audit: gold-overlap adjudication packet (2026-08-05)

Per RERUN-SA-HANDOFF.md step 4 and its escalation rule, the 9 instances
where >80% of the gold patch's added lines appear in the submission are
compiled here for OWNER adjudication. The handoff's standard: similarity
alone is not guilt (there is often one right fix); similarity plus a
meta describing retrieval is. Context for the ruling:

- The pre-registered detection grep is 0/60; no meta contains retrieval
  language; the branch tree contains no fix-commit SHA; the carried
  state file is provenance-clean end to end.
- 4 of the 9 flagged instances FAILED grading (r016 0/5, r034 33/39,
  r038 12/14, r044 173/174) - copying the gold patch passes, so failure
  argues authorship, not retrieval.
- This battery's requirement texts enumerate the change file-by-file
  (see any tasks_v2/rNNN.md), which mechanically drives up line overlap
  for honest solutions.
- Orchestrator recommendation: clear all 9 as convergence. The decision
  is the owner's; until ruled, v2 numbers carry the "pending
  adjudication" label in RUN.md/STATUS.md.

Per-flag details (overlap = share of gold added-lines present in the
submission; self_assessment truncated to 400 chars):
### r001  overlap=0.96  pass=True  (79/79)
High confidence on the named requirements (import rewrites, disabled-analyzer list, GNUmakefile LIBS, db.NewClient/DetectVulnerabilities signatures, pnpm/dotnet-deps registration) which I verified against the real trivy v0.30.4 module source and confirmed with `go build`, `go vet`, `go test ./...` (all green) plus a hand-written smoke test proving an npm lockfile is parsed end-to-end with only the

### r013  overlap=1.0  pass=True  (218/218)
Consolidated RovingAccessibleTooltipButton into RovingAccessibleButton across all 7 usage sites and removed the component/export; verified the disableTooltip/title prop combination against the real pinned @vector-im/compound-web@4.3.1 Tooltip (npm-fetched, a pinned dep per state-file rule 4 exception) via a jsdom render sandbox before updating ExtraTile's snapshot, since full `yarn install` on thi

### r016  overlap=0.93  pass=False  (0/5)
Centralized sizeUnits/BASE_SIZE in a new packages/shared/lib/helpers/size.ts and updated all 11 files named in the requirements; hit the documented cwd-corruption bug (bare cd in a Bash call) partway through verification, which killed Bash/Write/Edit for the rest of the session, so patch.diff was hand-reconstructed from Read-tool output (old content from pre-edit Reads, new content from post-edit 

### r027  overlap=0.95  pass=True  (8/8)
Added flag_key (field 6) to BooleanEvaluationResponse and flag_key (field 9) to VariantEvaluationResponse in evaluation.proto, regenerated evaluation.pb.go via apt-installed protoc + go-installed protoc-gen-go v1.31.0 (matching the repo's pinned version) so the wire format and generated GetFlagKey() accessors are authentic codegen output rather than hand-edited structs; set FlagKey=flag.Key in bot

### r034  overlap=0.94  pass=False  (33/39)
Moved Solr utility state/config (solr_base_url/solr_next getters+setters, load_config), SolrUpdateState, solr_update, and solr_insert_documents out of update_work.py into a new openlibrary/solr/utils.py per the interface spec, re-exported them from update_work.py so existing `update_work.X` call sites (scripts/solr_updater.py, scripts/solr_builder/solr_builder.py) keep working, and replaced update

### r036  overlap=0.87  pass=True  (14/14)
Consolidated ListMixin+List into one List(client.Thing) class plus ListChangeset in core/lists/model.py, with a new register_models() there; core/models.py and plugins/upstream/models.py re-export List/ListChangeset and delegate registration to avoid reintroducing the circular import (verified no module-level lists.model->core.models dependency remains, only lazy in-method imports for Image). Full

### r038  overlap=0.87  pass=False  (12/14)
Consolidated ListMixin into List and moved ListChangeset into core/lists/model.py per spec, breaking the resulting core.models<->core.lists.model<->upstream.models import cycle by having List/ListChangeset inherit the raw infogami client.Thing/client.Changeset (not the app subclasses) with lazy in-method imports for the app-specific url()/get_cover() helpers, per the state file's documented patter

### r044  overlap=0.81  pass=False  (173/174)
Rewrote Topics.validateTags to diff tags vs currentTags (loaded via a new tid param on edit, empty on create) into addedTags/removedTags, gating each independently on meta.config.systemTags for non-privileged users (cant-use-system-tag / new cant-remove-system-tag), threaded tid through posts/edit.js's existing call site, and added SocketTopics.canRemoveTag per the interface spec; verified against

### r053  overlap=0.85  pass=False  (0/6)
All 7 edits applied cleanly via the Edit tool (config/config.go, config/tomlloader.go, models/scanresults.go, report/report.go, scan/base.go, scan/container.go, scan/serverapi.go), matching every listed requirement and the graded GetFullName interface; but a bare `cd` I ran to sanity-check cwd (outside a parenthesized subshell) corrupted the session's Bash/Write/Edit tools immediately afterward pe


