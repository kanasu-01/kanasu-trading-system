# M9.5 — Strategy Validation Criteria

**Specification:** `KTS-M009-S005-SPEC002-V002`

**Status:** PROPOSED successor to published `KTS-M009-S005-SPEC002-V001`; not governing until exact publication/read-back succeeds.

**Design basis:** accepted AD-026 minimal MVP V1 historical Backtest-to-WFA qualification.

**Scope:** M9.5 qualifies one explicitly selected registered historical Trial at a time for M9.6 consideration. M9.6 remains a future consumer.

## Why V002 exists

V001 expanded the minimal AD-026 design into a StudyRevision-wide validation-run workflow: it scanned the complete Trial population, introduced run-start/run-completion state, run precedence, stale-run invalidation and restart reconciliation, and exposed a StudyRevision-wide eligible list. Those mechanisms are not required for the MVP V1 one-Trial qualification gate. V002 removes that expansion and returns M9.5 to the smallest complete behavior already defined by AD-026. V001 remains unchanged historical evidence; V002 does not rewrite it retroactively.

## What happens

```text
Explicitly selected registered historical Trial
                    ↓
Load centrally active immutable QualificationPolicy
                    ↓
Resolve and verify that Trial's exact saved Backtest result/evidence
                    ↓
Freeze the selected fixed CandidateRevision identity
                    ↓
Count completed trades and trades with net P&L > 0
                    ↓
Apply the one criterion: profitable-trade rate >= T
                    ↓
Append one attributable QualificationDecision
                    ↓
If ELIGIBLE, expose that exact CandidateRevision for M9.6 consideration
```

## Behavior — step by step

1. **Central policy.** Kanasu uses one centrally active immutable versioned `QualificationPolicy`. Its threshold `T` is selected by the authorized human before activation, is finite and from 0 through 100 inclusive, and is fixed for that policy version. Validation never accepts a caller-supplied threshold. A later threshold change requires a new higher policy version and a new append-only activation; earlier policies and decisions remain unchanged. M9.5 adds no HTTP/UI policy-edit or activation endpoint.

2. **One selected Trial.** A validation request names exactly one already registered `Trial`. Kanasu does not scan or automatically evaluate the complete `StudyRevision`, does not select a winner, and does not merge independent Trial results. The Trial's `StudyRevision` and complete registered search population remain historical context through the existing research catalog.

3. **Existing result only.** M9.5 never reruns Backtest. For an `EXECUTED` or `REUSED` result-bearing Trial, it reuses the existing research-catalog, RunAttempt, ResearchEvidence, artifact-identity, canonical-result and manifest/capital verification rules to establish the exact saved result. A Trial with no completed result-bearing disposition is `INSUFFICIENT`. If durable metadata claims a result/evidence lineage but the claimed bytes or identities are missing, corrupt or contradictory, the outcome is `INVALID`. A database/service/permission/read failure that prevents reliable verification is an `OPERATIONAL_ERROR`, not a strategy decision.

4. **Fixed CandidateRevision.** After a result-bearing Trial is successfully verified, Kanasu creates or reuses one immutable fixed `CandidateRevision` identity derived from that Trial's immutable `StudyRevision`, Trial, `ExperimentSpec` and parameter-configuration identities. The CandidateRevision freezes the selected fixed executable claim only; M9.5 does not build the later Candidate lifecycle, adaptive-candidate support, WFA orchestration or Paper progression.

5. **One economic criterion.** From the verified saved trades, `completed_trade_count` is the number of completed trades and `profitable_trade_count` is the number whose monetary net `pnl` is strictly greater than zero after effective costs. Losing and breakeven trades remain in the denominator. If `completed_trade_count` is zero, evidence is valid but economic qualification is `INSUFFICIENT` and the percentage is undefined. Otherwise compare the exact rational value `profitable_trade_count * 100 / completed_trade_count` to the exact Decimal threshold `T`; no display rounding participates in the decision. Equal to or above `T` is `ELIGIBLE`; below `T` is `REJECTED`.

6. **Append one decision.** Each completed evaluation appends one immutable `QualificationDecision` bound to the selected Trial, `StudyRevision`, active policy/version/threshold, evaluator version, decision time and every result/evidence/attempt identity that was actually verified. A valid sufficient decision also binds the fixed CandidateRevision and exact profitable/completed counts plus the exact rational rate numerator/denominator. A verified zero-trade decision records the fixed CandidateRevision and zero counts but no percentage denominator/rate. Missing or invalid evidence must never fabricate CandidateRevision, counts or evidence identities that were not established.

7. **Operational failure.** If the active policy, authoritative catalog, evidence, artifact store or decision persistence cannot be reliably read or written because of a database/service/permission/storage failure, the request reports `OPERATIONAL_ERROR`. It does not append a fabricated economic failure and does not change current eligibility. No hidden automatic retry is required by M9.5.

8. **Current eligibility for one Trial.** For a selected Trial, the latest append-only decision under the currently active policy is its current qualification state. If no decision exists under the active policy, current eligibility is unavailable pending evaluation. If the latest current-policy decision is `ELIGIBLE`, Kanasu may expose only its exact fixed CandidateRevision identity for M9.6 consideration. `REJECTED`, `INSUFFICIENT` and `INVALID` expose no eligible CandidateRevision. Activating a newer policy therefore makes older-policy decisions historical without deleting or rewriting them; reevaluation under the newer policy is explicit.

9. **Boundary.** `ELIGIBLE` means only that the exact CandidateRevision may be considered by future M9.6. M9.5 does not launch WFA, does not certify WFA/OOS, does not authorize qualified Paper, does not create live orders, and does not alter accepted Backtest/WFA/Paper economics. Additional qualification criteria remain deferred under DW-020.

## Example

If the active policy has `T = 50`, a verified selected Trial with 58 profitable trades among 100 completed trades is `ELIGIBLE`; 45 of 100 is `REJECTED`; 50 of 100 is `ELIGIBLE` because equality passes. A verified result with zero completed trades is `INSUFFICIENT`. If a later active policy has `T = 60`, the earlier 50-policy decision remains historical and the Trial has no current eligibility under the 60-policy until it is explicitly evaluated again.

## Stored data and implementation boundary

**Already exists and is reused:** registered StudyRevision/Trial/job/attempt/evidence lineage; immutable Backtest result and manifest artifacts; canonical Backtest result validation; the passive immutable `QualificationPolicy` value model; existing research SQLite storage and content-addressed artifact storage.

**Added by V002 implementation:** central policy registration/activation records, minimal fixed CandidateRevision records, append-only per-Trial QualificationDecision records, one selected-Trial qualification service, and a per-Trial current-eligibility query.

**Explicitly not added:** StudyRevision-wide validation runs; run-start/run-completion records; validation-run ordering/precedence; partial-run recovery; eligible-list batch materialization; HTTP/UI qualification endpoints; automatic WFA/Paper/Live actions; adaptive Candidate support; additional economic criteria.

## Acceptance checks

Focused tests must cover: no active policy; policy version/threshold immutability; monotonic policy activation; 0 and 100 threshold boundaries; exact equality and just-below threshold; profitable net P&L versus breakeven; exact rational comparison independent of Decimal context; verified zero-trade insufficiency; selected non-result-bearing Trial insufficiency; corrupt/mismatched claimed result/evidence invalidity; operational storage/read/write failure; exact fixed CandidateRevision identity; append-only decisions; reevaluation under the same policy replacing only the current view through a later decision; newer policy making older decisions historical until explicit reevaluation; no hidden winner selection; no Backtest rerun; and no WFA/Paper/Live launch.

## Historical note

Published V001 remains unchanged at `docs/design/M95_STRATEGY_VALIDATION_CRITERIA_SPEC002_V001.md`. Its embedded candidate-status label is historical wording and is not retroactively repaired by V002. V002 supersedes V001 only after this exact successor and implementation candidate is approved, published and read-back verified under the governing SOP.
