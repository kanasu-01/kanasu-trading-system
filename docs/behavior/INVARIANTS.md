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

**Status:** DESIGNED

A registered Trial remains represented in research history when it influenced the search process, including losing, invalid, failed, cancelled, interrupted and reused cases according to its accepted disposition contract.

### RESEARCH-RULE-002 ? Qualification does not rewrite immutable evidence

**Status:** DESIGNED

Changing a QualificationPolicy produces a new QualificationDecision over identified immutable evidence rather than rewriting the original result/evidence.

### RESEARCH-RULE-003 ? Successful execution is not equivalent to successful research

**Status:** DESIGNED

Workflow, execution, validity and evidence-decision state remain distinct.

### RESEARCH-RULE-004 ? Independent universe accounts are not a portfolio

**Status:** DESIGNED

Independent per-instrument P&L or returns are not summed and represented as one shared-capital portfolio.

### RESEARCH-RULE-005 ? Candidate progression preserves claim and stage order

**Status:** DESIGNED

WFA derives from an exact CandidateRevision. Research-qualified Paper may begin only after that same CandidateRevision satisfies its applicable registered WFA/OOS qualification. A material configuration/procedure change creates new research lineage. Separately labelled operational-smoke Paper cannot be represented as qualified progression.

### RESEARCH-RULE-006 ? Current constituents projected backward are not survivorship-free evidence

**Status:** DESIGNED

Universe quality and provenance constrain the research claims that may be made from a Study.
