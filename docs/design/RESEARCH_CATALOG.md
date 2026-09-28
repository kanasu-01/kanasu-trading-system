# M9.2 â€” Durable Research Catalog and Automatic Evidence

## Status

**DONE/CLOSED at accepted implementation/validation scope**

M9.2 builds the durable execution/evidence substrate required by later
M9 research workflows.

It reuses the accepted historical-data, Backtest, reproducibility,
risk/accounting and application contracts. It does not reopen their
validated financial semantics.

Starting baseline:

- branch: `m9-v1-research-platform`;
- parent baseline: `c8cdcbe042a5f2af528859218927bcd8d4e971d5`;
- focused research/API regression: 111 passed;
- full Python regression: 792 passed;
- `git diff --check`: passed.

Implementation and closure evidence:

- design baseline: `4eb28d8` - `Baseline M9.2 durable research catalog design`;
- M9.2a: `07f4be1` - durable research catalog schema;
- M9.2b: `24cdf67` - immutable research artifact persistence;
- M9.2c: `ba2129f` - research experiment lifecycle;
- M9.2d: `d21c204` - canonical Backtest result serialization;
- M9.2e: `0f4cc98` - automatic Backtest research evidence;
- M9.2f: `4b44050` - terminal research recovery;
- final committed-head focused validation: 198 passed in 8.19s;
- final committed-head full Python regression: 897 passed in 8.80s;
- final `git diff --check`: passed;
- local and remote branch heads synchronized at `4b44050b46ab4dfa6d5b5729b7876231c50671bf`.

## 1. Purpose

The current application can run an authoritative Backtest, and Kanasu
already has deterministic dataset/configuration/result fingerprints,
`BacktestRunManifest`, immutable `ResearchEvidence`, and dedicated
SQLite evidence persistence.

Before M9.2, application-owned durable execution lineage was missing.

A successful `/api/backtest/run` request returned an authoritative
result to the caller without automatically preserving the exact
manifest, result artifact, execution attempt and reproducibility
evidence as one durable research record.

M9.2 closes that bounded gap through the implemented catalog,
artifact, orchestration, automatic-evidence and restart-recovery
boundaries.

## 2. Scope

M9.2 owns:

- durable research-catalog persistence;
- immutable research artifacts;
- immutable `ExperimentSpec` identity;
- durable `RunAttempt` identity and execution state;
- automatic Backtest reproducibility evidence;
- restart handling for stale non-terminal attempts;
- retrieval/query primitives needed by later M9 milestones;
- application-level linkage between a Backtest response and its durable
  research attempt/evidence identity.

M9.2 does not own:

- `Study`, `StudyRevision` or registered `Trial` workflow;
- universe definition/snapshot or universe-quality semantics;
- batch research execution;
- qualification policy or qualification decisions;
- Candidate or CandidateRevision progression;
- WFA application workflow;
- PaperCampaign persistence;
- research-workspace frontend integration;
- real-money execution;
- changes to accepted M4 Backtest timing, fills, costs, sizing,
  accounting, drawdown or terminal-position semantics.

Those remain assigned to later M9 milestones.

## 3. Existing contracts that remain authoritative

M9.2 reuses rather than replaces:

- `kanasu.dataset.v1`;
- `kanasu.backtest-config.v2`;
- `kanasu.backtest-run-manifest.v1`;
- `kanasu.backtest-result.v1`;
- `BacktestRunManifest`;
- `dataset_fingerprint(...)`;
- `backtest_configuration_fingerprint_v2(...)`;
- `stable_backtest_result_fingerprint(...)`;
- immutable `ResearchEvidence`;
- `ResearchEvidenceStatus`;
- the existing `research_evidence` SQLite schema;
- historical-source retrieval and coverage semantics;
- authoritative `BacktestEngine` financial output.

`ResearchEvidenceStatus.ACCEPTED` continues to mean only that the
reproducibility-evidence contract is complete. It does not mean the
strategy is economically, statistically, OOS or Paper qualified.

## 4. Storage boundary

The default M9 research metadata database is:

`data/research.sqlite3`

The default immutable-artifact root is:

`data/research_artifacts/`

Both paths are application configuration and may be overridden through
the composition boundary.

They remain separate from:

`data/historical.sqlite3`

Historical storage continues to own candles and retrieval coverage only.

The research SQLite database owns:

- research-catalog metadata;
- ExperimentSpec records;
- RunAttempt records;
- artifact metadata;
- immutable `ResearchEvidence`.

Potentially large immutable payloads such as complete Backtest results
are stored as content-addressed files beneath the research-artifact
root rather than as SQLite BLOB values. This keeps the catalog usable
when later M9 universe/batch workflows generate substantially more
evidence.

The existing `research_evidence` table remains backward-compatible and
may coexist with the new catalog tables in the research database.

Existing `ResearchEvidence.artifact_references` values remain valid.
M9.2 must not reinterpret or destructively rewrite historical path-like
artifact references.

### Research schema versioning

M9.2 establishes an explicit SQLite research-schema version.

A legacy evidence-only research database with no M9 catalog version is
upgraded only by additive/non-destructive migration. Existing evidence
rows must remain byte-for-byte logically equivalent after reopening.

Schema migration occurs transactionally.

A database with a schema version newer than the running application
understands fails closed rather than attempting an unsafe downgrade or
silent reinterpretation.

## 5. Artifact contract

M9.2 introduces immutable, content-addressed research artifacts.

Initial artifact kinds are:

- `BACKTEST_RUN_MANIFEST`;
- `BACKTEST_RESULT`.

Artifact payload bytes are stored beneath the configured artifact root.
SQLite stores the catalog metadata required to resolve them.

Each artifact metadata record contains at minimum:

- SHA-256 artifact ID;
- artifact kind;
- schema identifier;
- deterministic relative storage location;
- byte count;
- creation timestamp.

The artifact ID is:

`sha256:<64 lowercase hexadecimal>`

and is calculated over the exact persisted bytes.

New automatic evidence uses stable logical references of the form:

`artifact:sha256:<64 lowercase hexadecimal>`

Absolute machine-specific paths are not written into new evidence.

Artifact writes use a temporary file followed by an atomic final-name
operation within the artifact filesystem. The final bytes are hashed
and verified before catalog metadata is allowed to reference them.

An existing artifact ID is idempotently reusable only when the existing
bytes produce the same hash. Different bytes can never overwrite an
existing content identity.

A crash may leave an unreferenced content-addressed artifact file.
That is safe orphaned storage and must not be represented as completed
research lineage.

The manifest artifact uses the existing
`backtest_run_manifest_bytes(...)` canonical serialization.

M9.2 introduces an equivalent public canonical Backtest-result byte
serialization derived from the exact payload already used by
`stable_backtest_result_fingerprint(...)`.

For Backtest result artifacts, the artifact ID therefore equals the
existing stable result fingerprint. M9.2 does not establish a second
result-identity domain.

## 6. ExperimentSpec contract

`ExperimentSpec` is the immutable deterministic computation definition
for one exact Backtest input under one identified executable software
revision.

For the M9.2 Backtest scope it records:

- computation kind: `BACKTEST`;
- manifest artifact identity;
- dataset fingerprint;
- configuration fingerprint;
- repository/software revision;
- creation timestamp as catalog metadata.

Its deterministic identity uses the new versioned schema:

`kanasu.experiment-spec.v1`

The deterministic fingerprint includes:

- computation kind;
- manifest artifact identity;
- dataset fingerprint;
- configuration fingerprint;
- repository/software revision.

Creation timestamp is catalog metadata and is explicitly excluded from
the deterministic ExperimentSpec fingerprint.

Therefore:

- the same exact effective inputs under the same executable revision
  resolve to the same ExperimentSpec;
- a different canonical dataset changes the spec;
- a different effective configuration changes the spec;
- a different executable software revision changes the spec;
- result identity is not part of the spec because the result is an
  output rather than an input.

An ExperimentSpec is immutable after creation.

Repository revision does not become part of the existing
`kanasu.backtest-config.v2` identity. M9.2 preserves the accepted
distinction between effective Backtest configuration identity and
software/execution provenance.

## 7. RunAttempt contract

A `RunAttempt` is one physical execution of one established
ExperimentSpec.

Every retry receives a new attempt ID even when it references the same
ExperimentSpec.

The accepted M9 execution-state vocabulary remains:

- `QUEUED`;
- `RUNNING`;
- `SUCCEEDED`;
- `FAILED`;
- `CANCELLED`;
- `INTERRUPTED`.

The synchronous M9.2 Backtest path normally creates an attempt directly
as `RUNNING` after its ExperimentSpec has been established.

`QUEUED` and user-driven `CANCELLED` behavior are not claimed as
implemented merely because the shared vocabulary contains those values.
M9.4 owns bounded queued/batch execution and cancellation semantics.

A RunAttempt records at minimum:

- attempt ID;
- ExperimentSpec ID;
- execution state;
- created/start timestamp;
- terminal timestamp when applicable;
- authoritative runtime/session run ID when one was produced;
- result artifact reference when available;
- ResearchEvidence ID when available;
- bounded failure classification/message when applicable.

The existing Backtest `session_id` therefore remains physical runtime
identity. It is not silently redefined as ExperimentSpec, RunAttempt or
ResearchEvidence identity.

Terminal attempts are not reopened or overwritten.

A retry creates another RunAttempt.

M9.2 does not treat retries as additional research Trials. Registered
Trial/search accounting is introduced in M9.4.

## 8. Pre-specification failures and pre-M9.4 execution

Exact ExperimentSpec identity cannot exist until the canonical dataset
has been retrieved and fingerprinted.

If execution fails before exact dataset/spec identity can be
established, M9.2 must not fabricate an ExperimentSpec or RunAttempt
for a computation specification that never became knowable.

The application may persist `INCOMPLETE` ResearchEvidence containing
the dataset context, requested range and available provenance/failure
information.

Before M9.4, automatic application Backtests are durable catalog
executions but are not represented as pre-registered Trials.

M9.4 may permit a later registered Trial to explicitly reference
pre-existing evidence as reused evidence where its contract allows it,
but it may not rewrite history and claim that an earlier unregistered
execution was registered before execution.

This preserves the M9.1 rule that research search/trial accounting must
be truthful about when registration occurred.

## 9. Automatic Backtest evidence flow

The accepted M9.2 Backtest flow is:

~~~text
validated Backtest request
        |
        v
resolve effective Backtest configuration,
DatasetContext and RuntimeContext
        |
        v
retrieve canonical historical candles ONCE
        |
        +-- failure before exact dataset identity
        |       -> persist INCOMPLETE evidence when possible
        |       -> no fabricated ExperimentSpec
        |       -> return operational failure
        |
        v
compute dataset fingerprint
        |
        v
build BacktestRunManifest BEFORE financial execution
        |
        v
serialize/persist immutable manifest artifact
        |
        v
compute effective configuration fingerprint
        |
        v
resolve immutable ExperimentSpec
        |
        v
create distinct RUNNING RunAttempt
        |
        v
execute authoritative BacktestEngine using the exact
already-retrieved/fingerprinted candle sequence
        |
        +-- execution failure
        |       -> persist non-ACCEPTED evidence
        |       -> mark attempt FAILED
        |       -> no fabricated result fingerprint
        |
        v
BacktestResult produced
        |
        v
compute stable result fingerprint
        |
        v
persist immutable result artifact
        |
        v
persist ACCEPTED ResearchEvidence
        |
        v
mark RunAttempt SUCCEEDED
        |
        v
return authoritative Backtest response linked to
attempt/evidence identity
~~~

The candle sequence used for dataset identity and the candle sequence
consumed by the Backtest engine must be the same canonical sequence.

The application must not retrieve historical data a second time merely
to create evidence.

## 10. Runtime refactor boundary

M9.2 may refactor `core/runtime/backtest_runtime.py` so canonical
historical retrieval and canonical candle execution are separately
testable operations.

The existing public `execute_backtest(...)` behavior remains
compatible.

The intended composition is conceptually:

~~~text
retrieve canonical candles
        |
        +-> fingerprint/manifest/catalog preparation
        |
        +-> authoritative engine execution of those same candles
~~~

There must not be a second Backtest financial implementation inside the
research catalog.

The refactor must prove that the legacy `execute_backtest(...)` path
and the catalog-aware composition use the same authoritative engine
semantics.

## 11. Repository/software revision

Automatic accepted research evidence requires an exact executable
software identity.

For the repository-backed V1 development/application environment,
M9.2 resolves software identity through an injected composition
boundary that reports at minimum:

- repository revision;
- whether the executable worktree is clean.

Tests inject a fixed software-identity provider and must not depend on
the test runner's actual Git state.

`ResearchEvidence.repository_revision` continues to carry the accepted
revision string without changing the existing logical model.

A clean worktree at an identified revision may produce
`ResearchEvidenceStatus.ACCEPTED` when all other evidence requirements
are satisfied.

If the application is executing source that differs from the claimed
repository revision, or an exact required software revision cannot be
established, computation may still complete, but its automatically
created evidence cannot be labelled `ACCEPTED`.

In that case M9.2 must not fabricate an ExperimentSpec or RunAttempt. The financial Backtest may still compute and return a result, with `INCOMPLETE` ResearchEvidence persisted when possible. A `SUCCEEDED` RunAttempt with `INCOMPLETE` ResearchEvidence is permitted only when the exact ExperimentSpec had already been established and a different evidence requirement became incomplete after attempt creation.

This is an intentional example of M9's separation between execution
success and evidence completeness.

A later packaged/deployed build may provide another separately
validated immutable build identity. M9.2 does not silently substitute
a dirty Git HEAD for exact software identity.

## 12. Transaction and crash semantics

Catalog persistence must preserve truthful terminal state.

Artifact-file creation happens before a database record is allowed to
reference the artifact:

~~~text
write temporary artifact
        |
        v
verify exact bytes/hash
        |
        v
atomically install content-addressed final file
        |
        v
register/reference artifact in SQLite transaction
~~~

An artifact file left behind before catalog registration is an
unreferenced orphan and does not itself establish research completion.

For successful attempt terminalization, the research database performs
one transaction that coordinates:

- required artifact metadata references;
- immutable ResearchEvidence insertion;
- RunAttempt result/evidence linkage;
- RunAttempt transition to `SUCCEEDED`.

For an execution failure after an ExperimentSpec exists, one database
transaction coordinates the non-ACCEPTED evidence record and terminal
`FAILED` attempt state where persistence itself remains available.

The existing public `SQLiteResearchEvidenceStore` behavior remains
compatible. Internal persistence may be refactored so the same
`research_evidence` insert contract can participate in the catalog's
transaction rather than duplicating evidence semantics.

If the terminal database transaction does not commit, the application
must not return a response claiming a completed durable research
record.

On application startup, an M9.2-owned `RUNNING` attempt left behind
without a committed terminal transaction is classified `INTERRUPTED`.

Because accepted evidence and successful attempt terminalization are
committed together, recovery must not create the contradictory state
"accepted terminal evidence + stale RUNNING attempt".

M9.2 does not claim multi-process distributed-worker coordination.
The accepted envelope remains the single-user local V1 application.

## 13. Result durability

A stable result fingerprint alone is not treated as the durable result.

Successful M9.2 Backtest evidence stores the canonical stable Backtest
result bytes as an immutable artifact in addition to recording the
existing result fingerprint.

The result artifact uses the exact canonical payload underlying
`stable_backtest_result_fingerprint(...)`. Its content-addressed
artifact ID is therefore the same SHA-256 identity as that existing
result fingerprint.

The stable result artifact intentionally excludes execution/session ID,
matching the accepted reproducibility contract.

The physical Backtest `session_id` is retained separately on the
RunAttempt as runtime execution identity.

Therefore equivalent deterministic retries may share one immutable
result artifact while retaining distinct RunAttempt IDs and distinct
runtime/session IDs.

The persisted artifact represents the existing authoritative financial
Backtest result. M9.2 does not create a competing financial-accounting
result model.

Presentation-specific frontend state is not part of the canonical
result artifact.

## 14. API boundary

The existing Backtest request and authoritative financial fields remain
compatible.

A successful application Backtest additionally exposes durable
research identity sufficient to correlate the returned computation
with its catalog record:

- RunAttempt ID;
- ResearchEvidence ID;
- ResearchEvidence status.

The existing Backtest `run_id` remains execution/session identity and
must not be silently redefined as research identity.

A financially successful computation with `INCOMPLETE` reproducibility
evidence may still report the authoritative financial result, but the
evidence status must remain visible and must not be represented as
accepted research evidence.

If the application cannot durably commit the catalog terminalization
required for the response, it returns an operational application error
rather than claiming a completed durable research record.

M9.2 does not require the full research-workspace frontend. Later
milestones own catalog browsing, Study workflow and complete research
UX.

## 15. Failure semantics

M9.2 keeps the following concepts distinct:

- HTTP/request validation failure;
- historical-data acquisition/coverage failure;
- deterministic Backtest execution failure;
- interrupted process/runtime attempt;
- incomplete reproducibility evidence;
- accepted reproducibility evidence;
- future research qualification rejection.

A failure to produce complete evidence cannot be represented as
`ResearchEvidenceStatus.ACCEPTED`.

A successful computation is not automatically a successful research
decision.

## 16. Behavioral impact

Primary declaration for implementation:

`BEHAVIOR IMPACT: ADDED`

Proposed affected behavior IDs:

- `RESEARCH-FLOW-001` â€” application Backtests automatically create
  durable research execution/evidence lineage;
- `RESEARCH-RULE-007` â€” exact fingerprinted Backtest input is the exact
  input consumed by authoritative execution;
- `RESEARCH-RULE-008` â€” retries preserve one immutable specification
  while receiving distinct attempt identities;
- `RESEARCH-RULE-009` â€” incomplete or failed evidence cannot be
  presented as accepted reproducibility evidence;
- `RESEARCH-RULE-010` â€” accepted automatic evidence requires exact
  executable software identity rather than a dirty or unknown source
  revision.

Adjacent invariants that must remain unchanged:

- `DATA-RULE-001`;
- `DATA-RULE-002`;
- `BT-RULE-001`;
- `BT-RULE-002`;
- `WFA-RULE-001`;
- `PAPER-RULE-001`;
- `PAPER-RULE-002`;
- `SAFETY-RULE-001`;
- `RESEARCH-RULE-002`;
- `RESEARCH-RULE-003`.

## 17. Validation gates

M9.2 implementation is not accepted until deterministic tests prove:

1. an existing evidence-only research database upgrades
   non-destructively and its ResearchEvidence rows remain readable;
2. an unknown newer research-schema version fails closed;
3. historical candle storage remains separate from research catalog
   storage;
4. identical artifact bytes resolve to one immutable content identity;
5. conflicting bytes cannot overwrite an existing artifact identity;
6. new artifact references are machine-independent logical references;
7. the canonical Backtest result artifact identity equals the existing
   stable result fingerprint;
8. equivalent exact Backtest specifications under the same executable
   revision reuse ExperimentSpec identity;
9. changes to effective data, configuration or executable revision
   change ExperimentSpec identity as applicable;
10. ExperimentSpec creation timestamp does not change deterministic
    identity;
11. retries receive different RunAttempt identities while retaining the
    same ExperimentSpec when applicable;
12. runtime/session ID remains distinct from RunAttempt and
    ExperimentSpec identity;
13. a successful application Backtest automatically persists manifest,
    result, ExperimentSpec, RunAttempt and ResearchEvidence;
14. persisted dataset/configuration/result fingerprints match the
    accepted existing reproducibility functions;
15. the candles fingerprinted are exactly the candles executed by the
    authoritative Backtest engine;
16. historical data is not fetched a second time for evidence creation;
17. execution failure cannot produce false ACCEPTED evidence;
18. pre-specification failure cannot fabricate ExperimentSpec or
    RunAttempt identity;
19. a dirty or unknown software revision cannot produce automatically
    ACCEPTED reproducibility evidence;
20. computation success with incomplete software identity keeps
    execution success distinct from evidence completeness;
21. stale non-terminal attempts are recovered as INTERRUPTED;
22. accepted evidence and successful RunAttempt terminalization cannot
    commit independently;
23. durable records survive fresh store/application instances;
24. pre-M9.4 catalog execution is not misrepresented as a
    pre-registered Trial;
25. existing Backtest HTTP financial output remains authoritative;
26. accepted M3/M4 reproducibility and Backtest-validity regressions
    remain green;
27. the complete Python regression remains green; and
28. `git diff --check` passes.

## 18. Implementation slicing

The implementation should proceed in bounded slices:

~~~text
M9.2a  research DB schema/versioning + catalog models
M9.2b  content-addressed immutable artifact persistence
M9.2c  ExperimentSpec + RunAttempt lifecycle
M9.2d  Backtest canonical-result serialization + runtime input refactor
M9.2e  automatic Backtest evidence/application integration
M9.2f  terminal transaction + restart/recovery validation
M9.2g  behavior/documentation synchronization and closure
~~~

Each slice requires focused tests before the next slice begins.

M9.2 implementation should introduce a reusable research orchestration
service beneath the API rather than placing catalog semantics directly
inside the FastAPI route. M9.4 can then reuse the same execution/evidence
substrate for registered Study/Trial workflows.

## 19. Explicit non-goals

M9.2 does not establish:

- strategy profitability;
- qualification eligibility;
- WFA/OOS acceptance;
- shared-capital portfolio research;
- universe membership truth;
- survivorship-bias claims;
- Paper qualification;
- real-money execution;
- distributed jobs;
- remote workers;
- multi-user authorization;
- cloud research storage.

Those require their separately accepted milestone contracts.
