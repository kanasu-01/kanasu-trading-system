# Kanasu Behavioral Invariants

## Status meanings

- `DESIGNED` ? accepted intended behavior not yet claimed as implemented.
- `IMPLEMENTED` ? implementation exists but full trace verification is not yet recorded here.
- `VERIFIED` ? implementation and appropriate test/evidence trace have been checked.
- `DEFERRED` ? intentionally outside the current implementation scope.
- `SUPERSEDED` ? retained for history and replaced by another behavior ID.

## Existing validated behavior

### DATA-RULE-001 ? Missing history is not silently invented

**Status:** VERIFIED

Historical-source composition may use trusted local coverage or an allowed provider, but missing historical candles are not silently synthesized to make a request appear complete.

### DATA-RULE-002 ? Fully covered LOCAL_FIRST does not require provider capability

**Status:** VERIFIED

When trusted local coverage fully satisfies a LOCAL_FIRST request, Kanasu can return local data without constructing/authenticating the external provider.

### DATA-RULE-003 - Historical provider bindings are explicit and effective-dated

**Status:** DESIGNED

Provider-backed historical retrieval uses explicit effective-dated provider bindings. A request may span multiple applicable bindings, but unexplained gaps, conflicting overlaps or ambiguous mappings fail rather than being guessed. Provenance retains each binding and its applied subrange.

### DATA-RULE-004 - Provider wall time does not rewrite canonical time identity

**Status:** DESIGNED

AngelOne-aware request bounds are converted to `Asia/Kolkata` for provider request formatting and naive bounds retain explicit India-wall-time interpretation. Provider formatting does not rewrite the canonical requested range, candle timestamps or dataset fingerprint semantics.

### DATA-RULE-005 - Dataset identity and provenance evolution is versioned

**Status:** DESIGNED

`kanasu.dataset.v1` and existing storage keys are not silently redefined. Successor identity/provenance semantics are versioned, incompatible acquisition streams are not silently mixed, and conflicting stored candle values are not silently overwritten.
### BT-RULE-001 ? Completed-bar decisions obey accepted next-interval execution

**Status:** VERIFIED

A strategy decision made from a completed candle cannot use that candle's future information to obtain an earlier fill. Accepted Backtest execution follows the M4 causal ordering contract.

### BT-RULE-002 ? Simulated account state has one backend authority

**Status:** VERIFIED

Authoritative simulated cash, positions, equity and P&L come from the execution/portfolio domain rather than independent frontend reconstruction.

### WFA-RULE-001 ? OOS data does not select its preceding parameters

**Status:** VERIFIED

A WFA window selects parameters from its permitted in-sample information before running the corresponding out-of-sample evaluation.

### PAPER-RULE-001 ? Wall-clock advancement alone cannot create a Paper fill

**Status:** VERIFIED

A Paper pending intent requires qualifying observed market-source progression under the accepted causal runtime contract.

### PAPER-RULE-002 ? Historical reconciliation cannot manufacture retrospective live trades

**Status:** VERIFIED

Historical gap-recovery candles may rebuild permitted strategy state but cannot retrospectively create Paper executions.

### SAFETY-RULE-001 ? V1 has no supported real-money execution path

**Status:** VERIFIED at the accepted M8 application scope

The supported V1 Backtest and Paper application paths use simulated execution. Real broker order execution remains outside V1.

## M9 designed behavior

### RESEARCH-RULE-001 ? Tested research lineage is not silently erased

**Status:** VERIFIED

A registered Trial remains represented in research history when it influenced the search process, including losing, invalid, failed, cancelled, interrupted and reused cases according to its accepted disposition contract.

### RESEARCH-RULE-002 ? Qualification does not rewrite immutable evidence

**Status:** DESIGNED

Changing a QualificationPolicy produces a new QualificationDecision over identified immutable evidence rather than rewriting the original result/evidence.

### RESEARCH-RULE-003 ? Successful execution is not equivalent to successful research

**Status:** DESIGNED

Workflow, execution, validity and evidence-decision state remain distinct.

### RESEARCH-RULE-004 ? Independent universe accounts are not a portfolio

**Status:** VERIFIED

Independent per-instrument P&L or returns are not summed and represented as one shared-capital portfolio.

### RESEARCH-RULE-005 ? Candidate progression preserves claim and stage order

**Status:** DESIGNED

WFA derives from an exact CandidateRevision. Research-qualified Paper may begin only after that same CandidateRevision satisfies its applicable registered WFA/OOS qualification. A material configuration/procedure change creates new research lineage. Separately labelled operational-smoke Paper cannot be represented as qualified progression.

### RESEARCH-RULE-006 ? Current constituents projected backward are not survivorship-free evidence

**Status:** VERIFIED

Universe quality, provenance and effective-dated membership constrain the research claims that may be made from a Study. Current constituents projected backward are not survivorship-free. A point-in-time claim cannot silently apply a future membership state to an earlier research time.

### RESEARCH-RULE-007 - Fingerprinted Backtest input is the executed input

**Status:** VERIFIED

Automatic Backtest evidence fingerprints the exact canonical candle sequence that is passed to authoritative Backtest execution. Evidence creation must not perform a second historical retrieval whose content could diverge from the executed input.

### RESEARCH-RULE-008 - Retry identity does not inflate computation identity

**Status:** VERIFIED

Equivalent retries may reference the same immutable ExperimentSpec but always receive distinct RunAttempt identities. Runtime/session identity remains separate from both.

### RESEARCH-RULE-009 - Incomplete evidence cannot be represented as accepted

**Status:** VERIFIED

A failed or incomplete reproducibility record cannot be labelled `ResearchEvidenceStatus.ACCEPTED`. Computation success, evidence completeness and future research qualification remain separate concepts.

### RESEARCH-RULE-010 - Accepted automatic evidence requires exact software identity

**Status:** VERIFIED

Automatic evidence may be `ACCEPTED` only when the executable software revision is exactly identifiable. If executable software identity is dirty or unknown, an exact ExperimentSpec cannot be established and no RunAttempt may be fabricated. The financial computation may still produce a result and may persist incomplete evidence when possible. A `SUCCEEDED` RunAttempt with incomplete evidence is valid only when the exact ExperimentSpec had already been established and another evidence requirement later became incomplete.
### RESEARCH-RULE-011 - Instrument lineage is not ticker or provider identity

**Status:** VERIFIED

Canonical instrument lineage uses a Kanasu-owned immutable `instrument_id`. Effective-dated symbol or provider-token changes do not silently create, merge or rewrite canonical instrument identity.

### RESEARCH-RULE-012 - Point-in-time universe membership does not use future membership state

**Status:** VERIFIED

When research is represented as point-in-time universe evidence, the membership applied at each research time corresponds to that time rather than a future membership state. Joins, departures and quality/provenance changes remain explicit. Retrospective `CURRENT_SNAPSHOT` and `CUSTOM_FIXED` use is permitted with its explicitly limited non-PIT semantics.

### RESEARCH-RULE-013 - Retrieval failure is distinct from post-retrieval preparation failure

**Status:** VERIFIED

A genuine successor historical-retrieval failure is distinct from a
post-retrieval DatasetReference preparation, persistence or integrity failure.
Authoritative preparation/integrity failures retain fail-closed state semantics
and are not silently rewritten as provider-retrieval failures or ordinary
independent Trial outcomes.

### RESEARCH-RULE-014 - Registered Trial truth precedes registered execution

**Status:** VERIFIED

A registered Trial exists before any new physical execution performed for that Trial. Exact compatible earlier evidence may be reused only with explicit reused-source lineage; the earlier execution is never rewritten as though it had been registered beforehand.

### RESEARCH-RULE-015 - Trial, job and execution identities remain distinct

**Status:** VERIFIED

Trial, ResearchJob, ExperimentSpec, RunAttempt and runtime/session identities remain distinct. Retry keeps the same Trial, creates new operational job/attempt lineage where applicable, does not inflate the registered Trial denominator and preserves prior disposition history.

### RESEARCH-RULE-016 - Queue ownership and cancellation remain truthful

**Status:** VERIFIED

A durable queued ResearchJob is claimed atomically by at most one worker. Cancellation and interruption states describe what actually happened rather than what was merely requested; running work is not falsely reported cancelled before cancellation becomes effective. Startup recovery changes only stale RUNNING work that requires reconciliation; already queued or terminal executed, reused, failed and cancelled work is not rewritten. If recovery persistence cannot be committed reliably, startup fails closed.

### RESEARCH-RULE-017 - Registered Trial population is immutable

**Status:** VERIFIED

A registered StudyRevision owns one complete finite Trial population before execution starts. Material research-plan changes create new StudyRevision lineage rather than silently changing that population or its denominator.

### RESEARCH-RULE-018 - Continuous universe membership does not reset the account

**Status:** VERIFIED

A universe snapshot transition does not reset an instrument's simulated account while that instrument remains continuously eligible. Trial boundaries follow maximal continuous membership episodes; a genuine membership gap creates a separate episode.
