# M9.5 — Strategy Validation Criteria

**Specification:** `KTS-M009-S005-SPEC002-V001`

**Candidate:** `KTS-M009-S005-SPEC002-V001-CAND005` — proposed; not approved or published

**Design basis:** AD-026 at `68d1f6543ec3f5271fb3cb0529b27feb9cd99b33`

**Scope:** M9.5 strategy validation only. M9.6 remains a future consumer.

## What happens

```text
Existing Backtest → saved result and evidence
                        ↓
M9.5 requested for a specific registered StudyRevision
                        ↓
Load active centrally defined QualificationPolicy
                        ↓
Find that StudyRevision's registered Trials
                        ↓
For each Trial, resolve its exact saved Backtest result
                        ↓
Verify result/evidence → derive profitable-trade percentage
                        ↓
Apply the one validation criterion
                        ↓
Save each Trial's attributable QualificationDecision
in a durably identified validation run
                        ↓
Only a fully completed run exposes current eligibility
for its exact StudyRevision and active policy
                        ↓
          Future M9.6 (not designed here)
```

## Behavior — step by step

1. **Central rule.** Kanasu loads the active, immutable, versioned `QualificationPolicy` from a central place. The policy already contains the predefined percentage `T`; no one enters a percentage during validation. An authorized human determines the initial configured value **before the policy is activated**. `T` must be a finite number from 0 through 100 inclusive. No universal 50% value is assumed. If no valid active policy exists, validation stops without marking any result eligible.
2. **Find existing results.** When validation is requested for a specified registered `StudyRevision`, Kanasu examines its registered Trials. Only completed, result-bearing Trials are evaluated; pending, failed and otherwise uncompleted Trials retain their true research status without a fabricated qualification. Each result-bearing Trial is identified by its exact fixed strategy configuration and saved Backtest result. No manual shortlist, best-Trial selection or merging of independent results is required.
3. **Check saved evidence.** For each result-bearing Trial, Kanasu reuses existing authoritative research-catalog and artifact-verification checks to establish that the Backtest result and its identity are trustworthy. A reliably established missing required result is `INSUFFICIENT`; corrupted evidence or mismatched identity is `INVALID` on the evidence-validity axis. Neither outcome is eligible, and the economic comparison is not performed. A database outage, permission denial or other inability to perform reliable verification is an **operational error**, not evidence classified as missing or invalid; follow Step 9.
4. **Read the metric.** The Backtest has already calculated performance metrics for its API response and saved the underlying trades, bar records and equity history. M9.5 **does not run Backtest again**. From the verified saved trades, it derives `net_profitable_trade_rate_pct` using the existing Backtest definition: completed trades with monetary net P&L strictly greater than zero divided by all completed trades, multiplied by 100. Losing and breakeven trades remain in the denominator. Zero completed trades is `INSUFFICIENT` even if `T = 0`.
5. **Evaluate.** The only economic validation condition is `net_profitable_trade_rate_pct >= T`. Compare the actual unrounded value against the exact saved policy threshold. With valid, sufficient evidence: at or above `T` is `ELIGIBLE`; below `T` is `REJECTED`. Keep evidence validity, the criterion outcome and the final qualification decision distinguishable.
6. **Save the result.** After resolving the active policy and registered `StudyRevision`, Kanasu first attempts to save and confirm a unique validation **run-start record** identifying the `StudyRevision`, policy version, initiation order and run ID. A request becomes an **initiated run only when this start record is durably committed and verified**; no Trial evaluation or decision is written before this boundary. For each assessed Trial in an initiated run, Kanasu appends one `QualificationDecision` with its outcome/reason, run identity, time/evaluator version, `StudyRevision` and Trial identities, policy version and threshold, and whichever saved-result/evidence/attempt and fixed `CandidateRevision` identities have actually been verified. Completed/profitable counts and the actual rate are recorded **only if they can be reliably established**; otherwise they are explicitly **unknown**, never invented or silently recorded as zero. For a verified zero-trade result, counts are zero but the rate is undefined and the decision is `INSUFFICIENT`. A missing/corrupt result or unproven Candidate identity gives a non-eligible, Trial-traceable decision without a fabricated CandidateRevision. A failure to identify the Trial itself is an operational error, not a fabricated decision.
7. **Provide current eligibility.** A validation run covers the specified `StudyRevision`'s complete registered Trial population, retaining non-result-bearing Trial statuses, and completes only after all applicable Trial outcomes and its own completion are durably recorded. The **latest durably initiated run**, ordered by its stored initiation sequence for that `StudyRevision`, governs current eligibility only if it completed successfully under the **currently active policy**; its one decision per Trial then determines the current view. If a newer durably initiated run is incomplete or has failed, or if the active policy has changed without a matching completed run, current eligibility is **unavailable pending successful revalidation**, not the older eligible list. If a subsequent validation request fails **before** its run-start record is durably saved, that request was **not initiated** and cannot override the last completed run: after reliable storage recovery, the previous decision remains current if its policy is still active and no newer initiated run exists. While storage cannot be reliably inspected, no current eligibility is reported. Earlier records remain historical. Only verified `ELIGIBLE` fixed `CandidateRevision` identities from the complete governing run are exposed; the list is derived, not editable or separately saved. M9.5 does not start WFA or specify M9.6 processing.
8. **Policy changes.** A changed threshold is introduced by a new authorized, immutable policy version; any additional economic criteria would require a separately approved future design. The next requested validation uses the then-active version and creates new decisions; earlier Backtests, policies and decisions remain unchanged. Until a complete validation run is saved under the new active policy, there is no current eligible list for that StudyRevision; prior-policy decisions remain historical only.

9. **Operational errors.** An unavailable database/service, permission error, failed required read, failed decision write or failed run-completion write is reported as `OPERATIONAL_ERROR`, never as a failed economic criterion. **Before run-start commitment:** failure is a **rejected start**; no run or persistent eligibility invalidation may be claimed. If the start write may have committed but the acknowledgement failed, Kanasu must reconcile durable run-start evidence after storage recovery before reporting any current eligibility; it must not assume either that the request started or that it did not. **After confirmed run start:** an operational failure stops the whole run; its durable incomplete/failed run supersedes earlier successful runs for the current eligibility view until a newer run completes successfully. Saved partial decisions remain attributable history, never a qualified list. Kanasu reports known failures/progress truthfully, never asserts that an unsaved error or terminal record persisted, and does not silently retry or promote any strategy. A further successful validation is necessary **only where a newer initiated run is incomplete/failed, or the active policy has changed**; a rejected start alone does not erase an earlier completed decision.

## Example

For illustration only, suppose the active policy uses `T = 50%`. A verified Backtest with 58 profitable trades among 100 completed trades is **ELIGIBLE**; one with 45 among 100 is **REJECTED**. A result with no completed trades is **INSUFFICIENT**. When the active policy later becomes `T = 60%`, the 58% result is rejected **on reevaluation**, while its previous 50%-policy decision remains in history. These example values do not prescribe the initial configured threshold.

## Stored data and boundary

**Already exists:** Backtest result artifacts in the configured research-artifact store; Study/Trial/attempt/evidence identity in the research SQLite database; the authoritative profitable-trade calculation. The canonical saved Backtest result contains underlying trades, bar records and equity curve, **not a separate saved `net_profitable_trade_rate_pct` field**.

**To implement in M9.5 after separate approval:** a central versioned `QualificationPolicy`, an evaluation service using saved evidence, append-only `QualificationDecision` persistence, fixed CandidateRevision lineage, and a query for current eligibility. Use the existing configured research storage; do not introduce competing copies of original Backtest results.

**Boundary:** M9.5 only qualifies saved registered historical Backtests for *consideration* by the later research stage. No automatic WFA launch, Paper/Live trading, unregistered-result promotion or alteration of existing Backtest/WFA economics is authorized by this specification. The central deferred-work ledger requires its separately controlled synchronization **before production implementation**.

**Acceptance checks:** policy missing/invalid; 0 and 100 threshold boundaries; equality; just-below threshold; positive net P&L versus breakeven; zero trades with undefined rate; verified, missing and invalid evidence; unknown versus verified counts/identities; multiple independent registered Trials without winner-picking, including non-result-bearing statuses; exact candidate/evidence lineage; append-only decisions; later non-eligible reevaluation overriding earlier eligibility in the current view; new policy and stale/incomplete-run handling; rejected starts before durable run creation retaining prior valid eligibility; committed start followed by failure blocking stale eligibility; ambiguous commit reconciliation and restart recovery; database/permission/write failures producing operational errors without partial eligibility; and no WFA/Paper/Live execution. This is human-language behavior, not implementation approval.

**Numbering history:** An earlier M9.5 `SPEC001` proposal about `StudyRevision` protection was withdrawn because that behavior already existed. CAND001, CAND002, CAND003 and CAND004 of this `SPEC002-V001` were unapproved and unpublished proposals; this candidate supersedes them as a proposal, not as an active published specification.
