# M9.4 - Registered Studies and Bounded Local Batch Execution

## Status

**ACCEPTED DESIGN BASELINE; IMPLEMENTED / VALIDATED THROUGH M9.4i LOCAL CORRECTIVE CANDIDATE; INDEPENDENT RE-REVIEW PENDING**

`M94_DESIGN_ACCEPTED=True`

The accepted design baseline was published at `9b7ab42` and synchronized at `199ec34`. Production implementation subsequently proceeded in separately reviewed M9.4a-M9.4f slices. The M9.4f implementation/closure slice was historically published at `b93ae6a`. M9.4g later corrected the first independent-audit findings and was historically re-closed at `68df76b`. M9.4h preserved the 24 accepted design decisions while correcting residual N01-N07 defects and was published through h4 at `306c156a5b58edb8a4dd6331409d473bc08af98b`. The independent re-review of that exact head returned `M95_GATE=BLOCKED` with H01-H05. The current local M9.4i corrective candidate addresses H01-H04 and synchronizes H05 evidence without changing the accepted architecture. Its reproduced pre-publication evidence is 153 H01-H04 focused tests, 245 repository-wide `test_m94*.py` tests, 251 semantic `-k m94` tests with 1098 deselected, 1349 complete Python tests, and clean `git diff --check`. It is not staged, committed or published, and independent re-review remains pending.

M9.4 introduces the durable research workflow above individual
Backtests:

- Study and immutable StudyRevision registration;
- registered Trial accounting before execution;
- deterministic universe-to-Trial expansion;
- truthful reuse of compatible pre-existing evidence;
- durable local research jobs;
- bounded worker concurrency;
- queue claiming;
- cancellation;
- restart recovery;
- partial-failure accounting; and
- truthful Study-level aggregation.

M9.4 extends the accepted M9.2 research catalog and M9.3
instrument/universe/dataset foundations. It does not replace them.

`BEHAVIOR IMPACT: NONE`

This design-draft step changes documentation only. Any later
behavior-changing implementation slice must make its own independently
reviewable behavior-impact declaration.

## 1. Starting baseline

M9.4 begins from:

- branch `m9-v1-research-platform`;
- M9.3 closure
  `da4fd808747a9b09dd41573d3c8ea8bc016ac744`;
- research schema version `1`;
- existing tables:
  - `research_evidence`;
  - `research_artifacts`;
  - `experiment_specs`;
  - `run_attempts`;
- complete Python regression: `1078 passed`;
- clean `git diff --check`;
- clean worktree.

At this baseline there are no production:

- `Study`;
- `StudyRevision`;
- `Trial`;
- `ResearchJob`;
- Study/Trial persistence tables;
- operational queued-attempt creation;
- queued-job claiming;
- user-driven cancellation operation; or
- local research batch scheduler.

The names `QUEUED` and `CANCELLED` already exist in
`RunAttemptState`, but M9.2 intentionally did not claim operational
queue or user-cancellation behavior.

## 2. Existing foundations that remain authoritative

M9.4 must preserve and reuse:

### M9.2

- immutable content-addressed `ResearchArtifact`;
- deterministic `ExperimentSpec`;
- distinct physical `RunAttempt`;
- existing `ResearchEvidence`;
- exact software identity;
- immutable result/manifest artifacts;
- automatic Backtest reproducibility evidence;
- atomic attempt/evidence terminalization;
- stale non-terminal attempt recovery.

### M9.3

- canonical `instrument_id`;
- provider identity separate from canonical identity;
- effective-dated provider mappings;
- immutable `UniverseDefinition`;
- immutable `UniverseSnapshot`;
- `ResolvedUniverseSnapshot`;
- point-in-time membership rules;
- universe-quality classes;
- successor dataset identity and provenance;
- `DatasetReference`;
- binding-aware historical retrieval;
- acquisition-stream storage;
- explicit successor Backtest integration.

### Existing execution authority

`api/backtest_application.py` remains the accepted application Backtest
composition boundary.

M9.4 must ultimately invoke the accepted Backtest/research execution
path. It must not create another implementation of:

- trading signals;
- fills;
- costs;
- risk sizing;
- portfolio accounting;
- drawdown;
- Backtest result calculation.

The M9.3 successor path remains explicit opt-in for existing callers.

M9.4 must not manufacture canonical instrument/provider truth from the
temporary legacy `RELIANCE -> 2885` information.

## 3. M9.4 scope

M9.4 owns:

1. durable Study identity;
2. immutable StudyRevision registration;
3. registered Trial identity;
4. registration-before-execution;
5. deterministic finite Trial expansion;
6. Study/Revision/Trial persistence;
7. exact relationships among Trial, ExperimentSpec, RunAttempt,
   runtime/session ID and ResearchEvidence;
8. truthful reuse of compatible pre-existing evidence;
9. durable ResearchJob queue state;
10. bounded local worker concurrency;
11. atomic queue claiming;
12. duplicate-job execution prevention;
13. queued and running cancellation semantics;
14. restart recovery;
15. retry accounting;
16. partial failure;
17. truthful progress accounting;
18. Study-level independent-account aggregation;
19. explicit reporting denominators; and
20. backend application/service integration required to validate the
    workflow.

M9.4 does not own:

- profitability claims;
- strategy qualification;
- `QualificationPolicy` evaluation;
- qualification decisions;
- Candidate progression;
- robustness qualification;
- WFA/OOS progression;
- persistent PaperCampaigns;
- full research-workspace frontend;
- shared-capital multi-symbol portfolio accounting;
- real-money execution.

Those remain assigned to later milestones.

## 4. Study identity

A `Study` is the durable user-recognizable research investigation.

Examples:

- "SMA crossover on liquid NSE equities";
- "15-minute momentum investigation";
- "RELIANCE pullback research".

`Study` identity is a generated opaque `study_id`.

The identity is not:

- a symbol;
- a strategy ID;
- a Trial ID;
- an ExperimentSpec ID;
- a RunAttempt ID;
- a runtime/session ID; or
- a ResearchEvidence ID.

A Study may have many immutable StudyRevisions.

Study-level presentation metadata such as a display title or archival
flag may change without altering historical StudyRevision contents.

A Study that has influenced research history is not hard-deleted merely
to hide unsuccessful work.

## 5. StudyRevision identity

A `StudyRevision` is one immutable registered research plan.

Registration freezes all material research choices required to
understand what was planned.

The initial M9.4 revision plan includes, at minimum:

- parent `study_id`;
- research hypothesis or research intent;
- strategy/procedure identity;
- supported execution timeframe;
- requested research time range;
- timezone;
- initial simulated capital;
- risk/economic assumptions represented by the accepted configuration;
- exact parameter variant or finite parameter search definition;
- canonical universe definition/reference;
- exact resolved universe snapshot segments;
- each snapshot's quality and provenance references;
- price-adjustment/data-treatment basis;
- pinned executable repository/software revision for the registered execution cohort; and
- evidence-reuse policy.

The software revision pin is intentional even though exact software
identity also belongs to `ExperimentSpec`.

The two identities answer different questions:

- StudyRevision pins one executable-software cohort so one registered
  research population cannot silently mix code revisions;
- ExperimentSpec records that same exact executable revision as part of
  deterministic computation identity.

A bug fix or other executable change may alter computation semantics.
Executing the same registered Trial population under another revision
therefore requires a new StudyRevision rather than silently mixing software
cohorts.

The exact accepted serialized plan uses a versioned canonical schema.

Candidate schema name:

`kanasu.study-revision.v1`

The canonical plan is persisted as an immutable content-addressed
research artifact.

Candidate artifact kind:

`STUDY_REVISION_PLAN`

The `study_revision_id` is the content identity of those canonical plan
bytes. The plan includes the parent `study_id`, so identical plan text
belonging to different Studies cannot accidentally become one revision.

Creation/registration time is metadata and is not allowed to alter the
canonical plan fingerprint.

Each Study additionally receives a monotonic human-readable
`revision_number`.

Registration of exactly the same canonical plan is idempotent.

## 6. Exactly when a new StudyRevision is required

A new StudyRevision is required when any material choice changes,
including:

- hypothesis or declared research intent;
- strategy/procedure identity;
- timeframe;
- research period;
- canonical universe selection;
- universe membership snapshot or temporal membership evidence;
- universe-quality assumption;
- parameter variant/search space;
- initial capital;
- effective risk/economic configuration;
- price-adjustment/data-treatment assumption;
- pinned executable software revision;
- evidence-reuse policy; or
- another field that changes the planned Trial population,
  computation meaning or research interpretation.

A new revision is not required merely because:

- a job waits longer in the queue;
- worker ordering changes;
- the backend worker limit changes;
- the application restarts;
- a failed physical attempt is retried under the exact registered plan;
- display-only Study metadata changes.

A registered StudyRevision is never edited in place.

## 7. Registration transaction

Registration must complete before any Trial from the revision may
execute.

The registration flow is:

~~~text
draft Study plan
    |
    v
validate supported research choices
    |
    v
resolve exact UniverseSnapshot coverage
    |
    +-- gap / overlap / invalid quality
    |       -> registration fails
    |       -> no partial Trial population
    |
    v
freeze canonical StudyRevision plan
    |
    v
deterministically expand the complete finite Trial population
    |
    v
persist StudyRevision + every Trial atomically
    |
    v
REGISTERED
~~~

The complete Trial population therefore exists durably before execution
starts.

M9.4 must not execute the first Trial while later Trials are still being
discovered or silently added.

A material plan change after registration creates another revision.

## 8. Universe expansion into Trials

M9.4 reuses `resolve_universe_snapshots(...)`.

The Study research range must first resolve without the gaps or conflicting
overlaps prohibited by M9.3.

Resolved snapshots are membership evidence. A snapshot transition does not by
itself require a new simulated account for an instrument that remains
continuously eligible.

For each parameter/configuration variant, Trial expansion:

1. resolves the ordered `ResolvedUniverseSnapshot` sequence;
2. collects, for each canonical `instrument_id`, every applied subrange in
   which that instrument is a member;
3. coalesces adjacent subranges into one maximal continuous membership episode
   when the previous applied range ends exactly where the next begins and the
   instrument remains a member;
4. preserves the complete ordered snapshot/subrange evidence supporting that
   episode;
5. creates a new episode when there is a real interval during which the
   instrument is not an applicable universe member; and
6. registers one Trial per instrument, continuous membership episode and exact
   parameter/configuration variant.

The deterministic expansion unit is:

~~~text
StudyRevision
+ canonical instrument_id
+ maximal continuous membership episode
+ ordered snapshot/subrange evidence
+ exact parameter/configuration variant
= one registered Trial
~~~

Example:

~~~text
Jan-Mar: RELIANCE, TCS
Apr-Jun: RELIANCE, INFY
~~~

RELIANCE remains continuously present. Its simulated account therefore does
not reset merely because TCS left and INFY joined. The RELIANCE Trial covers
the continuous Jan-Jun episode while retaining both snapshot identities and
their exact applied ranges as membership evidence.

If RELIANCE were absent for an interval and later re-entered, that genuine
membership gap creates separate Trial episodes. Kanasu does not silently run a
Trial through a period in which its registered universe evidence says the
instrument was not a member.

This preserves M9.3 temporal membership truth without manufacturing account
resets from unrelated constituent changes.

For a fixed `CURRENT_SNAPSHOT` or `CUSTOM_FIXED` universe covering the complete
research range, each instrument/parameter combination normally produces one
Trial.

Trial expansion order is canonical using:

1. membership-episode start;
2. membership-episode end;
3. canonical instrument identity;
4. canonical ordered snapshot/subrange evidence identity; and
5. parameter/configuration identity.

The complete Trial population is finite before registration commits.

Registration rejects an expansion exceeding the backend-owned configured
safety limit rather than constructing an unbounded workload.

The safety limit is operational configuration, not a financial result.

## 9. Trial identity

A `Trial` is one registered research test in one immutable
StudyRevision.

Candidate identity schema:

`kanasu.trial.v1`

Deterministic Trial identity includes:

- `study_revision_id`;
- canonical `instrument_id`;
- exact maximal continuous membership-episode range;
- canonical ordered snapshot/subrange membership evidence;
- exact registered parameter/configuration variant.

Trial registration time is metadata and does not affect Trial identity.

A Trial exists before physical execution.

A Trial is not:

- an ExperimentSpec;
- a ResearchJob;
- a RunAttempt;
- a Backtest runtime/session;
- a ResearchEvidence record.

Retries do not create additional Trials.

A universe snapshot transition that leaves the instrument continuously present
does not create another Trial or reset its simulated account merely because
snapshot identity changed.

This prevents both operational retries and unrelated universe transitions from
inflating research accounting.

## 10. Trial and ExperimentSpec relationship

The registered Trial describes what research was planned.

`ExperimentSpec` continues to describe the exact deterministic
computation after exact dataset identity and exact executable identity
are known.

Therefore a new Trial may initially have no ExperimentSpec.

The first successful specification-preparation step may bind the Trial
to exactly one `experiment_spec_id`.

That binding is one-way and immutable.

After a Trial has an ExperimentSpec:

- retries must use that exact ExperimentSpec;
- a different dataset fingerprint cannot silently replace it;
- a different software revision cannot silently replace it;
- a different configuration fingerprint cannot silently replace it.

If a material exact computation identity must change after binding,
Kanasu requires new research lineage rather than silently rewriting the
registered Trial.

This preserves the distinction:

~~~text
Trial
= registered research test

ExperimentSpec
= exact deterministic computation

RunAttempt
= one physical execution attempt
~~~

## 11. ResearchJob is the durable queue authority

M9.4 introduces a separate durable `ResearchJob`.

This resolves the M9.4 queue-ownership question.

Queue state does not live primarily on Trial because:

- a Trial is research/search identity;
- one Trial may require more than one operational retry.

Queue state does not live only on RunAttempt because:

- a queued task can exist before exact dataset identity exists;
- therefore an ExperimentSpec and RunAttempt may not yet be legal to
  create.

A ResearchJob represents one operational attempt to progress one Trial.

One Trial may therefore have multiple ResearchJobs over time.

A terminal ResearchJob is immutable and is never reopened.

Retry creates another ResearchJob for the same Trial.

Initial M9.4 retry eligibility is limited to Trials whose current disposition
is:

- `FAILED`;
- `CANCELLED`; or
- `INTERRUPTED`.

The retry transaction:

- preserves the old terminal ResearchJob;
- appends a Trial-disposition history event preserving the prior disposition;
- changes the Trial's current disposition back to `PENDING`;
- creates a new `QUEUED` ResearchJob; and
- never changes `total_registered_trials`.

`EXECUTED` and `REUSED` Trials are not retried through this operation.

`INVALID` and `INSUFFICIENT` Trials are not automatically reopened either.
Changing material inputs or assumptions requires new registered research
lineage.

Thus retry continues one registered research test without erasing earlier
failure, cancellation or interruption.

## 12. ResearchJob state

M9.4 uses a separate `ResearchJobState` with the familiar vocabulary:

- `QUEUED`;
- `RUNNING`;
- `SUCCEEDED`;
- `FAILED`;
- `CANCELLED`;
- `INTERRUPTED`.

The names intentionally align with execution vocabulary, but
`ResearchJob` and `RunAttempt` remain different objects.

A ResearchJob records, at minimum:

- `job_id`;
- `trial_id`;
- state;
- creation time;
- claim/start time;
- terminal time;
- worker/claim identity;
- cancellation-request time when applicable;
- linked `attempt_id` when a RunAttempt became legal;
- completion kind when successful;
- reused prior attempt/evidence references when applicable;
- bounded failure classification/message.

Successful completion kind is explicitly one of:

- `EXECUTED`;
- `REUSED`.

Reuse therefore cannot masquerade as a new physical execution.

## 13. Initial queue creation

Registering a StudyRevision does not need to start execution
immediately.

The accepted workflow is:

~~~text
register StudyRevision and every Trial
        |
        v
inspect frozen registered population
        |
        v
start revision batch
        |
        v
atomically create one initial QUEUED ResearchJob
for each eligible PENDING Trial with no prior job
        |
        v
bounded workers claim jobs
~~~

Initial batch start is idempotent.

The first successful start records operational
`initial_batch_started_at` metadata and creates the initial ResearchJobs.

Calling start again for an already-started StudyRevision:

- creates no duplicate initial jobs;
- creates no additional Trials;
- does not reset completed or failed history; and
- returns the existing batch/progress state.

Retries are a separate explicit operation. Repeating batch start never creates
retry jobs.

Initial queue creation is atomic for the registered population.

A revision cannot silently gain new Trials merely because execution started.

## 14. Bounded local concurrency

M9.4 is a local, single-user research workflow.

Backend application configuration owns worker concurrency.

The Study request and frontend do not directly dictate arbitrary worker
counts.

Candidate configuration:

`research_max_workers`

Requirements:

- positive integer;
- backend validated;
- subject to an implementation safety ceiling;
- active claimed jobs never exceed the configured worker count for the
  authoritative scheduler.

Worker count is operational metadata and does not alter StudyRevision or
ExperimentSpec financial identity.

The initial implementation may use a bounded local thread pool or an
equivalent bounded execution primitive.

M9.4 does not claim distributed-worker scheduling.

Multiple independent Kanasu application processes concurrently
operating the same research database are outside the supported V1
operational envelope unless a later separately validated design adds
global scheduler ownership.

Per-job SQLite claiming must nevertheless remain duplicate-safe.

## 15. Queue claiming and duplicate-worker prevention

A worker must never obtain work by:

1. reading `QUEUED`;
2. releasing the database;
3. later blindly writing `RUNNING`.

That pattern permits duplicate execution.

Claiming must be one SQLite transactional operation.

Conceptually:

~~~text
BEGIN IMMEDIATE
    choose next eligible QUEUED job
    conditionally transition that exact job
        QUEUED -> RUNNING
    attach worker/claim identity and claimed_at
COMMIT
~~~

The claim succeeds only if the job was still `QUEUED`.

Competing workers therefore cannot both successfully claim the same
job.

Initial ordering is deterministic FIFO using durable creation ordering
with `job_id` as the stable tie-breaker.

M9.4 does not introduce user job priorities.

## 16. Relationship to RunAttempt

A claimed ResearchJob may perform specification preparation first.

If exact ExperimentSpec identity cannot legally be established, the job
may fail without creating a RunAttempt.

Once exact ExperimentSpec identity exists:

1. bind the Trial if it is not yet bound;
2. enforce an existing Trial binding if one already exists;
3. create a distinct RunAttempt only when new financial execution is
   actually going to occur.

One executing ResearchJob links to at most one new RunAttempt.

A retry:

- keeps the same Trial;
- creates a new ResearchJob;
- creates a new RunAttempt if financial execution occurs again;
- retains the exact Trial-bound ExperimentSpec.

Runtime/session ID remains separate.

ResearchEvidence remains separate.

## 17. Truthful reuse of pre-existing evidence

M9.4 may reuse pre-M9.4 or earlier M9.4 evidence only after the Trial has
been registered.

Reuse never changes the historical creation time or meaning of the old
RunAttempt.

The minimum reuse condition is exact compatibility:

- exact same ExperimentSpec;
- prior RunAttempt is `SUCCEEDED`;
- required immutable result artifact exists and verifies;
- required ResearchEvidence exists;
- evidence satisfies the accepted reproducibility requirement for this
  reuse path.

M9.4 initial reuse must not use:

- approximately similar configuration;
- matching symbol text alone;
- matching result metrics alone;
- a different dataset fingerprint;
- a different software revision;
- incomplete evidence presented as accepted exact reuse.

The flow is:

~~~text
registered Trial
    |
    v
resolve exact ExperimentSpec
    |
    v
find compatible earlier successful evidence
    |
    +-- none / reuse forbidden
    |       -> create new RunAttempt and execute
    |
    +-- exact accepted evidence available
            -> no new RunAttempt
            -> ResearchJob succeeds with completion_kind=REUSED
            -> Trial records reused source identities
~~~

For pre-M9.4 evidence, the new Trial's registration timestamp remains
later than the original execution.

Kanasu therefore says:

"this registered Trial reused earlier compatible evidence"

and never:

"that earlier execution was already a registered Trial."

## 18. Evidence-reuse policy

StudyRevision registration freezes the chosen reuse behavior.

Initial candidate values:

- `ALLOW_EXACT_ACCEPTED`;
- `FORCE_NEW_EXECUTION`.

`ALLOW_EXACT_ACCEPTED` permits only the exact reuse rules in this
document.

`FORCE_NEW_EXECUTION` always creates a new RunAttempt after exact
specification preparation even when compatible prior evidence exists.

Changing reuse policy requires a new StudyRevision.

## 19. Trial disposition

ResearchJob execution state is not sufficient for research accounting.

M9.4 maintains a Trial-level **current disposition**, distinct from
qualification.

Candidate dispositions are:

- `PENDING`;
- `EXECUTED`;
- `REUSED`;
- `INVALID`;
- `INSUFFICIENT`;
- `FAILED`;
- `CANCELLED`;
- `INTERRUPTED`.

Meanings:

- `PENDING` - registered and currently awaiting durable resolution;
- `EXECUTED` - authoritative computation completed through a new physical
  RunAttempt;
- `REUSED` - exact compatible earlier evidence was deliberately reused;
- `INVALID` - input/data validity prevents the requested interpretation;
- `INSUFFICIENT` - usable history/evidence is insufficient;
- `FAILED` - preparation/execution failed for another classified reason;
- `CANCELLED` - cancellation became effective before successful completion;
- `INTERRUPTED` - executing work lost its process before truthful completion.

These are not qualification decisions.

M9.5 owns research rejection, eligibility and acceptance policy.

A Trial with a negative financial result is still `EXECUTED`.

"Losing money" is a result property and never causes the Trial to disappear.

### 19.1 Append-only Trial disposition history

The Trial row stores the current disposition used for current workflow and
progress.

Every disposition transition is also written to append-only
`trial_disposition_events`.

Each event records at minimum:

- immutable event ID;
- Trial ID;
- monotonically increasing Trial-local sequence number;
- previous disposition when applicable;
- new disposition;
- timestamp;
- causing ResearchJob ID when applicable;
- bounded reason/classification.

Registration records:

`NONE -> PENDING`

Successful new execution records:

`PENDING -> EXECUTED`

Exact evidence reuse records:

`PENDING -> REUSED`

Failure, effective cancellation and interruption record their corresponding
terminal dispositions.

### 19.2 Retry preserves prior history

Initial retry eligibility is limited to:

- `FAILED`;
- `CANCELLED`;
- `INTERRUPTED`.

An explicit retry appends, for example:

`FAILED -> PENDING`

and creates a new ResearchJob.

If that retry succeeds, another event records:

`PENDING -> EXECUTED`

The Trial's current disposition is now `EXECUTED`, but its earlier failure
remains permanently inspectable through:

- the previous terminal ResearchJob;
- its RunAttempt/evidence where one existed; and
- append-only Trial disposition history.

Retry therefore neither rewrites history nor creates another Trial.

### 19.3 Progress after retry

`total_registered_trials` never changes because of retry.

An explicit retry may move one Trial from a retryable terminal disposition
back to `PENDING`. Consequently the current terminal-count portion of progress
may temporarily decrease.

That is truthful: the denominator is unchanged while unresolved execution work
has explicitly been reopened.

Historical terminal events remain inspectable throughout.

## 20. Cancellation semantics

### 20.1 Queued cancellation

A queued job can be atomically transitioned:

`QUEUED -> CANCELLED`

No RunAttempt is created.

The Trial receives `CANCELLED` when no other active job can still
complete it.

### 20.2 Running cancellation request

A running job is not immediately relabelled `CANCELLED`.

Instead Kanasu durably records:

`cancel_requested_at`

The job remains `RUNNING` until the worker acknowledges a safe
cancellation point or actual computation terminates.

This avoids claiming that work stopped while it is still running.

### 20.3 Cooperative cancellation checkpoints

M9.4 may stop safely at boundaries such as:

- before historical retrieval;
- after retrieval but before new financial execution;
- after exact-spec/reuse resolution but before new execution.

M9.4 does not kill Python worker threads asynchronously.

### 20.4 Non-interruptible computation

The accepted Backtest engine is not silently redesigned merely to add
mid-calculation cancellation.

If cancellation is requested after non-interruptible authoritative
financial execution has begun:

- the request remains recorded;
- Kanasu does not falsely report immediate cancellation;
- the computation is allowed to reach a truthful terminal result;
- if successful completion occurred before cancellation could become
  effective, the ResearchJob/Trial remain successful and the late
  cancellation remains inspectable;
- if application/process termination occurs instead, recovery uses
  `INTERRUPTED`.

This is intentionally more conservative than unsafe forced thread
termination.

## 21. Batch cancellation

Cancelling a StudyRevision batch means:

- every still-queued job is atomically cancelled;
- every running job receives a durable cancellation request;
- no new retry job is created automatically;
- running work follows the cooperative rules above.

The StudyRevision and all registered Trials remain in research history.

Batch cancellation never deletes unsuccessful or unfinished Trials.

## 22. Restart recovery

Durable queue state survives application restart.

Startup recovery is separate from execution resumption.

On startup:

- `QUEUED` ResearchJobs remain `QUEUED`;
- stale `RUNNING` M9.4 jobs from the prior process become `INTERRUPTED`;
- the affected Trial current disposition becomes `INTERRUPTED` when no
  successful terminalization for that job was committed;
- that interruption is appended to Trial-disposition history;
- associated non-terminal M9.2 RunAttempts become `INTERRUPTED` according to
  the accepted attempt-recovery rule;
- existing terminal jobs remain unchanged.

Startup recovery itself does **not** automatically claim queued jobs.

After restart, the scheduler stays dormant until the user/application
explicitly resumes execution for the registered StudyRevision.

Explicit resume:

- claims the already-existing `QUEUED` jobs;
- creates no replacement Trials;
- creates no duplicate initial ResearchJobs; and
- does not automatically retry jobs recovered as `INTERRUPTED`.

An interrupted Trial requires the separate explicit retry operation if it is
to execute again.

A stale running job is therefore never silently replayed.

If a stale job already bound its Trial to an ExperimentSpec, that binding
remains and any retry must use the same ExperimentSpec.

Recovery must not create contradictions such as:

- Trial `EXECUTED` while its only current job remains `RUNNING`;
- ResearchJob `SUCCEEDED` while its new RunAttempt remains `RUNNING`;
- accepted terminal evidence attached to stale active execution.

Recovery and terminalization therefore use one research-database authority.

## 23. Transactional terminalization

M9.4 uses the same research SQLite database as M9.2 so related lifecycle
state can be coordinated transactionally.

For a newly executed successful Trial, the durable terminal operation
must coordinate, as applicable:

- result artifact metadata;
- ResearchEvidence;
- RunAttempt `SUCCEEDED`;
- ResearchJob `SUCCEEDED`;
- job completion kind `EXECUTED`;
- Trial disposition `EXECUTED`;
- exact linked identities.

For execution failure after a RunAttempt exists, the terminal operation
must coordinate:

- applicable non-accepted evidence;
- RunAttempt terminal failure/interruption state;
- ResearchJob terminal state;
- Trial terminal disposition.

For exact evidence reuse, one transaction links:

- existing immutable ExperimentSpec;
- existing successful RunAttempt/evidence/result;
- new ResearchJob completion kind `REUSED`;
- new Trial disposition `REUSED`.

A database failure must not return a Study status claiming durable
success that was not committed.

Content-addressed file creation may still leave a safe unreferenced
orphan file exactly as permitted by M9.2.

## 24. Partial failure

One failed Trial does not erase or invalidate unrelated completed
Trials.

Default batch behavior is:

- continue processing independent remaining jobs after an
  instrument-specific failure;
- persist the exact failure/disposition;
- preserve successful/reused Trials;
- expose partial completion truthfully.

A scheduler/database failure that prevents trustworthy lifecycle
persistence stops new claims rather than continuing to create
untracked work.

No automatic "all succeeded" status is allowed when only part of the
registered population completed.

## 25. Failure classification

Where applicable M9.4 reporting keeps distinct:

- invalid registered input;
- invalid canonical data;
- insufficient history;
- dataset/provider retrieval failure;
- exact-specification preparation failure;
- deterministic financial-computation failure;
- transient worker/operational failure;
- research-database persistence failure;
- cancellation;
- interruption.

Research qualification rejection is not one of these operational
failure classes. M9.5 owns that decision.

## 26. Progress accounting

The primary denominator is:

`total_registered_trials`

It is frozen when StudyRevision registration commits.

Progress reports expose counts such as:

- total registered;
- pending;
- queued;
- running;
- executed;
- reused;
- invalid;
- insufficient;
- failed;
- cancelled;
- interrupted.

Terminal progress is calculated from explicit terminal Trial
dispositions.

Kanasu must not report "100% successful" merely because all surviving
successful jobs completed while failed/cancelled Trials were hidden.

Retries do not increase `total_registered_trials`.

They increase operational job/attempt history only.

## 27. Independent-account aggregation

M9.4 implements the Study-aggregation portion of
`RESEARCH-RULE-004`.

Universe Backtests remain independent per-instrument simulated
accounts.

Study reporting may calculate distributions and breadth statistics
across completed/reused independent results, for example:

- count;
- median;
- mean where appropriate;
- quantiles;
- proportion meeting a clearly stated descriptive condition.

Every aggregate metric must identify at least:

- registered Trial denominator;
- result-bearing Trial count;
- excluded/failed/invalid/cancelled/interrupted counts relevant to the
  metric.

Independent P&L values must not be summed and presented as one
shared-capital portfolio.

An aggregate of returns must be labelled as a research distribution or
cross-sectional statistic, not portfolio return.

M9.4 introduces no cross-instrument position netting, cash sharing,
portfolio sizing or portfolio drawdown.

## 28. Persistence design

M9.4 uses an additive research-schema migration.

Candidate next schema version:

`RESEARCH_SCHEMA_VERSION = 2`

Existing version-1 tables and rows remain authoritative and
backward-compatible.

Candidate new tables are:

### `studies`

At minimum:

- `study_id` primary key;
- creation time;
- display metadata;
- archived flag if supported.

### `study_revisions`

At minimum:

- `study_revision_id` primary key;
- `study_id` foreign key;
- monotonic `revision_number`;
- canonical plan artifact ID;
- registered time;
- `initial_batch_started_at` operational metadata when execution begins.

Operational start time is not part of immutable StudyRevision identity.

### `trials`

At minimum:

- `trial_id` primary key;
- `study_revision_id` foreign key;
- canonical instrument ID;
- continuous membership-episode start/end;
- canonical ordered membership-evidence representation or immutable reference;
- parameter/configuration identity;
- registration time;
- optional immutable bound ExperimentSpec ID;
- current Trial disposition;
- current-disposition timestamp;
- reused source identity where applicable;
- bounded current disposition/failure detail.

Current-disposition columns are a current projection and do not replace
historical events.

### `trial_disposition_events`

At minimum:

- immutable `event_id` primary key;
- `trial_id` foreign key;
- monotonically increasing Trial-local sequence number;
- previous disposition when applicable;
- new disposition;
- timestamp;
- causing ResearchJob ID when applicable;
- bounded reason/classification.

`UNIQUE(trial_id, sequence_number)` prevents ambiguous event ordering.

Trial disposition history is append-only.

### `research_jobs`

At minimum:

- `job_id` primary key;
- `trial_id` foreign key;
- ResearchJob state;
- creation time;
- claimed time;
- terminal time;
- worker/claim identity;
- cancellation-request time;
- linked new RunAttempt ID when applicable;
- successful completion kind;
- reused source references when applicable;
- bounded failure classification/message.

M9.4 does not initially introduce a separate `batch_jobs` table.

The registered StudyRevision plus its durable Trial/ResearchJob population is
the batch authority.

A separate batch entity should be introduced later only if a concrete
requirement proves that this model cannot represent the required lifecycle
truthfully.

## 29. Schema migration rules

Migration from research schema v1 to v2 must be:

- additive;
- transactional;
- fail-closed;
- covered by migration tests;
- non-destructive to existing evidence/artifacts/specs/attempts.

Existing:

- `research_evidence`;
- `research_artifacts`;
- `experiment_specs`;
- `run_attempts`

must not be rewritten merely to manufacture Study/Trial history.

Pre-M9.4 RunAttempts remain historical unregistered executions unless
a later registered Trial explicitly reuses them.

## 30. Application execution integration

M9.4 must not duplicate the Backtest engine.

The batch worker must reach the existing authoritative research/Backtest
execution through application/core composition.

A bounded refactor is permitted if required to expose reusable phases
such as:

- exact dataset/specification preparation;
- exact-evidence reuse lookup;
- new physical execution;
- coordinated terminalization.

That refactor must retain one authoritative financial execution path.

Canonical universe Trial execution must use explicit M9.3 canonical
instrument/provider/retrieval context.

The absence of an authoritative default provider-binding configuration
remains a real boundary.

M9.4 must fail clearly when required canonical provider truth is
unavailable.

It must not fall back to legacy ticker/token guessing.

Normal existing Backtest callers remain on their accepted behavior
unless they explicitly select the successor context.

## 31. API/frontend boundary

M9.4 owns the backend workflow necessary to validate:

- create/reopen Study;
- register StudyRevision;
- inspect registered Trials;
- start bounded batch execution;
- inspect progress;
- request cancellation;
- inspect individual dispositions/results;
- recover after restart.

Exact HTTP route design may be introduced in a separately reviewed
implementation slice.

M9.4 does not require the complete research-workspace frontend.

M9.8 owns complete frontend integration.

## 32. Behavioral traceability

Existing affected behavior IDs include:

- `RESEARCH-RULE-001` - tested research lineage is retained;
- `RESEARCH-RULE-003` - execution success and research success remain
  distinct;
- `RESEARCH-RULE-004` - independent universe accounts are not a
  portfolio;
- `RESEARCH-RULE-006` - universe quality/effective membership constrain
  claims;
- `RESEARCH-RULE-008` - retry identity does not inflate computation
  identity;
- `RESEARCH-RULE-009` - incomplete evidence cannot become accepted;
- `RESEARCH-RULE-010` - exact software identity gates exact execution;
- `RESEARCH-RULE-011` - canonical instrument/provider identity remain
  separate;
- `RESEARCH-RULE-012` - future universe membership cannot be applied
  backward.

Candidate new M9.4 behavior IDs are:

### RESEARCH-RULE-014

A registered Trial exists before new execution; reuse explicitly records
that the reused execution occurred earlier.

### RESEARCH-RULE-015

Trial identity, operational ResearchJob identity, ExperimentSpec identity,
RunAttempt identity and runtime/session identity remain distinct. Retries do
not inflate registered Trial count, and retryable disposition changes remain
append-only inspectable rather than rewriting earlier failure, cancellation or
interruption history.

### RESEARCH-RULE-016

A durable queued ResearchJob is claimed atomically by at most one worker
and cancellation/interruption state reflects what actually happened
rather than what was merely requested.

### RESEARCH-RULE-017

A registered StudyRevision has an immutable finite Trial population; material
research-plan changes create new revision lineage rather than silently
changing the denominator.

### RESEARCH-RULE-018

A universe snapshot transition does not reset an instrument's simulated
account while that instrument remains continuously eligible. Trial boundaries
follow maximal continuous membership episodes, while genuine membership gaps
create separate episodes.

These IDs must not be marked `VERIFIED` by documentation alone.

After design acceptance they must be synchronized into behavioral
traceability with `DESIGNED` status before or with their first
implementation slice.

## 33. Required implementation behavior declaration

Every later M9.4 behavior-changing implementation slice must declare
exactly one primary impact:

~~~text
BEHAVIOR IMPACT: NONE
~~~

or:

~~~text
BEHAVIOR IMPACT: ADDED
BEHAVIOR IDS: ...
BEHAVIOR BEFORE: ...
BEHAVIOR AFTER: ...
RATIONALE: ...
USER/RESEARCH IMPACT: ...
IMPLEMENTATION PATHS: ...
TEST/EVIDENCE: ...
UNCHANGED ADJACENT INVARIANTS: ...
~~~

Equivalent declarations apply to `CHANGED` or `REMOVED`.

## 34. Proposed implementation slicing after design acceptance

This design has now been explicitly reviewed and accepted. Production implementation remains blocked until the accepted baseline diff is reviewed and the baseline is staged and committed through the controlled workflow.

### M9.4a - Domain and additive persistence

Candidate scope:

- Study;
- StudyRevision;
- Trial;
- ResearchJob models;
- schema v2 migration;
- catalog persistence.

No scheduler yet.

### M9.4b - Registration and universe expansion

Candidate scope:

- canonical StudyRevision plan;
- StudyRevision plan artifact;
- deterministic universe/parameter expansion;
- atomic registration;
- immutable Trial denominator.

No financial execution changes.

### M9.4c - Durable queue and bounded worker claiming

Candidate scope:

- initial ResearchJob enqueue;
- bounded scheduler;
- atomic claim;
- duplicate-worker prevention;
- truthful progress.

No reuse/cancellation/recovery completion yet unless separately
reviewed.

### M9.4d - Execution, exact reuse and retry lineage

Candidate scope:

- authoritative Backtest/research composition;
- Trial-to-ExperimentSpec binding;
- new RunAttempt execution;
- exact compatible evidence reuse;
- retry accounting;
- coordinated terminalization.

### M9.4e - Cancellation and restart recovery

Candidate scope:

- queued cancellation;
- running cancellation requests;
- safe cancellation checkpoints;
- stale-job interruption;
- paired job/attempt recovery;
- restart validation.

### M9.4f - Aggregation, application integration and closure

Candidate scope:

- independent-account Study aggregation;
- explicit denominators;
- partial-failure reporting;
- backend workflow integration;
- behavioral trace verification;
- focused and complete regression;
- documentation synchronization.

The slicing may be revised during design review if a smaller safer
boundary is identified.

## 35. Validation requirements

M9.4 implementation is not complete until evidence covers at least:

1. Study identity persists across restart.
2. StudyRevision is immutable.
3. material plan change requires a new revision.
4. identical registration is idempotent.
5. pinned software revision cannot silently vary inside one StudyRevision.
6. all Trials are registered before any execution begins.
7. universe gaps/overlaps prevent partial registration.
8. effective-dated membership expands deterministically.
9. snapshot transition does not reset a continuously present instrument.
10. a true membership gap creates separate membership episodes.
11. each Trial retains exact ordered snapshot/subrange membership evidence.
12. retries do not create new Trials.
13. Trial and RunAttempt identities remain distinct.
14. prior retryable failures remain visible after later success.
15. Trial-disposition history is append-only and ordered.
16. queued work can exist before ExperimentSpec creation.
17. two workers cannot claim one queued job.
18. active jobs never exceed configured local worker bounds.
19. repeated initial batch start creates no duplicate jobs.
20. one failed Trial does not erase unrelated successful Trials.
21. queued cancellation creates no RunAttempt.
22. running cancellation is not reported effective before safe termination.
23. non-interruptible financial execution is not killed unsafely.
24. stale running jobs recover to `INTERRUPTED`.
25. queued jobs survive restart.
26. startup recovery does not silently resume computation.
27. explicit resume claims existing queued jobs without duplication.
28. interrupted work is not automatically retried.
29. terminal ResearchJobs are never reopened.
30. exact compatible evidence may be reused only after Trial registration.
31. reused pre-M9.4 evidence retains its original historical execution truth.
32. approximate/incomplete evidence cannot masquerade as exact reuse.
33. successful execution coordinates Trial/job/attempt/evidence terminal truth.
34. losing Trials remain visible.
35. invalid/insufficient/failed/cancelled/interrupted history remains
    inspectable.
36. progress denominator remains the complete registered Trial population.
37. retry may change current progress without erasing historical events.
38. aggregate metrics expose result-bearing and excluded denominators.
39. independent P&L is never presented as one portfolio P&L.
40. normal legacy Backtest behavior remains unchanged.
41. canonical batch execution never invents provider mappings.
42. accepted M4 Backtest financial regressions remain green.
43. accepted M9.2 catalog/evidence regressions remain green.
44. accepted M9.3 instrument/universe/dataset regressions remain green.
45. full Python regression remains green.
46. `git diff --check` passes.

## 36. Non-negotiable invariants

M9.4 must not:

- change accepted M4 financial semantics;
- change M5 WFA mathematics;
- change M6/M7 Paper causality;
- weaken M8 application authority;
- reinterpret M9.2 ExperimentSpec/RunAttempt/ResearchEvidence identities;
- weaken M9.3 canonical instrument/universe/dataset truth;
- treat provider token as canonical instrument identity;
- silently enable the successor path for legacy callers;
- hide failed or cancelled research work;
- convert negative-result Trials into missing history;
- present independent accounts as shared-capital portfolio economics;
- qualify strategies;
- claim profitability;
- implement real-money execution.

## 37. M9.4 completion boundary

M9.4 may be considered complete only when:

- the accepted design has been explicitly frozen;
- implementation occurred in separately reviewed slices;
- registered Studies/Revisions/Trials survive restart;
- the complete Trial population exists before execution;
- local resource use is bounded;
- queue claiming is duplicate-safe;
- cancellation/restart semantics are truthful;
- retries preserve Trial accounting;
- exact evidence reuse preserves historical truth;
- partial failure remains inspectable;
- progress uses explicit denominators;
- independent-account aggregation does not masquerade as a portfolio;
- accepted M0-M9.3 invariants remain green; and
- behavior, validation and authoritative documentation are synchronized.

Historical pre-implementation gate after explicit human design acceptance and before accepted-baseline staging/commit:

`M94_DESIGN_ACCEPTED=True`

`M94_PRODUCTION_MUTATION_AUTHORIZED=False`

## Human-reviewed M9.4 acceptance reconciliation

Review date: 2026-09-30

Human review status: ALL 24 M9.4 DECISIONS APPROVED IN SUBSTANCE.

Design-baseline status: ACCEPTED AND PUBLISHED at `9b7ab42`; authoritative baseline synchronization published at `199ec34`.

That pre-implementation authorization gate was satisfied before M9.4a began. Production implementation then proceeded through separately reviewed M9.4a-M9.4f slices under the accepted 24-decision baseline.

The following decisions are normative for the accepted M9.4 design baseline.

1. **Study identity.** A Study is the durable top-level identity of one research investigation. Kanasu assigns an opaque Study ID. Display metadata may change, but research execution details belong to immutable StudyRevisions. Research history is retained or archived rather than deleted merely because results are poor or no longer interesting.

2. **StudyRevision identity and revision triggers.** A StudyRevision is one immutable registered research plan. Material changes create a new revision, including research intent, strategy/procedure, timeframe, research period, universe/evidence, parameter search space, initial capital, risk/economic configuration, data treatment, evidence-reuse policy, and pinned executable software revision. Operational changes such as worker count, queue order, restart, and retry do not create a new revision. Identical registration is idempotent.

3. **Complete Trial pre-registration.** A StudyRevision must resolve and atomically register its complete finite Trial population before any Trial executes. Registration is all-or-nothing. The registered population is the fixed research denominator. M9.4 does not create new result-driven adaptive Trials inside an already registered revision.

4. **Trial identity.** A Trial is one deterministic pre-registered research test belonging to exactly one StudyRevision. Its identity includes the StudyRevision, canonical instrument, maximal continuous membership episode with exact universe evidence, and registered parameter/configuration variant. Trial identity is distinct from ResearchJob, ExperimentSpec, RunAttempt, runtime/session ID, and ResearchEvidence. Retries never create a new Trial. Once a Trial is bound to an exact ExperimentSpec, that binding is not silently replaced.

5. **ResearchJob authority.** ResearchJob is the durable operational queue/work identity for progressing one Trial. One Trial may have multiple ResearchJobs through explicit retries. A terminal ResearchJob is never reopened. A ResearchJob may exist before ExperimentSpec or RunAttempt exists. One ResearchJob creates at most one new RunAttempt. Successful completion distinguishes fresh EXECUTED computation from REUSED prior exact evidence.

6. **Separate, atomic, idempotent Start.** Registration and execution start are separate operations. Starting a StudyRevision atomically creates exactly one initial QUEUED ResearchJob for every eligible PENDING Trial that has never had an initial job. Repeating Start creates no duplicate Trials or jobs and does not retry failed, cancelled, or interrupted work. Retry is separate. Initial M9.4 does not use arbitrary selective scheduling as part of Start.

7. **Bounded local concurrency.** M9.4 uses a backend-controlled bounded local worker pool. `research_max_workers` is validated against a supported safety ceiling and is operational configuration, not research identity. Parallelism must not change Trial financial semantics or create shared-capital behavior. Initial M9.4 does not claim distributed multi-machine scheduling support.

8. **Atomic duplicate-safe queue claiming.** A ResearchJob is claimed through an atomic durable `QUEUED -> RUNNING` transition only when an actual bounded worker slot is available. Claim ownership/time metadata is recorded. At most one worker may claim a job. Queue order is deterministic FIFO with a stable job-ID tie-breaker. Initial M9.4 has no user priority system or result-driven queue ordering. Claiming alone does not create a RunAttempt.

9. **Strict exact-evidence reuse.** A registered Trial may reuse prior evidence only after its exact ExperimentSpec is established. Reuse requires the same ExperimentSpec, a successful prior RunAttempt, required accepted reproducibility evidence, and a verified immutable result artifact. Reuse creates no fake new RunAttempt and never rewrites historical registration timing. Pre-M9.4 executions may be reused but remain historically pre-M9.4 executions. StudyRevision freezes either `ALLOW_EXACT_ACCEPTED` or `FORCE_NEW_EXECUTION`.

10. **Explicit retry with append-only history.** Retry keeps the same Trial and creates a new ResearchJob. Initial ordinary retry is allowed only when current Trial disposition is FAILED, CANCELLED, or INTERRUPTED. Retry atomically returns the Trial to PENDING, appends a disposition event, and creates one new QUEUED ResearchJob. EXECUTED and REUSED are not ordinary retry candidates; INVALID and INSUFFICIENT are not silently reopened. Duplicate retry requests cannot create simultaneous retry jobs. A simple retry cannot silently change an already-bound ExperimentSpec.

11. **Truthful cancellation.** A QUEUED job may atomically become CANCELLED and cannot later be claimed. A RUNNING job is not force-killed; cancellation is durably requested and acted on at safe cooperative checkpoints. Until cancellation completes, the job remains RUNNING with cancellation-request metadata. If computation truthfully completes before cancellation takes effect, the successful result is retained and the cancellation request remains auditable. Terminal jobs are never retrospectively cancelled.

12. **Restart recovery separate from resume.** Existing QUEUED ResearchJobs remain queued after restart. Stale RUNNING work is reconciled against durable evidence and, absent a proven completed outcome, becomes INTERRUPTED with corresponding truthful Trial/RunAttempt history. Startup does not automatically resume queued work and does not create retries. Explicit RESUME processes already-existing queued jobs only; failed, cancelled, and interrupted Trials require explicit Retry.

13. **Fixed registered-Trial denominator.** The immutable registered Trial population is the authoritative research denominator. Trials remain in that denominator when losing, invalid, insufficient, failed, cancelled, interrupted, retried, or reused. Progress exposes explicit Trial-disposition counts rather than only a percentage. ResearchJob statistics are separate because retries can create more jobs than Trials. Financial summaries state the denominator to which each metric applies.

14. **Independent-account aggregation.** Study aggregation summarizes distributions and counts across independent Trial accounts. Per-Trial capital, positions, risk state, P&L, equity, and drawdown remain independent. Continuous membership across unrelated universe snapshot transitions preserves the same Trial/account episode; genuine membership gaps create separate episodes. M9.4 must not sum independent-account P&L/capital/equity and present it as shared-capital portfolio performance.

15. **Additive research schema v2.** M9.4 extends, rather than replaces, the M9.2 research catalog. Candidate schema v2 adds `studies`, `study_revisions`, `trials`, `trial_disposition_events`, and `research_jobs`, while preserving existing ExperimentSpec, RunAttempt, ResearchEvidence, ResearchArtifact, identities, timestamps, and history. Pre-M9.4 executions are not retroactively converted into registered Trials. Critical lineage relationships receive database constraints where practical. Initial M9.4 does not add a separate `batch_jobs` table.

16. **Failure/outcome classification.** Execution state, validity, financial result, and later research qualification remain separate dimensions. M9.4 distinguishes invalid input/data, insufficient history, deterministic compute failure, transient operational failure, cancellation, interruption, and explicit unknown/unclassified failures without guessing. A losing or zero-trade Backtest remains EXECUTED when the authoritative computation completed validly.

17. **Qualification remains outside M9.4.** M9.4 is an execution, lineage, and descriptive-evidence layer. It does not assign QUALIFIED, REJECTED, PROMISING, READY_FOR_PAPER, or equivalent research judgments. M9.5 owns versioned qualification/rejection/eligibility policy and Candidate progression. M9.4 completion means the registered workload was truthfully resolved, not that the strategy passed research standards.

18. **Authoritative Backtest financial semantics remain unchanged.** M9.4 owns orchestration, not financial computation. Fresh execution must use the established authoritative Backtest/application path and preserve existing timing, risk, position sizing, accounting, costs, P&L, equity, and drawdown semantics. M9.4 also preserves M9.3 canonical-instrument and dataset truth and never invents provider mappings or data assumptions. Any genuine financial-semantic change requires separate review.

19. **Research-only execution boundary.** M9.4 may access historical-data and Backtest capabilities but has no real broker-order placement, modification, or cancellation authority. Research configuration does not expose a `live=True`-style switch. M9.4 does not automatically launch Paper trading from research results. Qualification, WFA/OOS, persistent Paper progression, and all real-money execution remain later explicit stages; real money remains V2 scope.

20. **Implementation order M9.4a through M9.4f.** Implementation proceeds in dependency order: M9.4a domain models/additive persistence; M9.4b registration/universe expansion; M9.4c durable queue/bounded worker claiming; M9.4d authoritative execution/exact reuse/retry lineage; M9.4e cancellation/restart recovery; M9.4f aggregation/application integration/closure. Each slice is independently reviewed and validated before the next. M9.4 application integration means an authoritative backend workflow, not expansion into the later research-workspace/frontend milestone.

21. **Mandatory behavior-impact declaration.** Every M9.4 implementation slice declares `BEHAVIOR IMPACT: NONE`, `ADDED`, `CHANGED`, or `REMOVED`, plus affected rule/invariant IDs, before/after behavior, rationale, affected paths, tests/evidence, and adjacent invariants that must remain preserved. If an established M0-M9.3 behavior genuinely needs modification, implementation stops for separate review rather than silently incorporating the change.

22. **Partial-failure isolation with fail-closed persistence authority.** An ordinary Trial or ResearchJob failure does not automatically abort unrelated Trials. Independent work continues and all dispositions remain visible. If authoritative research persistence or reconciliation becomes unreliable, Kanasu stops claiming new ResearchJobs and fails closed rather than executing work whose durable lineage cannot be guaranteed. Initial M9.4 has no heuristic whole-batch abort rule based merely on observing several ordinary Trial failures.

23. **Backend-controlled Trial-population safety bound.** Before registration commits, M9.4 fully resolves and counts the finite Trial population and compares it with a validated backend-controlled `research_max_trials_per_revision` bound. Exceeding the bound rejects registration atomically with zero Trials registered and reports the calculated workload. Kanasu never silently samples or truncates the Trial population. The safety bound is operational configuration, not StudyRevision/Trial identity. Its initial numeric value will be selected and explicitly reviewed during implementation using measured resource evidence.

24. **M9.4 closure evidence standard.** M9.4 is not DONE merely because implementation exists. Closure requires reviewed evidence covering persistence/restart survival; deterministic and duplicate-safe registration; universe membership continuity and true-gap splitting; idempotent Start; bounded duplicate-safe claiming; authoritative Backtest parity; positive and negative exact-reuse cases; preservation of pre-M9.4 history; retry lineage; queued and running cancellation; mixed-state restart recovery; partial-failure isolation and fail-closed persistence behavior; fixed denominators; independent-account reporting; truthful failure classification; absence of M9.4 qualification and live-order authority; full regression preservation; and an inspectable durable lineage from Study through result evidence/artifact.

These 24 decisions constitute the human-reviewed accepted M9.4 design baseline. They remain normative and are not rewritten by the implementation/closure evidence below.


## M9.4 implementation and closure evidence

BEHAVIOR IMPACT: ADDED across M9.4a-M9.4f. The slices implement the already accepted registered-research workflow without changing accepted M4 financial semantics, M5 WFA mathematics, M6/M7 Paper causality, M8 application authority, M9.2 evidence identity or M9.3 canonical instrument/universe/dataset truth.

Published implementation chain:

- accepted design baseline: `9b7ab42`;
- authoritative accepted-design synchronization: `199ec34`;
- M9.4a registered Study persistence foundation: `6a68d0a`;
- M9.4b deterministic finite StudyRevision/Trial registration: `d3abbfc`;
- M9.4c durable ResearchJob queue: `8d2e572`;
- execution-preparation refactor preserving Backtest authority: `610916a`;
- actual bounded worker-slot enforcement: `0de1ab8`;
- atomic Trial/RunAttempt binding: `28f60e8`;
- M9.4d execution, exact reuse and retry lineage: `6116863`;
- M9.4e cancellation and restart recovery: `878e929`;
- M9.4f published at `b93ae6a`: truthful progress/read models, independent-account Study aggregation, backend workflow/API integration and closure synchronization.

Historical M9.4f closure validation:

- M9.4-wide regression: 154 passed;
- M4 financial + accepted M9.2 + accepted M9.3 + M9.4 + startup-recovery preservation matrix: 682 passed;
- complete Python regression: 1250 passed in 18.93s;
- `git diff --check`: passed;
- no files staged at the validation checkpoint.

The current backend HTTP workflow supports Study creation/reopen, complete StudyRevision registration, Trial/progress/aggregation/lineage reads, Start and cancellation. Start initializes the durable bounded queue; it does not expose a guessed production execution-input resolver. Actual queue draining remains composed through the application service with an explicit execution handler because M9.4 must not manufacture canonical instrument/provider/data mappings that M9.3 does not supply.

Independent-account aggregation reports result-bearing/excluded denominators and per-Trial account-return/drawdown distributions. It does not sum independent capital, P&L, equity or drawdown into shared-capital portfolio economics.

M9.4 remains an execution, lineage and descriptive-evidence layer. It does not qualify strategies, promote Candidates, launch qualified Paper campaigns or place real broker orders.

Historical M9.4f closure status: DONE/CLOSED. Human review of the complete candidate diff, controlled staging, commit and push completed successfully for M9.4f at `b93ae6a`. M9.4g later superseded that closure evidence, and M9.4h now governs current corrective status after the post-remediation audit challenged the M9.4g re-closure.

## M9.4g independent-audit remediation and re-closure evidence

The historical M9.4a-M9.4f commit identities and their validation counts above
remain historical facts. They are not rewritten.

A later independent post-closure audit demonstrated that additional bounded
correction and closure proof were required. The accepted remediation design is
`docs/design/M9_4G_INDEPENDENT_AUDIT_REMEDIATION.md`.

M9.4g preserves the 24 accepted M9.4 decisions and specifically verifies the
previously missing closure scenarios:

- mixed-state restart with QUEUED, RUNNING, EXECUTED, REUSED, FAILED and
  CANCELLED work represented simultaneously;
- cancellation requested during already-running financial computation;
- recovery persistence failure with transaction rollback and fail-closed
  startup refusal;
- retry after recovered interrupted bound work while preserving Trial,
  ExperimentSpec and prior attempt history;
- real ASGI persistence through the actual HTTP/application boundary; and
- representative measurement of the configured Trial-population safety bound.

The representative D18 workload used one membership episode and 5,000 distinct
parameter variants through production registration code. On the recorded local
environment (Windows 10 AMD64, Python 3.11.9, SQLite 3.45.1, repository head
`a32e22d5b59bc625595d0c0ff3e6036a5e4ac527`) it registered and persisted all
5,000 Trials in 10.837931 seconds with 11.857 MiB traced peak Python memory,
6.855 MiB SQLite storage and 1.104 MiB content-addressed artifacts.

The 5,000 value therefore remains the reviewed backend safety ceiling for the
current single-user local implementation. This evidence is not a throughput
SLA, latency guarantee or distributed-capacity claim. Changing the limit still
requires explicit review and does not change StudyRevision or Trial identity.

Historical M9.4g D20 automated validation passed 64 focused tests, 222 M9.4-wide tests, 757 cross-milestone preservation tests and 1325 complete Python tests with `git diff --check` clean. Final human review, separately approved stage/commit/push and post-push verification also passed, and the candidate was published at `68df76b`. A subsequent independent post-remediation audit nevertheless returned `M95_GATE=BLOCKED`; therefore that re-closure remains a historical fact rather than current gate proof.

## M9.4h post-remediation corrective evidence

M9.4h preserves the accepted 24-decision design baseline and corrects the residual N01-N07 findings. N01-N04 are published at `d1efd238`: stable execution snapshots/final semantic binding, executable procedure authority, mandatory successor reuse dataset lineage and fail-closed authoritative error propagation. N05-N06 are published at `524b9dda`: durable atomic complete-population proof required by Start and semantic FIFO chronology across timezone offsets with exact microsecond ordering and stable job-ID tie-breaking.

Current corrective validation consists of 144 focused h1+h2 tests, 66 focused h3 tests, 172 M9.4-wide tests, 1342 cross-milestone preservation tests and 1342 complete Python tests, with `git diff --check` clean. N07 synchronizes authoritative closure/traceability documentation. M9.4h is a corrective re-closure candidate; the independent re-review has not yet returned PASS and M9.5 remains blocked.
The independent post-remediation M9.4 audit remains required before M9.5
implementation.
