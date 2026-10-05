# M9.4i - Final Independent Re-Review Corrections

## Status

PUBLISHED CORRECTIVE CANDIDATE; POST-PUSH VERIFIED; INDEPENDENT RE-REVIEW PENDING.

M9.5 remains BLOCKED.

This bounded corrective slice exists because the independent re-review of
published M9.4h HEAD
`306c156a5b58edb8a4dd6331409d473bc08af98b`
returned:

`M95_GATE=BLOCKED`

The re-review independently reproduced four remaining authority/integrity
defects and one closure-evidence defect.

M9.4i is not M9.5 design. It must preserve the accepted M9.4 architecture and
correct only the remaining verified defects before another independent
re-review.

## 1. Authoritative baseline

Repository:

`kanasu-01/kanasu-trading-system`

Branch:

`m9-v1-research-platform`

M9.4i starting HEAD:

`306c156a5b58edb8a4dd6331409d473bc08af98b`

Published M9.4i corrective HEAD:

`eab3c742ca5fbe0d7e058bb4cc8db758803848ab`

Post-push verification confirmed the local and remote
`m9-v1-research-platform` branch heads both equal that exact commit.

Relevant earlier correction heads:

- `d1efd238c3ee0762de7a31647c3c919f98dbcab6` - M9.4h N01-N04;
- `524b9dda8ab40ac5da9de44a284310fa163e21e9` - M9.4h N05-N06;
- `306c156a5b58edb8a4dd6331409d473bc08af98b` - M9.4h N07 documentation candidate.

The new independent re-review reproduced:

- H01 HIGH - canonical class identity plus `deepcopy` does not prove canonical
  executable behavior;
- H02 HIGH - the supported lower exact-reuse completion boundary can
  terminalize reuse without current DatasetReference artifact verification;
- H03 HIGH - unreadable authoritative prepared manifests such as
  `PermissionError` can become ordinary Trial failure and allow later claims;
- H04 MEDIUM - the population proof proves the caller-supplied subset, not
  completeness of the canonical registered plan;
- H05 LOW - validation selectors/count wording is not sufficiently exact and
  some authority claims exceed demonstrated guarantees.

The re-review independently reproduced the complete Python suite at 1342
passing tests. That regression result is useful preservation evidence but does
not override H01-H04.

## 2. M9.4i objective

M9.4i shall make the registered M9.4 authority chain true at the supported
workflow boundary:

1. registered procedure identity determines the executable strategy behavior;
2. exact reuse has one supported authority that verifies immutable artifact
   lineage before atomic terminalization;
3. inability to read or verify an authoritative immutable artifact propagates
   fail-closed rather than becoming an ordinary Trial outcome;
4. only complete canonical plan expansion can mint a startable Trial
   population;
5. validation evidence records exact commands/scopes rather than ambiguous
   labels.

No correction may change Backtest financial mathematics, WFA mathematics,
Paper causality, independent-account aggregation, provider truth, dataset
identity meaning, qualification scope, or live-order scope.

## 3. Preservation boundaries

M9.4i must preserve:

1. M4 Backtest timing, fills, sizing, P&L, equity, drawdown and execution
   feedback;
2. M5 walk-forward mathematics;
3. M6/M7 Paper causality;
4. M8 application authority;
5. M9.2 ExperimentSpec, RunAttempt, evidence and content-addressed artifact
   identities except stricter integrity enforcement;
6. M9.3 canonical instrument, universe, DatasetIdentityV2 and DatasetReference
   truth;
7. fixed StudyRevision Trial denominators;
8. independent simulated Trial accounts rather than shared-capital portfolio
   claims;
9. bounded local workers and duplicate-safe claiming;
10. Start separate from Retry;
11. retry preserving Trial identity and append-only history;
12. recovery separate from resume/retry;
13. cooperative cancellation;
14. exact reuse without fabricated RunAttempt;
15. no guessed provider, procedure, economic or data mappings;
16. no strategy qualification authority in M9.4;
17. no live-order authority.

## 4. H01 - Canonical executable procedure authority

### D01 - Resolver-supplied strategy objects are not registered execution authority

A `ClaimedTrialExecutionInputs.strategy` object may remain in the compatibility
shape of the resolver contract, but registered M9.4 execution must not consume
that caller-owned object as the financial strategy authority.

Its class identity, instance methods, monkey-patched instance attributes,
closures, callbacks or other mutable aliases must not determine registered
financial execution.

### D02 - Registered execution constructs strategy behavior from canonical authority

For a registered Trial, executable strategy behavior must be constructed from:

- the accepted `strategy_procedure_id`;
- the accepted canonical procedure mapping;
- the validated `BacktestConfig`;
- the registered parameter configuration.

Add one explicit canonical registered-strategy construction helper at the
strategy-factory boundary.

The helper must:

1. resolve the accepted procedure class from `strategy_procedure_id`;
2. resolve the configured strategy class from `BacktestConfig`;
3. require those authorities to be identical;
4. construct a fresh strategy through the canonical strategy factory;
5. require the constructed exact type to equal the accepted procedure class;
6. verify the constructed strategy's effective research parameters equal the
   registered parameter configuration.

The resolver-supplied strategy instance is therefore not used to prove
effective parameters.

### D03 - Preparation and final execution each use fresh canonical instances

Registered preparation must use a canonical strategy constructed from the
validated snapshot rather than the resolver-owned strategy instance.

After retrieval/preparation, the executor must take its final stable input
snapshot, revalidate registered semantics, construct a new canonical strategy
from that final snapshot, and pass that canonical instance into
`execute_prepared()`.

`execute_prepared()` may continue to isolate its supplied strategy for the
general/non-registered orchestration contract. M9.4i must not break supported
non-registered callers.

### D04 - Required H01 regressions

Add adversarial tests proving:

1. an instance-level override of `on_new_candle` on an otherwise canonical
   strategy instance cannot change registered execution;
2. a mutable closure/callback attached to the resolver-owned strategy cannot
   change registered execution during final manifest verification;
3. canonical execution still produces the registered strategy behavior;
4. registered ExperimentSpec/evidence remains bound to the canonical
   executable behavior;
5. unrelated configured procedure/class mismatches still fail closed.

## 5. H02 - One supported exact-reuse authority

### D05 - Raw reuse terminalization is an internal persistence primitive

The SQLite transaction that atomically marks a RUNNING job as exact reuse is
not a supported workflow/API authority.

The current public lower-level completion boundary must be removed from the
supported surface, for example by converting it to an explicitly private
persistence primitive used only by the authoritative executor workflow.

Tests may exercise the primitive's transaction invariants directly, but project
documentation and application code must not treat it as independently
authoritative.

### D06 - Artifact verification belongs to the workflow authority

Before invoking the atomic reuse terminalizer, the authoritative registered
reuse workflow must verify the requested and source DatasetReference artifacts
through the content-addressed artifact store:

- artifact exists;
- bytes match the artifact ID;
- byte count is correct where metadata supplies it;
- bytes decode as the accepted DatasetReference schema;
- durable artifact metadata/schema is compatible;
- durable dataset-ID binding exists;
- requested and source canonical dataset IDs match;
- source evidence references the exact source DatasetReference.

Only after this verification may the private database transition persist
`REUSED`.

The transition must continue to create no new RunAttempt and preserve source
attempt/evidence/result history.

### D07 - Required H02 regressions

Add tests proving:

1. corruption of a previously valid source DatasetReference blocks supported
   reuse;
2. corruption of a requested DatasetReference blocks supported reuse;
3. missing artifact bytes block supported reuse;
4. the registered executor cannot reach REUSED through an unverified public
   completion route;
5. successful reuse still persists explicit requested/source lineage and
   creates no fake RunAttempt.

## 6. H03 - Authoritative immutable-artifact read failures

### D08 - Immutable artifact access failures are authoritative at authority boundaries

When an execution identity or accepted lineage depends on an immutable
content-addressed artifact, inability to read or verify that artifact is an
authoritative research-state/integrity failure.

At the prepared Backtest manifest boundary, classify at least:

- missing file;
- permission/access failure;
- other filesystem `OSError`;
- content-address identity mismatch/corruption;

as `AuthoritativeResearchStateError`.

Do not convert those failures into ordinary Trial FAILED outcomes.

### D09 - Worker pool remains fail-closed

An authoritative immutable-artifact failure must propagate through:

- orchestrator;
- claimed-job executor;
- worker-loop boundary.

The already claimed job remains truthfully recoverable according to existing
recovery semantics, and the current worker-pool invocation must initiate no
later claims after the authoritative failure.

Ordinary independent strategy/financial failures remain isolated and must not
be reclassified as authoritative merely because they are exceptions.

### D10 - Required H03 regressions

Add tests proving, with a one-worker multi-job pool:

1. manifest `PermissionError` propagates authoritatively;
2. representative manifest `OSError` propagates authoritatively;
3. the later job remains QUEUED/unclaimed;
4. no false Trial FAILED disposition is written for the authoritative failure;
5. the existing corrupt/missing manifest behavior still fails closed;
6. ordinary financial computation failure still remains an isolated Trial
   failure.

## 7. H04 - Complete population minting authority

### D11 - Atomicity and completeness are distinct

The schema-v5 proof currently proves that one supplied Trial tuple and its
events committed atomically.

That is necessary but not sufficient to prove that the tuple is the complete
population implied by the canonical StudyRevision plan.

M9.4i must not describe transaction atomicity as proof of plan completeness.

### D12 - Canonical expansion is the sole supported proof minter

`RegisteredStudyRegistrationService.register_study_revision()` owns canonical
plan resolution, membership-episode expansion, parameter-variant expansion,
Trial identity creation and population-limit enforcement.

Only this complete canonical expansion workflow may mint the durable
startability proof.

The raw catalog persistence operation that accepts prebuilt Trial/event tuples
must become an explicitly private persistence primitive. It is not a supported
registration authority.

Application/API code must reach population registration through the
registration service, not through the primitive.

### D13 - Start continues to verify durable proof against durable rows

`start_study_revision_batch()` must retain its existing fail-closed checks:

- proof exists;
- count is positive;
- durable Trial count matches proof;
- durable Trial-ID fingerprint matches proof;
- Start remains idempotent;
- Start never acts as Retry.

M9.4i does not weaken these checks.

### D14 - Required H04 regressions

Add tests proving:

1. supported registration of a genuine multi-Trial plan persists the full
   population and proof;
2. no supported/public population-registration API accepts an arbitrary
   caller-supplied Trial subset;
3. Start still rejects revision shells and missing/corrupt proofs;
4. private partial persistence without authoritative proof remains
   non-startable;
5. repeated canonical registration remains idempotent;
6. Retry does not change the registered denominator.

The earlier adversarial case - supplying one authentic Trial from a genuine
two-Trial plan directly to a public proof-writing method - must no longer be a
supported operation.

## 8. H05 - Reproducible validation evidence

### D15 - Validation labels must name exact selectors

Do not use phrases such as "all M9.4-named tests" unless the command actually
selects every matching test across the repository.

Record exact commands and exact counts for at least:

1. H01-H04 focused corrective tests;
2. research-local M9.4 filename selection, if retained;
3. repository-wide `test_m94*.py` filename selection;
4. repository-wide `pytest tests -k m94 -q` semantic-name selection;
5. expanded preservation matrix;
6. complete Python suite;
7. `git diff --check`.

Historical counts remain historical and must not be silently rewritten as
though they came from broader selectors.

### D16 - Documentation follows proven behavior

Only after H01-H04 implementation and validation may current project,
architecture, decision, invariant, traceability and validation documents claim
the corrected authorities.

The independent re-review remains pending after local validation and protected
publication.

`M95_GATE=BLOCKED` remains authoritative until that independent re-review
returns PASS.

## 9. Implementation slices

### M9.4i1 - Canonical registered strategy execution

Owns H01 / D01-D04.

Expected production areas:

- `core/strategies/strategy_factory.py`;
- `core/research/claimed_trial_execution_inputs.py`;
- `core/research/claimed_research_job_executor.py`;
- focused registered-execution tests.

### M9.4i2 - Exact reuse and immutable artifact authority

Owns H02/H03 / D05-D10.

Expected production areas:

- `core/research/claimed_research_job_executor.py`;
- `core/research/backtest_research_orchestrator.py`;
- `core/research/sqlite_research_catalog_store.py`;
- reuse/executor/worker tests.

### M9.4i3 - Sole complete-population authority

Owns H04 / D11-D14.

Expected production areas:

- `core/research/registered_study_registration.py`;
- `core/research/sqlite_research_catalog_store.py`;
- registration/application tests.

No schema migration is required merely to rename or internalize a persistence
primitive. If implementation evidence shows that private-boundary enforcement
cannot establish the accepted authority safely, stop and revise this design
before introducing a new schema.

### M9.4i4 - Closure evidence and documentation

Owns H05 / D15-D16 plus cross-slice validation.

Expected areas:

- authoritative documentation;
- traceability;
- exact validation command record;
- final re-review preparation.

## 10. Required validation before re-review

Before M9.4 can again become a re-closure candidate:

1. direct adversarial reproductions for H01-H04 must pass;
2. focused tests for every changed production boundary must pass;
3. repository-wide `test_m94*.py` selection must pass;
4. repository-wide `pytest tests -k m94 -q` selection must pass;
5. expanded cross-milestone preservation must pass;
6. complete Python regression must pass;
7. `git diff --check` must pass;
8. exact changed-file review must pass;
9. no unintended staging may exist;
10. protected stage, commit and push require separate human approval under the
    Kanasu Runner protocol;
11. post-commit and post-push verification must pass;
12. a fresh independent re-review must return exactly one M9.5 gate.

A green regression suite is necessary but does not replace adversarial
authority tests.

## 11. Final gate

M9.4i completion does not itself authorize M9.5.

After publication and post-push verification, perform another independent M9.4
re-review.

Only:

`M95_GATE=PASS`

authorizes fresh M9.5 design.

A PASS does not authorize M9.5 production implementation.

## Local M9.4i implementation and validation evidence

Status: PUBLISHED CORRECTIVE CANDIDATE VALIDATED; POST-PUSH VERIFIED; INDEPENDENT RE-REVIEW PENDING.

Parent HEAD:

`306c156a5b58edb8a4dd6331409d473bc08af98b`

The local corrective candidate implements the independent re-review findings as follows:

- H01: registered financial execution no longer trusts resolver-owned executable strategy behavior. Canonical registered strategy construction is derived from accepted procedure/configuration authority for specification preparation and again for final execution. Adversarial instance-method override and mutable-alias regression coverage was added.
- H02: the raw exact-reuse SQLite terminalizer is an internal persistence primitive rather than a supported public workflow. The registered executor verifies immutable DatasetReference bytes, identity, schema and compatible lineage before the atomic REUSED transition. Corrupt authoritative lineage fails closed and does not fabricate a new RunAttempt.
- H03: authoritative manifest reads classify filesystem failures including `PermissionError`/`OSError` as authoritative research-state failures. The worker pool stops before claiming later jobs; ordinary independent Trial failures retain their existing isolation semantics.
- H04: `RegisteredStudyRegistrationService` canonical plan/universe/variant expansion is the sole supported authority that can invoke complete-population persistence. Direct public population-proof minting is rejected. The private transaction primitive remains covered for rollback/identity invariants, and Start continues to verify the durable population count/fingerprint before creating initial jobs.
- H05: validation evidence uses explicit selectors and exact reproduced counts rather than ambiguous historical wording.

Reproduced local evidence on 2026-10-05:

1. H01 focused validation after implementation: 60 passed.
2. H01-H03 focused validation after H02/H03 reconciliation: 94 passed.
3. H01-H04 focused validation including population-authority tests: 153 passed.
4. Repository-wide filename selector: 20 files matching `tests/**/test_m94*.py`; 245 passed.
5. Semantic selector: `pytest tests -k m94 -q`; 251 passed, 1098 deselected.
6. Full Python regression: `pytest tests -q`; 1349 passed.
7. `git diff --check`: passed.
8. Supported core callers of the former public raw exact-reuse terminalizer: zero.
9. Supported core callers of the public population-proof writer: zero.
10. The known Windows status entries for `core/strategies/base_strategy.py` and `core/strategies/sma_crossover_strategy.py` remain content-clean under `git -c core.autocrlf=false diff -- <path>`.

The broad validation command itself completed all test and diff checks successfully. Its final shell status was non-zero only because a post-validation single-item untracked-file guard was brittle; that guard did not change repository content and does not invalidate the completed test evidence.

This section records the validated and published corrective candidate at `eab3c742ca5fbe0d7e058bb4cc8db758803848ab`. Protected staging, commit and push were separately human-approved, and post-push verification confirmed the exact local/remote HEAD and committed 17-file manifest. This publication does not close the independent audit. `M95_GATE=BLOCKED` remains authoritative until an independent re-review of `eab3c742ca5fbe0d7e058bb4cc8db758803848ab` returns `M95_GATE=PASS`.
