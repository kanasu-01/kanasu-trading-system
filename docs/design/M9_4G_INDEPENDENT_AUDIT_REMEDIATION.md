# M9.4g - Independent Audit Remediation and Re-closure

## Status

**HISTORICAL ACCEPTED REMEDIATION RECORD - M9.4g1-M9.4g4 IMPLEMENTED / VALIDATED / PUBLISHED; LATER RECLOSURE CHALLENGED BY M9.4h AUDIT**

`M94G_DESIGN_ACCEPTED=True`

`M94G_PRODUCTION_MUTATION_AUTHORIZED=True`

`M94G_RECLOSURE_COMPLETE=True`


Current-status note (2026-10-05): `M94G_RECLOSURE_COMPLETE=True` records
the historical M9.4g D20 outcome. A later independent post-remediation
audit returned `M95_GATE=BLOCKED` and established residual findings
N01-N07. Current closure status is therefore governed by
`M9_4H_POST_REMEDIATION_AUDIT_CORRECTIONS.md`; this document remains the
historical M9.4g design/evidence record and is not rewritten as though
that later audit passed.

Human acceptance recorded: 2026-10-03.

Accepted baseline source: independent post-closure M9.4 audit remediation
design reviewed through `M9.2_880`.

BEHAVIOR IMPACT: NONE

This document is a design/reconciliation artifact only. It does not
change runtime behavior.

## 1. Purpose

M9.4 was previously published as DONE/CLOSED through the implementation
and closure sequence ending at:

- M9.4f implementation: `b93ae6a`
- closure documentation: `e85e92f`
- M9.5 planning handoff: `f199e3a`

A subsequent independent post-closure audit at `f199e3a` reproduced and
identified integrity defects and missing closure evidence that were not
caught by the existing 1,250-test regression suite.

M9.4g is a bounded corrective milestone.

Its purpose is to repair those independently established defects,
complete the missing validation evidence, synchronize authoritative
documentation, and re-establish the M9.4 closure claim before M9.5
qualification implementation relies on M9.4 evidence.

M9.4g does not redesign the research platform and does not replace the
accepted M9.4 design baseline.

## 2. Authoritative baseline

Repository:

`kanasu-01/kanasu-trading-system`

Branch:

`m9-v1-research-platform`

M9.4 accepted design baseline:

`9b7ab42ca729f5c675cd84ebe3b9ec3b17a91a92`

Post-closure audit baseline:

`f199e3a8967db9ac64b164c06ed1deffb4a3f82f`

The 24 accepted M9.4 decisions remain normative.

M9.4g may correct implementation that fails those decisions. It must not
silently rewrite those decisions to make an implementation defect appear
acceptable.

## 3. Independent audit evidence

The independent review:

- verified branch and audited HEAD;
- observed a clean repository;
- independently ran the complete Python test suite;
- reported `1250 passed`;
- reported 154 tests in M9.4-named test files;
- reproduced several defects using production code paths;
- found no need to replace the authoritative Backtest engine;
- found substantial evidence supporting the bounded worker model,
  atomic queue claiming, retry transaction, coordinated terminalization,
  cooperative cancellation and restart-recovery foundation.

Passing tests are retained as regression evidence, but are not treated as
proof against independently reproduced correctness defects.

## 4. Audit finding disposition

### F01 - Prepared identity can differ from executed inputs

Disposition: ACCEPTED BLOCKER.

A prepared exact research identity must not describe one computation
while execution uses different strategy/configuration/runtime/dataset or
candle inputs.

Must be corrected before M9.5 qualification implementation.

### F02 - Registered declarations are not bound to actual executable semantics

Disposition: ACCEPTED BLOCKER.

Resolver-supplied declaration dictionaries are not sufficient proof that
the executable RuntimeContext/configuration/data treatment implements the
registered StudyRevision contract.

Must be corrected before M9.5 qualification implementation.

### F03 - Exact reuse omits successor canonical dataset compatibility

Disposition: ACCEPTED BLOCKER.

Registered exact reuse must preserve M9.3 canonical instrument and
dataset-treatment truth in addition to legacy ExperimentSpec identity.

Must be corrected before M9.5 qualification implementation.

### F04 - Authoritative preparation persistence failures can permit later claims

Disposition: ACCEPTED BLOCKER.

Failure of authoritative research persistence or reconciliation must
propagate to the worker-pool fail-closed boundary rather than be reduced
to an ordinary independent Trial failure.

Must be corrected before M9.5 qualification implementation.

### F05 - Incremental persistence APIs can bypass population/queue authority

Disposition: ACCEPTED CONTRACT DEFECT.

No supported persistence API may allow a caller to mutate the frozen
registered Trial denominator or bypass authoritative Start/retry job
creation.

Must be corrected before M9.5 introduces additional callers.

### F06 - Mixed-offset repeat registration can lose idempotence

Disposition: ACCEPTED CORRECTION.

Equivalent aware timestamps with different offsets must not cause an
unchanged StudyRevision registration to appear to have a different Trial
population.

This correction is grouped with M9.4g2 because it is adjacent to
population authority and identity comparison.

### F07 - Aggregation accepts semantically malformed result payloads

Disposition: ACCEPTED BLOCKER.

A content hash, schema label and top-level list shape do not by
themselves prove a canonical Backtest result is semantically valid.

M9.5 qualification must not consume such evidence.

### F08 - Failure reporting does not implement accepted cause distinctions

Disposition: ACCEPTED BLOCKER.

Execution phase and failure cause are separate concepts. M9.4 must
truthfully distinguish invalid input/data, insufficient history,
deterministic compute failure, transient operational failure,
cancellation, interruption and explicit unknown/unclassified failure
without guessing from arbitrary exception text.

### F09 - Invalid HTTP identifiers have inconsistent response mapping

Disposition: ACCEPTED LOW-SEVERITY CORRECTION.

Invalid request identifiers must be rejected consistently as request
validation errors rather than becoming internal-server errors.

This does not alter lifecycle-conflict semantics.

### F10 - Required closure evidence is incomplete

Disposition: ACCEPTED CLOSURE GAP.

Missing required evidence must be completed before M9.4 is re-closed.

### F11 - Closure/traceability documentation overstates verification

Disposition: ACCEPTED DOCUMENTATION CONSEQUENCE.

Authoritative documentation is synchronized only after implementation
and validation corrections are proven.

## 5. Non-negotiable preservation boundaries

M9.4g must preserve:

1. accepted M4 Backtest timing and financial semantics;
2. accepted M5 WFA mathematics;
3. accepted M6/M7 Paper causality;
4. accepted M8 application authority;
5. M9.2 ExperimentSpec, RunAttempt, evidence and immutable-artifact
   semantics except where stricter validation is required;
6. M9.3 canonical instrument, universe and successor dataset truth;
7. fixed registered Trial denominators;
8. append-only Trial/job/attempt history;
9. actual bounded local worker slots;
10. atomic duplicate-safe queue claiming;
11. explicit retry rather than retry-through-Start;
12. cooperative cancellation;
13. restart recovery separate from resume/retry;
14. independent-account aggregation rather than shared-capital portfolio
    claims;
15. absence of qualification authority in M9.4;
16. absence of live-order authority;
17. prohibition on guessed provider/procedure/data mappings.

M9.4g must not use an audit correction as justification to change
financial trading semantics.

## 6. M9.4g1 - Execution identity and registered-intent integrity

Owns F01, F02 and F03.

### D01 - Prepared execution identity is binding

`execute_prepared()` must execute inputs that are proven to match the
prepared specification.

Immediately before authoritative financial execution, the system must
either:

- consume an immutable prepared executable snapshot; or
- recompute authoritative identities from the exact inputs about to be
  executed and prove equality with the prepared identity.

An accepted result must never be terminalized under fingerprints or a
manifest that describe different financial inputs.

M9.4g must reuse the existing canonical Backtest run-manifest and
configuration-fingerprint authority, or a single shared canonical
projection used by that authority. It must not introduce a second
competing financial-execution identity merely for registered Trials.

Because `BacktestConfig` and strategy objects may contain mutable state,
the verification boundary must operate on the final values that will
actually execute. Verification must occur immediately before financial
execution, or execution must consume an immutable snapshot produced by
the same canonical preparation boundary.

### D02 - Prepared candle content is protected from post-prepare drift

The candle sequence represented by the prepared identity must not be
silently mutable between preparation and execution.

Implementation may use an immutable snapshot or equivalent verified
content check.

This must preserve canonical candle ordering and existing Backtest
semantics.

### D03 - Supplied RunAttempt remains bound to the exact specification

Existing RunAttempt/ExperimentSpec binding checks remain required.

New input-integrity checks are additive and must not weaken attempt
identity.

### D04 - Registered semantics are derived from executable truth

For each registered material field that can be authoritatively projected
from executable inputs, validation must derive the value from the actual
objects that will execute.

At minimum this includes all registered semantics currently represented
by:

- Backtest configuration;
- effective strategy parameters;
- RuntimeContext risk/economic settings;
- DatasetContext;
- price-adjustment/data-treatment basis.

A resolver-provided declaration may carry information, but it cannot
serve as its own proof of executable truth.

### D05 - Unverifiable material semantics fail closed

If a registered material declaration cannot be proven from authoritative
executable inputs under an accepted mapping, execution is rejected as
unverifiable.

M9.4g must not invent a provider, procedure, economic or data mapping to
make validation pass.

### D06 - Successor dataset compatibility participates in registered reuse

For registered execution using the M9.3 successor dataset path, exact
reuse eligibility must verify the applicable successor canonical dataset
semantics.

Compatibility must include the canonical identity/data-treatment facts
required by M9.3.

For the registered successor-dataset path, canonical reuse
compatibility is determined by the applicable
`DatasetIdentityV2.dataset_id`, with the requested and source
DatasetReference artifacts both present and integrity-verified.

Provider acquisition provenance is not automatically required to be
identical when distinct trusted acquisitions legitimately represent the
same canonical dataset and therefore the same canonical dataset
identity.

A missing, corrupt or unresolvable applicable DatasetReference fails
reuse eligibility. M9.4g must not fall back from failed successor
identity verification to legacy ExperimentSpec-only reuse.

### D07 - Reuse lineage remains explicit

Reuse must continue to:

- create no fake RunAttempt;
- preserve the original source RunAttempt;
- preserve source evidence/result identity;
- preserve historical execution time;
- record sufficient requested/source dataset lineage to prove
  compatibility.

### M9.4g1 required tests

At minimum:

1. mutate initial capital after preparation - reject;
2. mutate material runtime economics after preparation - reject;
3. mutate effective strategy parameters after preparation - reject;
4. mutate DatasetContext after preparation - reject;
5. mutate prepared candle content after preparation - reject or prove
   immutable;
6. keep declarations unchanged while changing actual risk/economic
   executable settings - reject;
7. keep declarations unchanged while changing actual data-treatment
   semantics - reject;
8. incompatible successor canonical instrument - no reuse;
9. incompatible price-adjustment basis - no reuse;
10. missing/corrupt required successor dataset lineage - no reuse;
11. compatible canonical dataset with acceptable differing acquisition
    provenance - preserve permitted reuse;
12. existing exact compatible reuse remains green;
13. existing authoritative Backtest parity remains green.

## 7. M9.4g2 - Persistence authority and population invariants

Owns F04, F05 and F06.

### D08 - Persistence/integrity failures stop new claims

Ordinary Trial-specific failure remains isolated.

Authoritative persistence, artifact-integrity or reconciliation failure
must remain distinguishable from an ordinary Trial outcome and must
propagate to the scheduler fail-closed boundary.

Once such a failure is observed, no new ResearchJob may be claimed by
that worker-pool run.

Already-claimed work follows truthful durable recovery semantics; it is
not guessed successful.

### D09 - Registered-population mutation has one authority

After successful complete registration, no supported public persistence
operation may append another initial Trial to the revision.

Whole-population registration remains the authority for the initial
denominator.

Internal persistence helpers may exist only when they cannot be used as
a supported bypass around the authoritative lifecycle.

### D10 - Initial and retry job creation have explicit authorities

Initial ResearchJobs are created by authoritative Start.

Retry ResearchJobs are created by authoritative Retry.

No supported lower-level job insertion API may be used to bypass those
lifecycle contracts for an already registered operational revision.

### D11 - Registration idempotence uses semantic chronological identity

Population equality must not depend on lexical ordering of ISO timestamp
text.

Reloaded Trial populations must be compared using the same semantic
datetime ordering/keying used by registration, or by an equivalent
order-independent canonical population comparison.

Existing content identities and stored timestamps must not be rewritten
merely to fix comparison ordering.

### M9.4g2 required tests

At minimum:

1. two-job pool: first job suffers authoritative artifact persistence
   failure; second remains QUEUED;
2. ordinary Trial failure still permits unrelated work to continue;
3. append Trial after complete registration - reject with zero mutation;
4. append Trial after Start - reject with zero mutation;
5. bypass initial-job creation outside Start - reject;
6. bypass retry-job creation outside Retry - reject;
7. repeated identical mixed-offset registration returns the existing
   revision/population;
8. chronological continuity/gap behavior remains unchanged;
9. fixed Trial denominator remains unchanged across retry/reuse/failure;
10. existing concurrent claim and worker-bound tests remain green.

## 8. M9.4g3 - Result validity, failure semantics and HTTP validation

Owns F07, F08 and F09.

### D12 - One strict canonical Backtest result reader

M9.4g must introduce or reuse a single strict version-aware validation
boundary for Backtest result artifacts consumed as authoritative
research evidence.

Validation must cover the canonical result shape actually emitted by the
authoritative serializer rather than only checking three top-level list
names.

The reader/validator must share the authoritative serialized-result
contract and schema definitions rather than inventing an independent
result format.

This validation boundary does not recompute trading signals, fills,
costs, positions, P&L or other Backtest financial behavior. It validates
the persisted canonical result contract; the existing Backtest engine
remains the sole financial-computation authority.

### D13 - Consumed financial fields are semantically validated

Before aggregation accepts a result-bearing Trial, required consumed
records must have valid:

- record structure;
- required fields;
- numeric types;
- finite numeric values;
- parseable timestamps where timestamps are canonical;
- chronological/record consistency required by the result contract;
- equity-bar/curve correspondence.

Garbage trade records or malformed timestamps may not become accepted
qualification inputs merely because the bytes are content-addressed.

### D14 - Failure disposition, phase and cause remain distinct

`TrialDisposition` remains authoritative for lifecycle/outcome classes,
including:

- `INVALID`;
- `INSUFFICIENT`;
- `CANCELLED`;
- `INTERRUPTED`;
- `FAILED`.

Those dispositions must not be duplicated or blurred into a generic
failure-cause string.

For an actual `FAILED` Trial/ResearchJob, durable semantic cause
classification must support at least:

- deterministic compute failure;
- transient operational failure;
- unknown/unclassified failure.

Typed/structured boundaries establish a known cause. Arbitrary
exception-message matching must not invent one.

Existing labels such as input resolution, historical retrieval,
specification preparation and Backtest execution describe a processing
phase, not by themselves a semantic failure cause.

M9.4g does not require a new durable phase field merely to preserve
those existing labels. If phase remains part of the durable/public
contract, it must be represented separately from cause through a
backward-compatible additive design. Otherwise the accepted minimum is
truthful Trial disposition plus truthful semantic cause classification.

Unknown remains an explicit truthful fallback.

### D15 - INVALID becomes an actual reachable runtime outcome

Where authoritative validation establishes invalid input/data under the
accepted contract, the Trial must be capable of reaching
`TrialDisposition.INVALID`.

A losing or zero-trade valid computation remains EXECUTED.

### D16 - HTTP identifier validation is consistent

Whitespace/empty semantic identifiers are request-validation failures.

Research read endpoints should return the accepted validation response
rather than 500.

Lifecycle conflicts remain distinct from malformed request identity.

### M9.4g3 required tests

At minimum:

1. real canonical serialized Backtest result accepted;
2. missing required bar field rejected;
3. malformed trade shape rejected;
4. malformed timestamp rejected;
5. mismatched curve/bar timestamps rejected where the canonical contract
   requires correspondence;
6. invalid numeric type rejected;
7. NaN/inf rejected in consumed financial data;
8. valid zero-result-bearing revision remains truthful;
9. invalid-data execution path -> INVALID;
10. insufficient history -> INSUFFICIENT;
11. deterministic failure -> FAILED with deterministic cause;
12. transient operational failure -> FAILED with transient cause;
13. unknown failure -> FAILED with explicit unknown cause;
14. whitespace progress/list/detail/aggregation identifiers -> 422;
15. lifecycle conflict behavior remains unchanged;
16. ASGI-level route tests cover the real HTTP mapping.

## 9. M9.4g4 - Closure evidence and documentation

Owns F10 and F11 plus final cross-slice validation.

### D17 - Mandatory missing closure scenarios are executed

Before M9.4 re-closure, evidence must include:

1. mixed-state restart with queued, running, executed, reused, failed and
   cancelled work represented together;
2. cancellation requested while financial computation is already
   running;
3. recovery persistence failure with transactional rollback and startup
   refusal/fail-closed behavior;
4. retry after recovered interrupted bound work;
5. real ASGI persistence workflow coverage;
6. representative resource measurement and explicit reviewed rationale
   for `research_max_trials_per_revision`.

### D18 - Population-limit evidence is measurement, not constant assertion

A test that asserts `5000` equals the configured value is not resource
evidence.

The final value must have a recorded workload/environment measurement
and a documented rationale.

If measurement shows the current value is inappropriate, changing the
operational bound requires explicit review but does not alter
StudyRevision/Trial identity.

### D19 - Behavioral documentation is synchronized after proof

After implementation and validation:

- PROJECT_STATUS;
- ROADMAP;
- ARCHITECTURE where affected;
- DECISIONS where affected;
- INVARIANTS;
- TRACEABILITY;
- M9.4 design/closure evidence;
- VALIDATION_PLAN

must accurately describe the repaired behavior and evidence.

Historical commit identities remain historical facts and are not
rewritten.

### D20 - M9.4 is re-closed only after final evidence

Re-closure requires:

- all accepted blocker corrections;
- focused regression for every audit finding;
- M9.4-wide regression;
- accepted cross-milestone preservation regression;
- complete Python regression;
- `git diff --check`;
- human final diff review;
- controlled staging;
- separately approved commit;
- separately approved push;
- post-push repository verification.

Only after this gate may M9.5 qualification implementation treat M9.4
evidence as a repaired trusted foundation.

Human acceptance of this M9.4g design does not itself authorize
production-code mutation.

The accepted design baseline must first be reviewed, staged, committed
and pushed under the normal separate human approval gates. After that
published design baseline exists, beginning M9.4g1 production
implementation requires a separate explicit human authorization.

## 9.1 M9.4g4 evidence status - 2026-10-04

The accepted D17 closure scenarios now have direct regression evidence for:

1. one mixed-state restart containing QUEUED, RUNNING, EXECUTED, REUSED,
   FAILED and CANCELLED work, where recovery changes only stale RUNNING work
   to INTERRUPTED and preserves the six-Trial denominator;
2. cancellation requested while financial computation is already running,
   where truthful completed execution is retained rather than fabricated as
   cancelled;
3. recovery persistence failure, transaction rollback and fail-closed startup
   refusal;
4. explicit retry after recovered interrupted bound work while preserving the
   Trial, ExperimentSpec binding and prior attempt history;
5. real ASGI workflow persistence into the independent SQLite catalog; and
6. representative resource measurement at the reviewed
   `research_max_trials_per_revision=5000` ceiling.

The one-off local resource measurement used production registration code with
one continuous membership episode and 5,000 distinct parameter variants on
Windows 10 AMD64, Python 3.11.9 and SQLite 3.45.1 at repository head
`a32e22d5b59bc625595d0c0ff3e6036a5e4ac527`.

Observed measurement:

- 5,000 Trials registered and 5,000 Trials persisted;
- elapsed registration time: 10.837931 seconds;
- traced peak Python memory: 11.857 MiB;
- SQLite database size: 6.855 MiB;
- content-addressed artifact footprint: 1.104 MiB across two files.

This is local safety-envelope evidence, not a throughput SLA or production
capacity guarantee. The value 5,000 remains a backend safety ceiling and
changing it requires explicit review. It is operational configuration and does
not participate in StudyRevision or Trial identity.

D19 documentation synchronization is part of M9.4g4. D20 automated validation has now passed: 64 focused tests, 222 M9.4-wide tests, 757 cross-milestone preservation tests and 1325 complete Python tests, with `git diff --check` clean.
Final human diff review, separately approved staging/commit/push and post-push verification subsequently completed successfully. The exact human-reviewed candidate was published at `68df76b853ebdb8881109798aaa5dac8906c453d`; local and remote branch heads were verified equal after push. M9.4 is therefore re-closed. The planned independent M9.4 post-remediation audit remains the next gate before fresh M9.5 design or implementation.

## 10. Implementation order

Implementation proceeds in four independently reviewable slices:

### M9.4g1

Execution identity and registered-intent integrity.

Findings:

F01, F02, F03.

### M9.4g2

Persistence authority and population invariants.

Findings:

F04, F05, F06.

### M9.4g3

Result validity, failure semantics and HTTP validation.

Findings:

F07, F08, F09.

### M9.4g4

Closure evidence, resource-bound evidence, documentation synchronization
and final re-closure.

Findings:

F10, F11 plus cross-slice closure validation.

Each implementation slice must:

1. declare behavior impact;
2. identify affected accepted M9.4 decisions/invariants;
3. add negative tests before or with the correction;
4. run focused regressions;
5. run appropriate preservation regressions;
6. inspect the exact diff;
7. stop for separate human staging approval;
8. stop for separate human commit approval;
9. stop for separate human push approval.

The next slice does not begin merely because code exists. The prior
slice must have reviewed validation evidence.

## 11. Explicit non-goals

M9.4g does not implement:

- M9.5 qualification policy or scoring;
- Candidate progression;
- M9.6 WFA/OOS progression;
- M9.7 persistent PaperCampaign progression;
- M9.8 research-workspace frontend;
- distributed research workers;
- multi-process shared-database scheduling claims;
- shared-capital multi-symbol portfolio simulation;
- new provider/procedure mappings invented from legacy data;
- real-money trading.

## 12. Stop conditions

Implementation must stop for separate design review if a proposed fix
would require:

- changing accepted Backtest financial semantics;
- redefining ExperimentSpec identity;
- redefining existing content-addressed artifact identity;
- weakening M9.3 canonical instrument/dataset truth;
- changing Trial identity;
- changing retry eligibility;
- changing cancellation truthfulness;
- adding qualification judgments to M9.4;
- inventing provider/procedure/data authority;
- introducing live-order authority.

## 13. Proposed acceptance gate

Before production implementation:

`M94G_DESIGN_ACCEPTED=True`

must be explicitly approved by the human reviewer.

Until then:

`M94G_PRODUCTION_MUTATION_AUTHORIZED=False`

No production-code mutation is authorized by this draft.
