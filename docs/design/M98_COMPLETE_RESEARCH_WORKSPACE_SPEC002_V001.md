# Kanasu Trading System — M9.8 Complete Research-Workspace Integration

**Specification:** `KTS-M009-S008-SPEC002-V001`
**Milestone:** M9.8 — Complete Research-Workspace Integration
**Implementation baseline:** `035ad39c73e69e647dbf492c999424f78c9c87bc`
**Preparation state:** `M98-CAND-009` is READY/FROZEN under `SOP-G-003-V014` after the complete corrected successor passed the Candidate Readiness Gate.
**Status:** PROPOSED M9.8 behavior in `M98-CAND-009`; Independent Review 1 is pending and no implementation/publication authority exists before the remaining review and human-disposition gates.
**Supersession:** `M98-CAND-001 / KTS-M009-S008-SPEC001-V001` is withdrawn and has no behavioral authority.

## 1. Purpose

M9.8 turns the already-built research capabilities into one usable V1 research workspace.

It does not rebuild:

- Backtest economics or execution.
- Study/StudyRevision/Trial/ResearchJob persistence.
- M9.5 qualification mathematics.
- M9.6 WFA mathematics or PASS/FAIL rules.
- M9.7 qualified Paper runtime or campaign lineage.

M9.8 connects those accepted capabilities through the application/API/frontend boundary.

The primary workflow is:

```text
Study
  ↓
Backtest one exact strategy
  ↓
save authoritative evidence
  ↓
Send Strategies to WFA
  ↓
M9.5 historical qualification
  ↓
Start WFA
  ↓
M9.6 candidate-bound WFA
  ↓
Send Strategies to Paper
  ↓
M9.7 durable PaperCampaign
  ↓
Start / Stop Qualified Paper
```

No stage silently reruns an earlier stage merely to progress to the next one.

## 2. User-facing terminology

For the MVP UI, a different parameter configuration is treated as a different **strategy**.

Example:

```text
SMA 20 / 50 = Strategy 1
SMA 25 / 55 = Strategy 2
```

Internally, Kanasu retains the existing authoritative identities such as Study, StudyRevision, Trial, FixedCandidateRevision, QualificationDecision, CandidateWfaDecision and PaperCampaign. Domain objects are not renamed.

The exact research claim remains bound to its instrument, timeframe, period, data, parameters and other registered lineage even when the UI uses the simpler word “Strategy.”

## 3. Navigation and page responsibility

Top navigation represents major application modules:

```text
Home | Backtest | Replay | WFA | Paper Trading | Portfolio
```

M9.8 adds **WFA** as a top-level page.

Workflow actions belong inside their relevant pages.

The left sidebar remains for global/runtime information only. It must not contain workflow actions such as Start Backtest, Send Strategies to WFA, Start WFA, Send Strategies to Paper or Start Paper.

Frontend labels must not present static UI text as authoritative broker/backend/trading state.

## 4. Study scope

A Study groups related research work.

The Backtest page provides a Study selector and a minimal New Study action. Existing M9.4 Study creation is reused. M9.8 adds only the missing workspace-facing Study listing/read capability required by selectors. No advanced Study-management system is required.

Each page explicitly shows its selected Study. M9.8 does not require a hidden application-wide Study selection.

### 4.1 Research Version rule

MVP V1 Backtesting runs **one strategy at a time**.

Each materially different Backtest research plan under a Study becomes its own immutable StudyRevision.

Example:

```text
Study: SMA Research

Revision 1 → SMA 20/50
Revision 2 → SMA 25/55
Revision 3 → SMA 30/100
```

Multiple strategies in one Backtest launch are deferred to a future version.

An identical canonical registered plan follows existing deterministic registration/idempotency rules rather than silently creating duplicate research lineage.

## 5. Canonical instrument registry

M9.8 activates the already-built M9.3 canonical instrument/provider-binding model through a repository-controlled, data-driven registry configuration.

The implementation constructs the existing:

- `Instrument`
- `ProviderInstrumentBinding`
- `StaticInstrumentRegistry`

It does not introduce a parallel identity model.

### 5.1 Multi-instrument rule

RELIANCE is only an example/regression instrument.

Production research logic must not contain RELIANCE-specific branching.

The registry is generic and may contain any number of supported NSE cash-equity instruments. The initial repository payload contains a small reviewed starter set only; that starter set is not an architectural limit.

Any supported NSE cash-equity instrument present in the canonical registry may be selected.

The Backtest research symbol selector is derived from the canonical registry rather than the temporary legacy symbol/token map.

An unknown, missing or ambiguous instrument/binding fails closed. Kanasu never guesses an AngelOne token from ticker text.

### 5.2 Current executable provider-symbol rule

For the present accepted M9.7 runtime contract, `ProviderInstrumentBinding.provider_symbol` must equal the candidate's runtime `DatasetContext.symbol`.

Therefore the starter bindings use runtime symbols such as `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, and `SBIN`; AngelOne tokens remain separate provider identity.

Provider tokens never become Kanasu's canonical instrument identity.

The existing temporary legacy `RELIANCE → 2885` map may remain only where necessary to preserve standalone M8 compatibility. It is not registered-research authority.

Provider-binding transitions use the existing M9.3 effective-dated mechanism rather than rewriting historical bindings.

### 5.3 Bootstrap provider-master provenance

The initial five AngelOne NSE cash-equity bindings are backed by the retained repository snapshot
`config/provider_snapshots/angelone_nse_eq_starter_2026-11-08.json`.

That snapshot records the exact five authoritative master rows plus the source URL, observation time,
full-master SHA-256, byte count and record count. The corresponding provider bindings begin at that
verified observation time. Kanasu does **not** project the current daily master backward into earlier
historical periods.

A provider-backed historical request before the earliest defensible binding interval therefore fails
closed unless a separately retained historical binding snapshot establishes coverage. A future master
change closes/supersedes the prior binding through the existing M9.3 effective-dated mechanism rather
than rewriting historical provenance.

Automatic daily broker-master synchronization remains outside M9.8 implementation scope; the retained
bootstrap snapshot is the immutable starting evidence for that later startup/day-refresh mechanism.

## 6. Backtest workspace

The substantial Backtest result dashboard is preserved in the research workspace.

The primary research workflow adds Study context and uses the existing M9.4 registered-research execution machinery.

User interaction remains one simple Start Backtest action.

### 6.1 Start Backtest behavior

One click internally composes the existing accepted workflow:

```text
selected Study
      ↓
canonical selected instrument
      ↓
register one immutable StudyRevision
      ↓
register authoritative Trial population
      ↓
start existing ResearchJob queue
      ↓
execute through existing ClaimedResearchJobExecutor
      ↓
existing authoritative Backtest engine
      ↓
persist evidence/result
      ↓
display authoritative result
```

Internal registration, queue and worker operations are not separate user buttons.

The user is not required to enter internal repository revision, evidence-reuse policy, universe identity payloads, provider token or artifact identity. Application composition derives them from accepted authorities.

The registered result is projected back into the existing Backtest response semantics; React does not recalculate financial results.

### 6.2 Existing standalone Backtest

The existing standalone M8 Backtest API/component remains regression-compatible and unchanged in-tree.

It must not be represented as registered M9 progression evidence unless execution actually occurred through the registered-research path.

### 6.3 Retry

Existing M9.4 Trial retry semantics are reused.

A FAILED/CANCELLED/INTERRUPTED Trial may be retried without creating a different strategy or StudyRevision.

Changing strategy parameters, instrument, research period or another identity-affecting research input creates a different registered research claim.

## 7. Send Strategies to WFA

The Backtest page contains `Send Strategies to WFA`.

This action operates only on completed saved Backtest strategies belonging to the currently selected Study. It does not scan every historical Backtest in Kanasu and it does not rerun Backtest.

### 7.1 Qualification dialog

The dialog shows the sole MVP V1 historical economic criterion:

```text
Profitable Trade Rate ≥ T %
```

No additional qualification criteria are introduced. DW-020 remains deferred.

### 7.2 QualificationPolicy authority

M9.5's centrally active immutable versioned `QualificationPolicy` remains authoritative.

The threshold supplied through this UI is not passed directly into individual M9.5 evaluation calls.

If the selected threshold equals the active policy threshold, reuse the active policy.

If it differs, atomically create the next immutable policy version and activate it before evaluation.

Policy-version selection and activation are backend-owned. React does not calculate the next version number.

Policy registration/activation is concurrency-safe and repeated/concurrent requests must not create conflicting active versions.

Any store API that claims to return the **current** qualification decision resolves the active policy and the latest decision for the Trial inside one coherent SQLite read snapshot. A policy activation cannot be observed on one connection while the decision is read from a different snapshot.

### 7.3 Global-policy consequence

The active qualification policy is global for MVP V1, not Study-specific.

Changing the threshold makes previous-policy decisions historical across Kanasu.

Only the currently selected Study is immediately reevaluated. Other Studies remain pending reevaluation under the new active policy.

The UI warns the user before activating a changed global threshold.

### 7.4 Study-level orchestration

M9.8 orchestrates over the Study, but every strategy is still evaluated through the existing M9.5 per-Trial service.

Each QualificationDecision remains independently attributable.

A failure to evaluate one strategy is not converted into a fabricated economic REJECTED decision. Already completed immutable decisions remain preserved.

## 8. WFA workspace

M9.8 adds a WFA page.

`Start WFA` operates on the selected Study's strategies that are currently eligible under the active M9.5 policy.

Internally, M9.8 orchestrates across applicable StudyRevisions while reusing `CandidateWfaService.evaluate_study_revision(...)`.

M9.6 mathematics and persistence are not rewritten.

Because MVP Backtesting contains one strategy per Research Version, each eligible Research Version can be processed independently.

### 8.1 WFA failures

Independent strategies remain independent.

An operational error is not a WFA FAIL.

Successful decisions already persisted remain authoritative.

M9.8 does not introduce a new WFA batch-state machine merely to represent Study-level orchestration.

## 9. WFA result display

The WFA page displays authoritative metrics read from existing M9.6 evidence.

The frontend does not recalculate WFA financial metrics or PASS/FAIL.

For the selected strategy, the MVP displays:

- consistency;
- average OOS account return;
- worst OOS equity drawdown;
- stitched OOS return;
- stitched maximum drawdown;
- account-return stability;
- overall WFA verdict.

Advanced research visualizations, heatmaps and analytics terminals are outside M9.8 MVP.

## 10. Fixed WFA → Paper criteria

The existing M5/M9.6 WFA verdict remains the only WFA→Paper admission rule.

When the user activates `Send Strategies to Paper`, the UI displays the fixed existing rules:

```text
Consistency                    ≥ 60%
Average OOS account return     > 0
Worst OOS equity drawdown      ≤ 20%
Stitched OOS return            > 0
Stitched maximum drawdown      ≤ 20%
Account-return stability       ≥ 0.20
```

These controls are display-only and cannot be individually enabled, disabled or edited in MVP V1.

The backend's existing authoritative WFA PASS remains the decision. The UI never independently recomputes PASS/FAIL from rounded display numbers.

## 11. Send Strategies to Paper

`Send Strategies to Paper` considers only current strategies in the selected Study with authoritative VALID + PASS + ELIGIBLE WFA state.

M9.8 creates or reuses M9.7 `PaperCampaign` records.

### 11.1 Duplicate safety

Repeated or concurrent Send actions must not create duplicate campaigns for the same exact current authority.

Matching identity is the exact CandidateRevision, current WFA decision and M9.7 configuration fingerprint.

If a matching campaign exists it is reused; otherwise it is created.

If historical qualification or WFA authority changes, the old campaign remains immutable historical evidence and does not silently adopt the new authority. A new currently valid campaign may then be created.

The final current-M9.5/current-M9.6 authority check and campaign reuse/insert share the same `BEGIN IMMEDIATE` write transaction. A service-level preflight alone is insufficient: policy or WFA supersession between preflight and durable persistence must fail closed without persisting or reusing stale current authority.

`Send Strategies to Paper` does not automatically start Paper Trading.

## 12. Paper Trading page

M9.8 retains one top-level **Paper Trading** page with two clearly separated modes:

```text
Qualified Research | Standalone Smoke
```

Default mode is `Qualified Research`.

### 12.1 Qualified Research mode

Qualified Research uses the existing M9.7 `QualifiedPaperCampaignApplication`.

The user selects a Study and current campaign, then explicitly starts/stops Paper Trading.

Campaign history remains durable. A campaign may contain multiple Paper sessions.

### 12.2 Standalone Smoke mode

The current M8 standalone start/status/stop application workflow remains available and regression-compatible.

It is visibly identified as operational smoke testing only and not research-qualified.

Standalone sessions cannot satisfy M9.7 research progression evidence.

### 12.3 Runtime ownership

The existing single process-local Paper runtime ownership remains authoritative.

Qualified and standalone modes must not create simultaneous conflicting Paper runtimes.

### 12.4 Stale authority

M9.7's authority recheck before every qualified session remains mandatory.

A stale campaign is blocked rather than silently updated.

Durable qualified-session registration is the admission linearization point. The exact expected current M9.5 qualification and M9.6 WFA decision are revalidated inside the same `BEGIN IMMEDIATE` transaction that inserts the session. If authority supersedes between preparation and registration, the session is not persisted and the Paper worker is not started.

Qualified Stop is identity-bound: immediately before mutating runtime lifecycle state, the process-local application compares the expected durable qualified session id with the currently owned runtime session id under the lifecycle lock. A different runtime is never stopped by a stale qualified request.

### 12.5 Session-continuity boundary

DW-021 remains deferred.

M9.8 does not aggregate multiple Paper sessions and present them as one continuous restored account.

No fabricated cross-restart position/cash/strategy state is introduced.

## 13. Backend authority and frontend boundary

React is presentation/orchestration UI only.

The backend remains authoritative for research identities, Study/StudyRevision/Trial state, Backtest results, QualificationPolicy, qualification decisions, Candidate identity, WFA metrics, WFA PASS/FAIL, Paper admission, campaign identity, Paper runtime/session state and account/position/execution state.

Frontend async reads are generation-fenced. Every Study mutation that can produce fresher strategy state (New Study, Start Backtest, Retry, Qualification) invalidates earlier Study reads before committing its result. Qualified-Paper polling is single-flight per generation: the next poll is scheduled only after the prior request settles, and Study/campaign/action generation changes invalidate older responses. A terminal STOPPED observation cannot regress to RUNNING because of out-of-order same-generation responses.

The frontend does not reconstruct financial or eligibility truth.

## 14. Failure and partial-operation semantics

M9.8 distinguishes:

- economic rejection;
- insufficient evidence;
- invalid evidence/lineage;
- operational failure;
- runtime failure.

These are not collapsed into one FAIL.

Study-level actions may produce partial outcomes because underlying strategy decisions are independently durable.

Completed immutable evidence is not rolled back merely because another strategy fails.

No hidden automatic retries are introduced.

## 15. Idempotency and concurrency

The following user actions tolerate repeated/concurrent requests safely where the underlying accepted authority permits it:

- deterministic registered Backtest Start;
- qualification using an unchanged policy;
- activation of a changed global qualification threshold;
- Study-level WFA orchestration;
- Send Strategies to Paper;
- Paper start/stop lifecycle operations.

Where an operation cannot safely repeat, the API returns a truthful conflict rather than creating duplicate or contradictory state.

## 16. Four-ply consequence analysis

### Ply 1 — Direct effects

M9.8 directly adds or connects:

- canonical registry configuration/loading;
- Study list/read workspace surface;
- registered-research Backtest application composition;
- qualification policy/workspace orchestration;
- Study-level WFA orchestration;
- WFA read/API/frontend page;
- qualified Paper HTTP/read surfaces;
- duplicate-safe campaign lookup/creation;
- Paper page qualified/standalone modes;
- WFA navigation.

### Ply 2 — Immediate dependent surfaces

Changes may affect API models/routes/application composition, bounded SQLite read/write helpers, frontend API clients/types/pages, startup composition, documentation/status/roadmap and focused tests.

### Ply 3 — Secondary consequences

M9.8 preserves:

- standalone M8 Backtest behavior;
- standalone M8 Paper behavior;
- M9.4 registered population/queue/retry/recovery authority;
- M9.5 active-policy and append-only decision semantics;
- M9.6 exact historical-decision binding;
- M9.6 fixed WFA verdict semantics;
- M9.7 stale-authority rejection;
- M9.7 one-active-qualified-session rule;
- content-addressed evidence identities;
- canonical instrument/provider separation.

### Ply 4 — Adversarial consequences

Implementation/Review 1 and Review 2 challenge at least:

- double-click Start;
- concurrent qualification-policy changes;
- same threshold submitted repeatedly;
- policy activation succeeds but one strategy evaluation fails;
- no active policy;
- missing/corrupt Backtest evidence;
- Study containing failed/interrupted Backtests;
- WFA eligibility becoming stale during operation;
- WFA operational error versus economic FAIL;
- missing/corrupt WFA artifact;
- duplicate Send-to-Paper requests;
- old campaign after new historical/WFA decision;
- missing/ambiguous current AngelOne binding;
- provider token transition;
- unknown symbol;
- application restart during research execution;
- restart during qualified Paper;
- standalone Paper already running when qualified Paper starts;
- qualified Paper already running when standalone start is requested;
- frontend navigation while operations are active;
- malformed IDs;
- persistence failure after runtime start or terminalization.

Review question:

> If an independent reviewer follows this action three or four consequences downstream, can any stale, duplicate, fabricated or incorrectly classified authority appear?

The required answer is no.

## 17. Explicit non-goals / deferred work

M9.8 MVP V1 does not add:

- multiple strategies in one Backtest launch;
- parameter-grid generation;
- automatic strategy optimizer;
- additional M9.5 qualification criteria;
- configurable multi-rule qualification builders;
- editable WFA PASS rules;
- alternative WFA mathematics;
- automatic Paper start after WFA;
- instrument-management administration UI;
- automatic broker-master synchronization;
- autonomous AI research;
- multi-user/role management;
- distributed workers;
- options/futures;
- real-money trading;
- Paper→Live qualification;
- continuous restored Paper account state across sessions/restarts;
- advanced visualization/analytics terminal;
- commercial-platform infrastructure.

## 18. Documentation synchronization

The controlled M9.8 implementation synchronizes current-state documentation:

```text
M9.7 → DONE/CLOSED at 035ad39c73e69e647dbf492c999424f78c9c87bc
M9.8 → ACTIVE
M9.9 → PLANNED
```

Historical review records are not rewritten.

## 19. Acceptance conditions

M9.8 is behaviorally acceptable only if all of the following are demonstrated:

1. User can create/select a Study through the workspace.
2. Registered-research Backtest accepts a canonical registered NSE cash-equity instrument.
3. Production research code is not RELIANCE-specific.
4. One Start Backtest executes one strategy through existing M9.4 registered research.
5. Backtest evidence/result is durable and visible.
6. Multiple separately run strategies can coexist under one Study.
7. Send Strategies to WFA considers only completed strategies in the selected Study.
8. The sole M9.5 profitable-trade-rate criterion remains authoritative.
9. Changed threshold creates/activates a new immutable global policy version atomically.
10. Current-policy qualification decisions remain individually attributable.
11. Start WFA processes all currently historically eligible strategies in the selected Study through existing M9.6.
12. WFA metrics and PASS/FAIL displayed in the UI come from authoritative M9.6 evidence.
13. The six WFA verdict rules are fixed/display-only.
14. Send Strategies to Paper admits only current VALID/PASS/ELIGIBLE strategies.
15. Repeated/concurrent Send-to-Paper does not create duplicate current campaigns.
16. Qualified Paper can start/stop using existing M9.7 runtime/application authority.
17. Campaign/session history survives reconstruction/restart according to existing M9.7 rules.
18. Standalone Paper remains available and clearly non-qualified.
19. Stale qualification/WFA/campaign authority fails closed at the durable campaign/session write boundary.
20. Current qualification/WFA reads are snapshot-coherent and cannot combine authority from different policy generations.
21. Study mutations fence older frontend reads and qualified-Paper polling is single-flight per generation.
22. Qualified Stop is bound to the exact active session identity under the runtime lifecycle lock.
20. Existing Backtest/WFA/Paper economics remain unchanged.
21. Existing relevant M8/M9.4/M9.5/M9.6/M9.7 regression suites remain green.
22. New API/frontend integration tests cover success, empty, partial, stale, duplicate, failure and restart states.
23. Documentation is synchronized to the actual accepted milestone state.

## 20. Final MVP workflow

```text
                    STUDY
                      │
                      ▼
                 BACKTEST PAGE
                      │
         select canonical instrument
         configure one exact strategy
                      │
               [Start Backtest]
                      │
              saved evidence/result
                      │
          [Send Strategies to WFA]
                      │
          global M9.5 policy T
                      │
       eligible strategies in Study
                      │
                      ▼
                   WFA PAGE
                      │
                 [Start WFA]
                      │
           existing M9.6 WFA
                      │
              PASS / FAIL results
                      │
       [Send Strategies to Paper]
                      │
       fixed WFA criteria displayed
                      │
        create/reuse PaperCampaigns
                      │
                      ▼
              PAPER TRADING PAGE
                      │
              Qualified Research
                      │
          select strategy/campaign
                      │
           [Start Paper Trading]
                      │
            real market data
          + simulated execution
                      │
            [Stop Paper Trading]
                      │
             durable history
```

This is the complete behavioral scope of M9.8 MVP V1.
