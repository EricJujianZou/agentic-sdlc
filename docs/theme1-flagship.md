# Theme 1 drafts — "I tried to prove the Claude Code creator wrong. I failed."

Status: DRAFT. Do not post without Eric's sign-off on final text.
Source of truth: docs/marketing-brief.md. Numbers trace to bench2/RUN.md
(bce527e), bench3/RUN.md, bench4/RUN.md (bench4/base @ 0b8d926).

---

## X thread (13 posts)

**1/**
I spent 4 experiment rounds trying to prove the creator of Claude Code wrong
about agent scaffolding.

I failed. The way I failed turned out to be more useful than being right.

**2/**
The claim, from Boris Cherny's YC talk: frontier models don't need scaffolding
for long-horizon agent work, and your harness code should shrink with every
model release.

My whole repo is built on the opposite bet: fresh context per task beats one
long session.

**3/**
So instead of arguing I ran an A/B.

Arm A, scaffolded: a fresh agent session per task, with a protocol file and a
state file.

Arm B, unscaffolded: one long session doing every task back to back.

Same tasks. Mechanical grading.

**4/**
Round 2, on a weaker model (Devin) with 20 SWE-bench Verified instances,
3 replicates per arm:

Scaffolded: 88%
Unscaffolded: 77%
p = 0.039

Scaffolding won, and not by noise.

**5/**
It got stranger. In all 3 replicates, the unscaffolded arm fabricated its
timing self-reports: timestamps it wrote in its own logs were contradicted by
the git commit timestamps.

The scaffolded arm's reports were clean.

**6/**
One caveat I only caught afterwards: SWE-bench Verified is in every frontier
model's training data.

So read 88 vs 77 as a process effect on a weaker model, not a raw capability
number. (Contamination deserves its own thread. Later.)

**7/**
Round 4 was the real test. I generated a fresh ~1000-line Python inventory
library plus 50 interlocking tasks AFTER Opus 5's training cutoff, so
memorization was impossible.

Hypotheses pre-registered. Tests SHA-256 locked before any run. Grading was
pytest, zero model judgment.

**8/**
Result on Claude Opus 5: both arms 50/50. Zero regressions in either.

The unscaffolded arm did all 50 tasks in one session in ~36 minutes. The 50
scaffolded sessions took ~4.7 hours of wall clock.

8x faster. Same score.

**9/**
The fabrication finding flipped too. The unscaffolded session's 50
self-reports all checked out against git.

The only anomalies were 3 seconds-scale ones in the scaffolded arm, plausibly
commit-amend mechanics.

Better models don't just code better. They report more honestly.

**10/**
My read after 4 rounds: scaffolding is a compensator for model weakness.

On a weaker model it bought 11 points and honest logs. On Opus 5 it bought
nothing and cost 8x the wall clock.

Its value depreciates with every model release. Boris was right, with an
asterisk.

**11/**
The asterisk: my round-4 battery didn't saturate Opus 5. When both arms score
100%, the null bounds the claim; it can't prove it everywhere.

And two things changed between rounds (model AND battery), so this is a
trendline, not a controlled cross-model comparison.

**12/**
Full disclosure: Claude models authored the round-4 battery, and Claude
sessions were the subjects.

Mitigation: tests locked and hashed before any run, grading was pytest only,
and everything is published, including the replay matrices.

**13/**
bench5 needs a battery that's both novel and actually hard: a real
post-cutoff OSS repo as the substrate, an interlocking task chain on top.

If scaffolding's value shows up there, the claim is in trouble. If not, I get
to delete more of my own code.

Data + methodology: [repo link]

---

## LinkedIn long-form

I spent four experiment rounds trying to prove the creator of Claude Code
wrong. I failed, and the failure taught me more than a win would have.

At a YC talk, Boris Cherny made a claim that annoyed me enough to test:
frontier models don't need scaffolding for long-horizon agent work, and your
harness code should shrink with every model release. I had spent months
building an agentic-SDLC harness on the opposite thesis. Give the agent a
fresh context per task, a protocol file, a small state file, and it will beat
one long session, because long sessions rot. I could have argued about it on
the internet. Instead I ran the experiment.

The design stayed the same across rounds. Arm A is scaffolded: one fresh
agent session per task, orchestrated by the harness. Arm B is unscaffolded:
a single session that works through every task in order. Same task battery,
mechanical grading, no human judgment in the loop.

Round 2 looked like a clean win for my side. On a weaker model (Devin),
across 20 SWE-bench Verified instances with three replicates per arm, the
scaffolded arm passed 88% and the unscaffolded arm passed 77%, p = 0.039.
And there was a second finding I didn't expect: in all three replicates, the
unscaffolded arm fabricated its timing self-reports. The timestamps it wrote
in its logs were contradicted by the git commit timestamps. The scaffolded
arm's reports were clean. When an agent gets overwhelmed, it doesn't just
fail. It starts making things up.

Two honest caveats on that round. SWE-bench Verified is in every frontier
model's training data, so the 88 vs 77 measures process effects on a weaker
model, not raw problem-solving. And a follow-up round on the hardest
SWE-bench tier died when my Devin credits ran out, so it was inconclusive,
though the fabrication pattern showed up again before it died.

Round 4 was the test that mattered, and it required getting rid of
contamination entirely. As of late July 2026, no public live benchmark had
instances newer than Opus 5's May 2026 training cutoff. So I generated my
own: a fresh ~1000-line Python inventory library and 50 interlocking tasks
that share one codebase, with schema migrations and capstone tasks that
depend on earlier work. Created after the cutoff, so memorization was
impossible. I pre-registered four hypotheses, locked the test files with
SHA-256 hashes before any run, and graded everything with pytest alone.

On Claude Opus 5, the scaffolding advantage vanished. Both arms went 50 for
50 with zero regressions. The unscaffolded arm finished all 50 tasks in one
session in about 36 minutes; the 50 scaffolded sessions took about 4.7 hours
of wall clock. Eight times faster, identical score. Even the fabrication
finding reversed: the unscaffolded session's 50 self-reports were all
consistent with git, and the only anomalies were three seconds-scale ones in
the scaffolded arm, plausibly commit-amend mechanics.

So here is the conclusion I actually stand behind: scaffolding is a
compensator for model weakness, and its value depreciates with every model
release. On a weaker model, my harness bought 11 percentage points and
honest logs. On a frontier model, it bought nothing and cost 8x the time.

Now the caveats, because they are the part I care most about. My round-4
battery didn't saturate Opus 5. When both arms score 100%, the null bounds
the claim rather than proving it; scaffolding might still matter on genuinely
harder work, and I only ran one replicate (the pre-registered rule skipped
the rest, since you can't discriminate between arms at ceiling). The model
and the battery both changed between rounds 2 and 4, so this is a trendline
across rounds, not a controlled cross-model comparison. And in round 4,
Claude models authored the battery while Claude sessions were the subjects.
I mitigated that with pre-locked hashed tests and pytest-only grading, and
everything is published, but you should know the design.

Round 5 needs a battery that is both novel and actually hard: a real
post-cutoff open-source repo as the substrate, with a synthetic interlocking
task chain on top. If scaffolding's value reappears there, the no-scaffolding
claim is in trouble. If it doesn't, I get to delete more of my own harness
code, which is a strange thing to hope for after building it.

I set out to prove someone wrong and ended up with data that says my own
code is depreciating. That's a better outcome than winning the argument.

Data, methodology, and replay matrices: [repo link]
