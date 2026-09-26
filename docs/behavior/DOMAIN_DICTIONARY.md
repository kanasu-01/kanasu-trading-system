# Kanasu V1 Domain Dictionary

## Research concepts

### Study

The research investigation a user recognizes and returns to over time.

### StudyRevision

One immutable registered version of a Study plan. A material research change creates another revision rather than silently rewriting the registered plan.

### Trial

One registered research test or disposition within a Study's search history. A Trial exists before execution and remains recorded whether it succeeds, loses money, fails, is invalid, is cancelled or is explicitly reused.

### ExperimentSpec

The exact immutable instructions for one deterministic computation. Equivalent retries reference the same specification.

### RunAttempt

One physical attempt to execute an ExperimentSpec. Retries have distinct attempt identities.

### Result

The authoritative output produced by an existing computation engine such as Backtest or WFA. M9 must not create a competing financial-accounting result model.

### ResearchEvidence

The existing immutable reproducibility/evidence record. Acceptance of a ResearchEvidence record means the evidence record satisfies its contract; it does not mean the strategy is qualified.

### QualificationPolicy

A versioned definition of the evidence criteria required for a particular research stage.

### QualificationDecision

An immutable application of one QualificationPolicy version to identified evidence. Re-evaluation under another policy creates another decision.

A criterion reports one of `SATISFIED`, `NOT_SATISFIED`, `INSUFFICIENT`, `NOT_APPLICABLE` or `INVALID`, together with its observed evidence and reason.

### Candidate

The stable lineage anchor for a research proposition that progresses between validation stages.

### CandidateRevision

One immutable executable research claim.

A fixed Candidate freezes its effective configuration and parameters.

An adaptive Candidate freezes its complete selection/retraining procedure rather than one historically selected parameter set.

### UniverseDefinition

A named or rule-based description of a set of instruments.

### UniverseSnapshot

An immutable, identifiable resolution of universe membership and its provenance/quality semantics.

Initial V1 universe-quality classes are:

- `PIT_VERIFIED` ? trusted effective-dated point-in-time membership;
- `PIT_RECONSTRUCTED` ? historical membership reconstructed from documented evidence;
- `RULE_BASED_PIT` ? membership reconstructed by a declared historical rule using information available at the relevant time;
- `CURRENT_SNAPSHOT` ? a present-day membership snapshot used retrospectively, with survivorship-bias limitations; and
- `CUSTOM_FIXED` ? a user-supplied fixed instrument list whose historical-selection limitations remain explicit.

### PaperCampaign

Persistent forward observation of one CandidateRevision using real market data and simulated execution. For research-qualified progression, the CandidateRevision must first satisfy its applicable registered WFA/OOS qualification. A separately labelled operational-smoke Paper run is not equivalent to qualified research progression.

### PaperSession

One runtime episode inside a PaperCampaign. A runtime session is not by itself the complete research campaign.

### Artifact

Immutable supporting material such as a manifest, serialized result, report, input snapshot or evidence document.

### AuditEvent

Append-only history of an important lifecycle, review or decision action.

## State dimensions

### Workflow stage

Where research is in the product lifecycle: `DRAFT`, `REGISTERED`, `DEVELOPMENT`, `VALIDATION`, `PAPER` or `CLOSED`.

### Execution state

Whether a computation is `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` or `INTERRUPTED`.

### Validity state

Whether the evidence is `VALID`, `INVALID`, `INSUFFICIENT` or `UNKNOWN` for its intended interpretation.

### Evidence decision

What the evidence permits: `INSUFFICIENT`, `REJECTED`, `ELIGIBLE`, `ACCEPTED_FOR_RESEARCH` or `RETIRED`.

These dimensions are intentionally independent. A computation can succeed operationally and still be rejected by the research process.
