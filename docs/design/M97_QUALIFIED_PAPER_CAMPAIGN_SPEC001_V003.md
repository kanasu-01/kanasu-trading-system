# M9.7 — Qualified Persistent Paper Campaigns and Operational Continuity

**Specification:** `KTS-M009-S007-SPEC001-V003`
**Milestone:** M9.7
**Status:** PROPOSED for human review. This wording does not authorize implementation until the exact canonical candidate completes the controlled Review-1 and human-approval process.
**Purpose:** Admit only an exact currently qualified fixed CandidateRevision into research-qualified Paper Trading, run that candidate through the already accepted real-market-data Paper runtime with simulated execution, and preserve durable campaign/session lineage across application restarts without inventing missing market observations, fills or trading state.

## 1. Human-language concepts

### WFA Eligible Strategy

A **WFA Eligible Strategy** is the exact fixed CandidateRevision whose current M9.6 decision is valid, has the existing WFA `PASS` verdict and is `ELIGIBLE`, and whose supporting M9.5 historical qualification remains the current eligible decision for that same CandidateRevision.

A prior WFA pass is not sufficient when the current historical qualification authority has changed or when a later WFA decision makes the CandidateRevision non-eligible.

### Qualified Paper Campaign

A **Qualified Paper Campaign** is one durable forward-observation record bound to one exact WFA Eligible Strategy and the exact WFA decision that admitted it.

A campaign is not a new strategy, does not change the candidate, and does not create a new economic qualification rule. It is the durable container that groups one or more later Paper runtime sessions performed under that same qualified research claim.

### Paper Session

A **Paper Session** is one existing M7/M8 runtime episode using real AngelOne market data and simulated Kanasu execution/accounting. Each session keeps its existing unique runtime/session identity and per-session journal identity.

### Operational continuity

For MVP V1, **operational continuity** means that the campaign identity, exact research lineage, individual session identities, live-provider binding used by each session, terminal Paper snapshots, failures and interruption records survive application restart and can be retrieved later.

Operational continuity does **not** mean that an in-memory strategy, pending intent, open simulated position, cash/equity state or provider socket is resumed after a process restart.

## 2. Progression rule

The M9 research progression remains:

`Historical Backtest -> M9.5 historical qualification -> M9.6 candidate-bound WFA -> M9.7 qualified Paper campaign`

M9.7 may create a qualified campaign only for an explicitly named exact CandidateRevision. It must never scan for a winner, automatically select a strategy, or automatically start Paper Trading merely because M9.6 produced `ELIGIBLE`.

The existing standalone M8 Paper API remains an **operational-smoke Paper path**. It may still run supported Paper sessions, but those sessions are not research-qualified campaigns and cannot satisfy M9.7 progression evidence.

## 3. Exact admission authority

Before a qualified campaign is created, Kanasu must establish all of the following from authoritative durable state:

1. the exact fixed CandidateRevision exists;
2. its latest candidate-bound WFA decision is `VALID`, has WFA verdict `PASS`, and outcome `ELIGIBLE`;
3. the WFA decision names that exact CandidateRevision, StudyRevision and Trial;
4. the M9.5 historical qualification decision referenced by that WFA decision is still the current decision under the currently active QualificationPolicy for that Trial, is still `ELIGIBLE`, and still names the same CandidateRevision;
5. the registered Trial, StudyRevision plan, ExperimentSpec and parameter-configuration fingerprint still match the CandidateRevision;
6. the exact registered executable inputs can be reconstructed through the existing registered-plan/input authority and pass the existing `ClaimedTrialExecutionInputs` validation;
7. the saved WFA result artifact physically exists, has the M9.6 WFA-result kind/schema, its bytes match the catalog byte count, it decodes under the existing M9.6 canonical validator, and its Candidate/Trial/StudyRevision/historical-decision, ExperimentSpec, admitted dataset, WFA-configuration, evaluator-revision, verdict, requested-range, strategy-parameter, initial-capital, risk/economic and data-treatment fields match the current WFA decision and exact registered candidate inputs;
8. the current software repository revision is positively known and the executable worktree is clean; and
9. the existing M9.6 executable-compatibility rule confirms that the candidate's non-research executable core has not changed incompatibly since the registered ExperimentSpec revision.

A missing, contradictory or non-eligible authority prevents campaign admission. A deterministic missing/corrupt/contradictory authority is an admission failure; a database, permission, Git, non-missing filesystem or other infrastructure failure that prevents reliable verification is an operational failure and must not be converted into a qualification rejection or fabricated campaign. Operational classification follows the causal exception chain so a wrapped SQLite, permission or non-missing `OSError` remains operational.

M9.7 does not rerun M9.5 or M9.6 mathematics during admission.

## 4. Immutable campaign identity and configuration binding

Campaign creation stores one immutable campaign record containing at least:

- campaign ID and creation time;
- exact CandidateRevision ID;
- exact admitting WFA decision ID;
- StudyRevision ID;
- Trial ID;
- ExperimentSpec ID;
- parameter-configuration fingerprint;
- one deterministic campaign-configuration fingerprint; and
- the exact clean repository revision observed at campaign creation.

The campaign-configuration fingerprint is derived canonically from the exact candidate/research inputs required for Paper execution: CandidateRevision and WFA decision identities, StudyRevision/Trial/ExperimentSpec, strategy procedure, canonical instrument ID, candidate symbol, timeframe, timezone, initial capital, exact registered strategy parameters, complete registered risk/economic configuration, data-treatment basis, registered historical provider, price-adjustment basis and registered repository revision.

The fingerprint is evidence of the exact frozen campaign claim. It does not replace the underlying registered records.

The live provider token/binding is **not** frozen once for the entire campaign because provider bindings are effective-dated and may legitimately change later. Each session records the exact live binding actually used.

## 5. Recheck before every new Paper session

A campaign does not grant permanent permission to start sessions without revalidation.

Before every session preparation, Kanasu must repeat the current authority checks in Section 3 and require:

- the same WFA decision ID that originally admitted the campaign remains the current WFA decision for the candidate;
- the current M9.5 decision still matches the historical decision referenced by that WFA decision;
- all immutable Candidate/Trial/ExperimentSpec/configuration identities still match the campaign;
- the campaign-configuration fingerprint recomputes identically;
- current software identity is exact and clean; and
- the candidate remains executable-compatible under the existing M9.6 rule.

If a new WFA decision, a new active historical policy/decision, a changed candidate identity or incompatible executable change appears, the old campaign cannot silently adopt it. The operator must use the separately controlled research process and, when appropriate, create a new campaign.

## 6. Exact current live-instrument binding

Qualified Paper Trading must not infer that a trading symbol/token represents the same canonical instrument merely because names look similar.

For each session, M9.7 resolves exactly one currently effective `angelone` provider binding from the accepted M9.3 `StaticInstrumentRegistry` for the campaign's canonical instrument ID.

The binding must:

- be uniquely applicable at session preparation time;
- identify the same canonical instrument as the registered Trial;
- identify AngelOne as provider;
- contain an explicit NSE exchange, provider symbol and provider instrument/token ID; and
- use the same symbol as the candidate's validated DatasetContext.

Missing, ambiguous, expired, future, timezone-incompatible or contradictory bindings block session preparation. M9.7 does not fall back to the temporary hard-coded AngelOne token map for a qualified campaign.

The exact binding ID, provider, provider instrument/token ID and provider symbol used are stored with the durable session record.

## 7. Exact candidate execution inputs

The qualified Paper path must use the exact validated `ClaimedTrialExecutionInputs` belonging to the candidate.

It must not rebuild the strategy from the ordinary Paper API's default `BACKTEST_CONFIG`, silently substitute default SMA periods, substitute another strategy alias, replace the registered initial capital, replace risk/economic settings, or substitute another timeframe/timezone.

The initial MVP qualified Paper path supports the already certified V1 execution timeframes `5m` and `15m` only, requires the candidate's registered time semantics to be `Asia/Kolkata`, and requires the candidate's registered historical provider to be `angelone`. These are the minimal supported real-market-data Paper operating envelope, not additional economic qualification gates.

M9.7 does not add a new strategy implementation or change strategy mathematics.

## 8. Real market data and simulated execution

A qualified session reuses the accepted M7/M8 Paper runtime:

`AngelOne real market data -> AngelOneLiveCandleFeed -> LivePaperRuntime -> PaperCandleProcessor -> StrategyRunner -> simulated TradeExecutionEngine -> authoritative PortfolioManager -> PaperTradingSession`

The AngelOne broker object used by this path remains `paper_mode=True` and is used to establish market-data capability. M9.7 adds no real-money order-routing call.

The live feed is configured from the exact current M9.3 provider binding instead of the temporary default token map. Session-wall-clock evaluation is normalized to `Asia/Kolkata`, matching the existing AngelOne live-market timestamp basis, before the accepted M7 same-day session-window logic is applied.

The existing M7 causal next-bar execution, reconnect/reconciliation policy, protection behavior, runtime supervision, execution economics, risk behavior, portfolio accounting and PaperTradingSession snapshot authority remain unchanged.

## 9. Canonical historical warm-up and live-gap reconciliation

The qualified path must not use an unrelated legacy symbol cache to warm the strategy or repair a live provider gap.

Historical warm-up and the existing M7 live-gap reconciliation use an adapter bound to the candidate's canonical instrument ID, registered `angelone` historical provider and price-adjustment basis and call the accepted M9.3 successor/binding-aware historical retrieval service.

The existing M7 rule remains unchanged: recovered historical candles may rebuild strategy state during reconciliation but cannot retrospectively create a live entry, pending intent or fill and cannot manufacture observations that were not received or authoritatively recovered.

## 10. Durable session registration and one-active-session rule

Before the Paper worker is allowed to start, M9.7 durably registers one session record in `CREATED` state after the existing process-local Paper owner has accepted the start operation.

The durable store permits at most one qualified session in `CREATED` or `RUNNING` state at a time. The existing `PaperTradingApplication` also continues to permit at most one process-local Paper runtime at a time.

The durable session record contains:

- runtime session ID;
- campaign ID;
- durable creation time;
- current evaluator repository revision;
- exact live-provider binding identity/details; and
- lifecycle state.

After worker startup, M9.7 records durable `RUNNING` only when the authoritative immediate Paper start response itself reports `RUNNING`. If that response still reports `CREATED` because the worker has not yet advanced the runtime lifecycle, M9.7 does not manufacture a `RUNNING` observation; the durable session remains `CREATED` until later terminal evidence or restart interruption. A very short session may also reach a terminal state before a separate durable `RUNNING` observation is recorded; the immutable terminal Paper snapshot remains the authoritative runtime lifecycle evidence in that case.

A failure to create or start the worker after durable registration, while the authoritative Paper session is still `CREATED`, terminalizes the registered session as `FAILED`; it must not leave a false active campaign session. An exception raised after the worker has advanced the authoritative Paper session to `RUNNING`, `STOPPED` or `FAILED` is not a worker-start failure and must not be reclassified by M9.7.

## 11. Durable terminal evidence

When the existing Paper runtime ends normally, the campaign session becomes `STOPPED` and stores the exact immutable `PaperTradingSession.snapshot()` in deterministic JSON form.

When the existing Paper runtime fails, the campaign session becomes `FAILED`, preserves the exact terminal snapshot when the runtime produced one, and preserves the authoritative failure type/message. A legitimate empty exception message, such as `TimeoutError()`, is preserved as an empty string rather than treated as missing failure evidence when the authoritative failure type is present.

The terminal snapshot retains the accepted Paper authority for cash, position, equity, P&L, drawdown, completed-trade count, active-position information and latest execution information.

If terminal snapshot persistence itself fails, the application must surface that as an operational persistence failure. It must not report durable campaign continuity as successful merely because the in-memory runtime stopped, and it must not overwrite the observed authoritative `STOPPED` or `FAILED` runtime outcome with a fabricated durable `FAILED` record. If no terminal evidence could be durably written before process loss, later restart recovery may truthfully classify the still-active durable record as `INTERRUPTED` because durable authority never obtained the terminal snapshot.

The existing per-session CSV/JSONL trade journal remains keyed by the same runtime session ID. M9.7 does not create a second trade journal format.

## 12. Application restart and `INTERRUPTED`

At application startup, every durable qualified session left in `CREATED` or `RUNNING` by an earlier process is changed to terminal `INTERRUPTED` with an explicit interruption reason. Its durable interruption time is the restart observation time unless that would precede the already stored session creation/start chronology, in which case the latest stored lifecycle boundary is used so recovery never creates impossible time ordering.

No terminal Paper snapshot is fabricated for that interruption because the old in-memory runtime/account state is unavailable.

The restart recovery does not:

- recreate or resume a provider socket;
- resurrect an old pending intent;
- reopen or recreate an old simulated position;
- infer missing fills from historical OHLC;
- infer missing market observations;
- continue the old strategy object's internal state; or
- pretend that the interrupted session stopped cleanly.

After interruption, the same campaign may later start a **new** Paper session only after all current admission/session checks pass again.

## 13. Session-boundary economics for MVP V1

Each M9.7 Paper session remains one existing authoritative M7 simulated account episode and starts with the exact registered candidate initial capital.

M9.7 does not carry cash, equity, open positions, pending intents or strategy object state from one Paper session into another.

Therefore the campaign is a durable research lineage/history container, not a continuous shared account. Kanasu must not sum session P&L, compound session returns or combine session drawdowns and present them as one continuous campaign portfolio/account result.

This limitation is explicit. True cross-session/cross-restart account checkpointing is deferred separately and becomes necessary before Kanasu claims uninterrupted multi-day/overnight Paper-account continuity.

## 14. Retrieval and history

A campaign and its ordered session history must survive application restart and be reloadable from the research database.

History preserves terminal `STOPPED`, `FAILED` and `INTERRUPTED` sessions rather than deleting or replacing them when a later session is started.

Campaign records are immutable. Session lifecycle transitions are monotonic: `CREATED -> RUNNING -> STOPPED/FAILED` or `CREATED/RUNNING -> INTERRUPTED` at restart recovery. Once `RUNNING` is durably recorded, its start time is immutable. Terminal state, terminal time, terminal snapshot and failure evidence are append-only: an idempotent repeat of the exact same terminal evidence may be reread, but `STOPPED`, `FAILED` or `INTERRUPTED` cannot be rewritten into a contradictory terminal state, time or evidence.

## 15. Existing operational-smoke Paper path remains distinct

M9.7 does not remove or silently relabel the existing M8 `/api/paper-trading` start/status/stop workflow.

That workflow continues to represent standalone operational Paper capability and existing frontend behavior. It is not evidence that a CandidateRevision passed M9.5/M9.6 and cannot create a qualified PaperCampaign.

The only existing Paper application change required by M9.7 is a generic prepared-runtime start hook that allows a qualified caller to register durable state immediately before worker start and persist the terminal immutable snapshot after worker completion. Existing M8 start/status/stop semantics must remain regression-compatible.

## 16. M9.8 boundary

M9.7 implements the qualified campaign domain, persistence, restart handling and application composition seam.

M9.7 does **not** add the complete public research HTTP/UI workflow for selecting a WFA-eligible candidate, creating a campaign, starting/stopping campaign sessions or browsing campaign history. M9.8 owns that research-workspace integration.

No public endpoint may claim qualified campaign authority until it is separately implemented against the M9.7 service.

## 17. Failure semantics

M9.7 keeps these conditions distinct:

- **not qualified / stale authority:** deterministic admission failure; no campaign/session is started;
- **missing or contradictory registered lineage/binding:** deterministic admission failure;
- **database/permission/Git/non-missing-filesystem/infrastructure/provider preparation failure:** operational failure, including when wrapped by another exception;
- **runtime/provider failure after session start:** durable session `FAILED` with authoritative runtime evidence when available;
- **terminal persistence failure after an observed runtime terminal outcome:** operational persistence failure; do not rewrite that observed `STOPPED`/`FAILED` outcome into a different durable terminal state;
- **application restart before terminal persistence:** durable session `INTERRUPTED`;
- **normal Paper completion/stop:** durable session `STOPPED`.

None of these events rewrites M9.5 or M9.6 decisions.

## 18. Explicit non-goals and deferred work

M9.7 does not implement:

- real-money orders or Live Trading;
- leverage, short selling, derivatives or shared-capital multi-symbol portfolio semantics;
- automatic Paper launch after WFA;
- automatic candidate winner selection;
- new economic qualification criteria;
- adaptive Candidate support;
- a campaign scheduler or distributed worker system;
- multi-user/commercial campaign infrastructure;
- durable provider socket/session restoration;
- open-position, pending-intent, strategy-state or continuous cash/equity checkpoint restoration across process/session boundaries;
- broker authentication/session lifecycle redesign already tracked by DW-015;
- frontend research-workspace integration assigned to M9.8; or
- a second Paper execution engine.

The continuous Paper-account checkpoint/restart capability is recorded as new deferred work rather than being silently added to this MVP.

## 19. Required deterministic validation

The M9.7 implementation must include tests proving at least:

1. only the exact current M9.6 `VALID/PASS/ELIGIBLE` CandidateRevision can create a campaign;
2. stale/replaced current M9.5 or M9.6 authority blocks admission/session start;
3. Candidate/Trial/ExperimentSpec/parameter contradictions block admission;
4. missing/corrupt WFA artifact blocks trustworthy admission;
5. unavailable or dirty software identity and incompatible executable core fail closed with correct operational/deterministic classification, including a resolver `OSError` remaining operational rather than becoming a qualification rejection;
6. the campaign configuration fingerprint changes for a representative frozen candidate execution-input change without mutating immutable registered mappings in place, while code review verifies the complete canonical field set declared in Section 4;
7. only `5m`/`15m`, `Asia/Kolkata` candidate time semantics and registered `angelone` provider execution are accepted in the qualified MVP path;
8. current AngelOne live binding is unique, applicable, canonical-instrument-matched and persisted per session;
9. qualified preparation uses the candidate's exact strategy object/parameters, runtime context, DatasetContext and initial capital rather than ordinary Paper defaults, while current-time session evaluation is normalized to IST;
10. warm-up and reconciliation use the candidate-bound successor historical retrieval adapter;
11. exact AngelOne market-data composition uses the registered binding/token, remains `paper_mode=True`, keeps broker historical order capability disabled for this live-data object, and invokes no real-order path;
12. durable session registration occurs before worker execution and lifecycle conflict cannot create an orphan durable session;
13. at most one durable qualified session can remain `CREATED/RUNNING`;
14. normal stop persists one exact terminal `STOPPED` snapshot;
15. runtime failure persists `FAILED` with failure evidence, including a legitimate empty `TimeoutError()` message;
16. terminal persistence failure after a fast normal stop or runtime failure is surfaced without calling the worker-start failure terminalizer or fabricating a contradictory durable `FAILED` record;
17. a real SQLite campaign/session store survives reconstruction, and startup recovery converts only stale `CREATED/RUNNING` qualified sessions to `INTERRUPTED`, preserves prior terminal sessions, maintains valid chronology and fabricates no terminal snapshot;
18. contradictory RUNNING start evidence or terminal state/time/snapshot/failure rewrites are rejected while idempotent identical lifecycle evidence remains stable;
19. a new session can be created under the same campaign after interruption only after current authority is rechecked;
20. campaign/session history survives store reconstruction and remains ordered/immutable;
21. exact qualified runtime composition constructs the real existing `PreparedLivePaperRun`/Paper execution graph through its application boundary with controlled provider fakes rather than stopping at an argument-capture double or in-memory campaign-store double;
22. existing M8 standalone Paper start/status/stop behavior remains green;
23. existing M9.4/M9.5/M9.6 and research-schema regressions, including all explicit schema-version assertions, remain green;
24. no `core/runtime`, execution, portfolio or strategy implementation is modified by this milestone; and
25. complete Python regression and `git diff --check` pass on the final implementation candidate.

## 20. Acceptance boundary

Passing M9.7 establishes that an exact qualified fixed CandidateRevision can be observed through persistent, real-market-data, simulated-execution Paper campaigns with truthful restart/session history.

It does **not** prove the strategy is profitable, does not certify live fills or capacity, does not create real-money execution authority, and does not close the overall V1 research product. M9.8 research-workspace integration and M9.9 research-ready acceptance remain later milestones.
