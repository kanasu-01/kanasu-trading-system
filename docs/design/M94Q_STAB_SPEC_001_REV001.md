# M9.4q approved specification preservation record

Publication-only archive for SOP-G-003-V008 §§18 and 47. This is not a new specification version, behavior change or reopening of R004. The original proposal and incorporated RO-01 V002 are preserved below, including their historical status labels, source-access limitations and approval requests. Those labels describe the original proposal dates, not current implementation or approval state.

Current evidence: owner authorized the integrated correction scope and isolated preparation, then granted Human Approval 2 for patch `91a83af52360f279af015fa39b44242a2c23d03dadd57289a5bb4cb86731451e`. Independent candidate technical/specification/regression/documentation/exact-diff review passed (report SHA-256 `adddedbf43f0dd3dbc313d3118978947939fef355f2a69072bb3a15de40538aa`). The owner subsequently explicitly designated the repository SOP as authoritative, under SOP-G-000-V003 §12. Independent direct GitHub-source verification passed prospectively at `c6e2d3cb199f9bbed606e89f3644f40950aee46c`; SOP blob `19b307a8e9bd607a72988402bcb24c57ba51f898`, SHA-256 `3ddfc8f38a84962c9cf9cbec94a57c52b36002b1029994c293a888d91139a2d5`. The previous reports remain historical and unchanged; no past Git operation is retrospectively authorized.

The preservation/traceability addition itself is proposed for exact-diff approval and is not covered by the original eleven-file approval. No protected Git operation or closure is authorized. Implementation commit SHA remains unknown until separately authorized creation/publication; the actual implementing commit(s) and read-back/review evidence must be recorded when known. M9.4q and M9.5 remain blocked pending their remaining gates.

## Complete integrated specification as originally presented

<!-- BEGIN ORIGINAL M94Q-STAB-SPEC-001 REVISION 001 -->
# M94Q_INTEGRATED_CORRECTION_SPECIFICATION

**Specification ID:** `M94Q-STAB-SPEC-001`  
**Revision:** `001 — proposed for exact-content approval`  
**Repository:** `kanasu-01/kanasu-trading-system`  
**Branch:** `m9-v1-research-platform`  
**Verified current HEAD:** `c6e2d3cb199f9bbed606e89f3644f40950aee46c`

This is one additive stabilization specification incorporating the unchanged RO-01 V002 obligations and the corrections for CS-001–003. It does not supersede RO-01 V002, reopen R004 or authorize implementation.

The attachment is supporting specification and provenance evidence. The user’s request governs this turn: read-only reconciliation and preparation only.

## `M94Q_RECONCILED_BLOCKERS`

| Permanent finding | Required correction | Relationship |
|---|---|---|
| `RO-01` | Require an exactly flat opening position in nonempty manifest-bound results. | Existing approved V002 obligation. |
| `M94Q-CS-001` | Reject recorded costs/cash movements contradicting disabled brokerage. | Additional manifest-bound financial constraint. |
| `M94Q-CS-002` | Bind completed-trade symbols to the manifest execution symbol. | Additional provenance constraint. |
| `M94Q-CS-003` | Validate fresh computed results before accepted evidence/success publication. | Ensures fresh execution crosses the same acceptance boundary. |

These are **four blocking obligations with shared implementation and tests**, not four separate work packages. CS-003 does not replace validation when persisted evidence is subsequently reused or aggregated.

**Approval preservation**

- Appendix A was independently checked: **11,819 bytes**, SHA-256  
  `d8480704b0b2ad3ee1f6739c78a04ec78613dd17d85b37cab43fb28f462325cd`.
- RO-01 V002’s existing Human Approval 1 and technical-specification assessment PASS remain preserved. Its formal Review 1 remains `INSUFFICIENT_SOURCE_EVIDENCE`; it is not relabelled PASS.
- R004 remains **ACCEPTED_CLOSED** at `c6e2d3cb…`. Its approvals, publication and final acceptance are not reopened.
- RO-01 V002 concerns opening holdings; it contains no broader brokerage-calculation correction. The previous audit’s suggestion otherwise is resolved by this reconciliation.

## `M94Q_SINGLE_INTEGRATED_CORRECTION_SPEC`

The following numbered requirements, implementation scope, regression matrix and acceptance criteria constitute the complete proposed specification.

### 1. Shared acceptance boundary

**1.1** Canonical research acceptance shall require both:

1. Existing canonical result structural/semantic validation.
2. Binding of that result to its authoritative frozen run manifest, including the existing capital checks and requirements 2–4 below.

**1.2** The manifest-dependent rules shall have one production owner in `core/research/reproducibility.py`, extending the existing `validate_backtest_result_manifest_capital_binding` boundary. Fresh acceptance, exact reuse and canonical aggregation shall use those same rules.

**1.3** Canonical serialization, schema identifiers, fingerprints and historical artifact bytes shall remain unchanged. Generic result decoding shall not acquire manifest-dependent assumptions.

**1.4** A valid empty result retains its existing semantics. The correction shall not manufacture an opening snapshot or require irrelevant symbol/fee comparisons when no records or trades exist. Existing rejection of malformed empty-result structures remains intact.

### 2. RO-01: exact flat opening position

**2.1** Every nonempty manifest-bound result shall have first-record `position_size == 0` using **exact numeric equality**, independently of capital tolerances.

**2.2** The field shall satisfy established numeric-type and finite-value rules. Boolean, missing, nonfinite, negative, fractional and other invalid quantities shall not become acceptable. Valid numeric zero representations remain acceptable without normalization.

**2.3** Existing first-record cash/equity comparisons with manifest `initial_capital` shall retain their current tolerances: relative `1e-12`, absolute `1e-7`.

**2.4** Otherwise valid generic legacy opening-holding payloads shall remain decodable when no manifest-bound flat-start claim is made.

**2.5** A later holding arising from a valid funded BUY shall remain acceptable.

**2.6** Stored contradictory evidence shall not be repaired, migrated, reinterpreted or supplied with invented transactions.

These requirements preserve RO-01 V002’s normative behavior, compatibility, verification and closure obligations.

### 3. CS-001: disabled-brokerage consistency

**3.1** For nonempty manifest-bound execution histories, the relevant execution configuration shall come from the authoritative manifest. Missing or invalid required configuration shall fail closed; it shall not default silently to an enabled/disabled assumption.

**3.2** When `brokerage_enabled` is false:

- Every completed trade’s canonical `transaction_cost` shall equal numeric zero.
- An observed ordinary BUY shall reconcile cash to preceding cash minus **recorded execution price × acquired quantity**.
- An observed ordinary exit shall reconcile cash to preceding cash plus **recorded execution price × disposed quantity**.
- A supported same-bar entry/protective exit shall retain existing unique-settlement validation and reconcile to completed net P&L, with zero transaction cost.
- Existing unchanged-holding/no-execution cash-conservation checks remain applicable.

**3.3** Cash comparisons shall use the established financial comparison convention—relative `1e-12`, absolute `1e-7`—with controlled rejection of nonfinite derived arithmetic. Zero trade cost is an exact requirement, not a tolerance-based fee allowance.

**3.4** These checks shall use recorded execution prices, which already reflect applicable slippage. They shall not compare fills to unadjusted market prices, disable slippage or reject legitimate slippage effects.

**3.5** Brokerage-enabled execution retains its existing validation and economics. This package shall not implement another fee calculator, infer fee schedules or expand into broader enabled-brokerage certification.

### 4. CS-002: completed-trade symbol provenance

**4.1** Every completed trade in a manifest-bound result shall have a symbol exactly matching authoritative `manifest.dataset_context.symbol`.

**4.2** Where trades exist, the required manifest symbol shall be a valid nonempty string. Missing or invalid authority shall fail closed.

**4.3** Foreign or mixed symbols shall be rejected. No case folding, alias inference, ticker/provider conversion or evidence rewriting is permitted.

**4.4** Canonical instrument identity and provider-binding authority remain unchanged. This rule compares execution symbols; it does not introduce a new instrument resolver.

### 5. CS-003: fresh-result acceptance

**5.1** After financial computation, fresh orchestration shall validate a private result snapshot before creating accepted result evidence or publishing success.

**5.2** Validation shall cover the exact canonical representation of the result that is subsequently fingerprinted and persisted. The validated snapshot and authoritative manifest shall not be replaced by caller-owned mutable values after validation.

**5.3** The manifest shall be the same frozen execution manifest already proven against the private prepared inputs. A reconstructed manifest may be used only through the existing exact identity/byte-equivalence proof.

**5.4** Structural validation and requirements 2–4 shall run inside existing computation-failure handling, before successful result publication.

**5.5** Invalid computed output shall follow the existing failure lifecycle:

- Standalone execution records FAILED evidence and terminalizes its attempt as FAILED, then preserves established exception behavior.
- Claimed execution uses its existing coordinated terminalizer for attempt, job, Trial and disposition history.
- No ACCEPTED result evidence or SUCCEEDED outcome shall be published for that output.
- Existing classification rules remain unchanged; ordinary validator `ValueError`/`TypeError` retains the current `unknown_failure` classification, with useful diagnostic text.

**5.6** Authoritative storage/integrity failures shall remain distinguishable and fail closed. A failed terminal transaction shall not be reported as durable failure or success; existing recovery semantics remain applicable.

**5.7** Exact software identity, attempt ownership and nonexact-software evidence rules remain unchanged. Exact identity alone shall not bypass result validation.

### 6. Persisted reuse and aggregation

**6.1** Exact lookup shall continue validating actual immutable artifact bytes, accepted evidence and exact lineage before applying the shared manifest rules.

**6.2** A semantically invalid candidate shall retain existing skip/nonreusable behavior. Lookup shall create no RunAttempt. Valid fresh execution remains available through the existing workflow.

**6.3** Canonical EXECUTED and REUSED aggregation shall apply the shared rules after resolving authoritative accepted evidence and manifest lineage.

**6.4** Invalid result-bearing evidence shall produce the existing aggregation failure behavior. It shall not be silently omitted, converted into a different Trial disposition or used to reduce the denominator.

**6.5** Existing artifact-integrity and authoritative-storage exception behavior shall not be weakened.

### 7. Preservation requirements

The implementation shall preserve:

- M4 fills, brokerage/slippage calculations, sizing, accounting, drawdown and initialization.
- M5 WFA mathematics; M6/M7 Paper causality; M8 application authority.
- M9.2 immutable artifacts, evidence identities and distinct physical attempts.
- M9.3 instrument/provider/dataset truth.
- Immutable registered populations and Trial identities.
- Bounded workers, transactional lifecycle transitions and append-only history.
- Explicit retry, cooperative cancellation and restart interruption.
- Independent-account aggregation and reuse without fabricated execution.
- Generic legacy decoding and existing capital tolerances.

No new feature, migration, strategy, dependency, framework, trading authority or architectural redesign is included.

### 8. Precise implementation scope

| File | Permitted change |
|---|---|
| `core/research/reproducibility.py` | Extend existing manifest binding with exact flat opening position, disabled-brokerage consistency and trade-symbol agreement; add focused diagnostics/documentation. Preserve generic decoding and serialization. |
| `core/research/backtest_research_orchestrator.py` | Insert canonical and manifest-bound validation of the private fresh result within existing failure handling. Reuse the shared boundary and existing prepared-manifest proof. |
| `core/research/study_aggregation.py` | **No production edit presently required:** its existing canonical path already invokes the shared binding. Verify through regressions. |

Current source anchors are the [shared binding](https://github.com/kanasu-01/kanasu-trading-system/blob/c6e2d3cb199f9bbed606e89f3644f40950aee46c/core/research/reproducibility.py#L2107), [fresh execution](https://github.com/kanasu-01/kanasu-trading-system/blob/c6e2d3cb199f9bbed606e89f3644f40950aee46c/core/research/backtest_research_orchestrator.py#L1161), [reuse validation](https://github.com/kanasu-01/kanasu-trading-system/blob/c6e2d3cb199f9bbed606e89f3644f40950aee46c/core/research/backtest_research_orchestrator.py#L867) and [aggregation binding](https://github.com/kanasu-01/kanasu-trading-system/blob/c6e2d3cb199f9bbed606e89f3644f40950aee46c/core/research/study_aggregation.py#L662).

No production changes to engines, portfolio, catalog transactions, scheduler, API, brokers or strategies are authorized by this scope. Any demonstrated necessity for another file must be identified in the exact proposed diff before implementation approval.

## `M94Q_SINGLE_IMPLEMENTATION_AND_TEST_SCOPE`

### Regression matrix

| Obligation | Required negative evidence | Required preservation evidence |
|---|---|---|
| RO-01 | Capital `1000`, opening one share marked at `1e-8`, then `100`, no BUY; repeat at `1e-9`. Generic decoding/capital closeness may pass, but manifest binding rejects. | True flat start; funded later BUY; generic legacy opening holding; empty result; unchanged capital tolerances. |
| Numeric boundaries | Missing, Boolean, fractional, negative and nonfinite position values retain rejection. Already-invalid values do not substitute for the whole-share RO-01 counterexamples. | Valid integer/float whole-share representations and numeric zero. |
| CS-001 | Disabled brokerage with explicit nonzero trade cost; unexplained entry cash deduction on an open holding; contradictory exit settlement. | Genuine zero-fee execution, slippage-enabled zero-brokerage execution, brokerage-enabled real-engine execution and same-bar protective exits. |
| CS-002 | Foreign and mixed completed-trade symbols; missing/invalid required manifest symbol. | Exact matching symbol, no-trade output and unchanged provider identities. |
| CS-003 | Fresh negative-cash/structurally invalid output and fresh outputs violating each manifest rule. | Real-engine open, losing, zero-trade and same-bar results; existing nonexact-software behavior. |
| Durable authority | Hash-valid artifacts with coherent evidence references tested through lookup, registered reuse and both canonical aggregation dispositions. | No fabricated attempt; truthful fresh fallback; unchanged Trial denominator. |
| Lifecycle | Validation failure during computation, cancellation requested during computation and terminal-persistence failure. | Existing cancellation outcome rules, atomic failure, explicit retry and restart recovery. |

Implement these in the existing relevant modules:

- `tests/research/test_backtest_research_orchestrator.py`
- `tests/research/test_m94d_claimed_research_job_executor.py`
- `tests/research/test_m94f_study_aggregation.py`
- `tests/research/test_m94q_fresh_independent_red.py`

Share fixtures where useful without creating a new framework. Correct contradictory success fixtures to represent valid histories; do not weaken their assertions or remove adversarial coverage.

### Integrated validation

After authorization:

1. Establish permanent RED evidence against the pinned baseline.
2. Obtain GREEN results for the affected modules.
3. Run all M9.4 modules and the complete Python suite on the integrated corrected source.
4. Verify SQLite lifecycle/evidence relationships, artifact hashes and failure atomicity.
5. Check exact diff, scope, whitespace and documentation links.
6. Record environment, selectors, counts and source identity; verify exact published-SHA CI where applicable.

The prior **1,684 passing tests**, including **560 M9.4 cases across 24 modules**, remain attributed to the previous audit. They were **not rerun for this specification-preparation turn** and are not a prescribed future count.

### Documentation scope

Update only newly affected content:

| Owner | Required update |
|---|---|
| `docs/PROJECT_STATUS.md` | Four reconciled obligations, corrected-source identity, evidence and separate technical/documentation/governance status. |
| `docs/validation/VALIDATION_PLAN.md` | Regression matrix, selectors, results and acceptance gates. |
| `docs/behavior/TRACEABILITY.md` | Tests linked to opening-account integrity, financial configuration, provenance and accepted-evidence rules. |
| `docs/architecture/ARCHITECTURE.md` | Shared manifest-bound acceptance boundary and preserved generic compatibility. |
| `docs/architecture/DECISIONS.md` | Bounded AD-025 corrective note; preserve existing accepted financial ownership. |

Preserve RO-01 V002’s complete approved text and hash, and link this additive specification to it. Preserve R004 acceptance and original historical reports.

No README, roadmap, governance, SOP or deferred-work rewrite is required by default. `M94Q-CS-004` remains deferred; the historical 90-control selector remains unidentified.

### Acceptance criteria

Technical acceptance requires all of the following:

- All four counterexamples fail at their applicable authority boundaries.
- Persisted invalid evidence is neither reused nor accepted into result-bearing aggregation.
- Fresh invalid output cannot publish ACCEPTED/SUCCEEDED evidence.
- Valid engine output and generic legacy compatibility remain intact.
- Required focused, M9.4 and full regression results are attributable to the corrected source.
- No protected contract, denominator or lifecycle behavior changes unintentionally.
- Exact approved changes, actual implementation and published result agree.
- Documentation and independent implementation review pass.

Acceptance of this correction package **does not itself close M9.4q or admit M9.5**.

## `M94Q_GOVERNANCE_UNRESOLVED`

The handoff reports ChatGPT’s original Library retrieval of Global Registry V10, including ACTIVE `SOP-G-000-V003` and `SOP-G-003-V008`. I have **not independently retrieved that Library source**:

`SOP_AUTHORITY_FOR_CODEX = NOT_VERIFIED`

That disclosure does not prevent this read-only specification preparation. For a mandatory formal gate requiring independent original-source verification, use an authorized Library-capable independent review channel.

Remaining distinctions:

- RO-01 V002’s technical assessment PASS is preserved; its formal Review 1 limitation remains accurately recorded.
- R004 is closed and needs no repeat approval or review.
- Historical protected-operation approvals and the original audit-report F06 remain `NOT_VERIFIED`, not proven absent.
- The prospective governance candidate remains nongoverning and is outside this technical correction.
- A technical PASS cannot retrospectively authorize historical Git operations.
- No SOP amendment, source-authority migration or milestone closure is included.

## `M94Q_NEXT_APPROVAL_GATE`

**Next: Human Approval 1 for the complete exact content of `M94Q-STAB-SPEC-001`, Revision 001, above**, incorporating unchanged RO-01 V002 and approving only the additive CS-001–003 obligations and coordinated scope.

This is a new additive package specification, not a successor rewriting RO-01 V002. The additions are explicitly separated in requirements 3–6; no previous approval is claimed to approve them automatically.

The minimum subsequent gates are:

1. Independent specification review of this integrated content, with the formal SOP-source requirement satisfied through a capable review channel.
2. **One Human Approval 2** for the complete exact production/test/documentation diff—not merely this file-scope plan.
3. Separately explicit authorization for applicable protected Git operations.
4. Actual published-state verification and independent Review 2.
5. Final human acceptance of the correction package.

No duplicate R004 gate, repeat RO-01 wording approval or automatic M9.4q closure is required or implied.

**MUTATIONS_PERFORMED: NONE — code, tests, documentation, SOPs and Git state unchanged.**
<!-- END ORIGINAL M94Q-STAB-SPEC-001 REVISION 001 -->

## Complete incorporated RO-01 V002 as approved

The following fenced text is the unchanged 11,819-byte source, including its final newline; SHA-256 `d8480704b0b2ad3ee1f6739c78a04ec78613dd17d85b37cab43fb28f462325cd`. Historical metadata and the original concluding label are preserved, not corrected by implication.

~~~~text
# KANASU M9.4q — RO-01 Manifest-Bound Opening-Position Integrity Correction — Candidate V002

**Status:** PROPOSED — NOT APPROVED — READ-ONLY PREPARATION  
**Date:** 28 October 2026  
**Specification family:** RO-01 standalone technical-correction family; V002 is the complete proposed successor to human-approved V001, SHA-256 `758212237956abcfd98918b04292d1191728a34834fabfafb42d2bdf06f5ead8`. It is not a revision of completed R004 documentation.  
**Target repository:** `kanasu-01/kanasu-trading-system`  
**Verified preparation branch:** `m9-v1-research-platform`  
**Verified preparation HEAD:** `c6e2d3cb199f9bbed606e89f3644f40950aee46c`  
**Governing Global SOP:** authoritative ChatGPT Library `/SOP/GLOBAL_SOP_REGISTRY.md`, Library V10, ACTIVE SOP-G-003-V008, independently read back 28 October 2026  
**Document authority:** This is a proposed specification only. It grants no implementation, Git, publication, closure, M9.5 or trading authority.

## 1. Objective and evidence basis

Eliminate the independently demonstrated HIGH-severity `RO-01` defect: a manifest-bound canonical Backtest result may contain an unearned opening holding with a tiny opening mark-to-market value, pass initial-capital tolerance, become eligible for exact evidence reuse and contribute fabricated return to canonical Study aggregation without any recorded BUY.

The independent review of the exact published HEAD reports `CURRENT_BASELINE_TECHNICAL_AUDIT: FAIL`. It reproduced a complete-manifest result with capital 1000, initial `cash=1000, position_size=1, close=1e-8, equity=1000.00000001`, then `cash=1000, position_size=1, close=100, equity=1100`; both execution events absent and no completed trade. Canonical decoding, manifest binding, exact-reuse qualification and canonical EXECUTED aggregation accepted it, yielding approximately 10% apparent return. This was deliberately fabricated corrupted evidence, not ordinary Backtest engine output. The complete original auditor response is preserved as Appendix A of the companion review package.

## 2. Authoritative contract and location

The ordinary Backtest `PortfolioManager` starts at initial capital with `position_size=0`; `BacktestEngine` starts with no pending execution intent, so the first emitted BarRecord is a pre-execution snapshot. Actual initial holdings cannot originate from a prior recorded BUY in this supported manifest-bound execution workflow.

Verified source at `c6e2d3cb199f9bbed606e89f3644f40950aee46c`:

- `core/research/reproducibility.py`, `validate_stable_backtest_result_payload` (near lines 2083–2104): generic canonical decoding deliberately permits legacy opening holdings; preserve that compatibility.
- `core/research/reproducibility.py`, `validate_backtest_result_manifest_capital_binding` (lines 2107–2190): verifies first-record `cash` and `equity` against manifest `initial_capital` with tolerances but currently omits opening `position_size=0`.
- `core/research/backtest_research_orchestrator.py`, `find_exact_reusable_execution` (near line 758): calls the manifest-binding validator to qualify reuse.
- `core/research/study_aggregation.py`, `_validate_result_manifest_capital` (near line 588): calls the same validator for canonical Trial results.
- `core/portfolio/portfolio_manager.py` near line 30: initializes position size to zero.
- `core/backtest/backtest_engine.py` near lines 73, 110–128: no pending initial execution; records first account snapshot.

## 3. Required bounded behavior

1. At the **manifest-bound research-validation boundary**, any **nonempty** canonical Backtest result must have the first BarRecord's `position_size` equal to **exactly zero**, using the already established canonical numeric-type/finite validation. Do not treat a tiny nonzero holding as zero through financial tolerance. Missing/invalid position-size values must fail under established canonical result rules.
2. Continue validating first-record `cash` and `equity` against authoritative manifest `initial_capital` with the **existing** numerical tolerances. The new position-flat requirement is independent of cash/equity numerical closeness.
3. Preserve the generic `decode_stable_backtest_result_bytes` and general stable-result structural validator's historically intentional acceptance of otherwise valid **legacy opening-holding payloads** when no authoritative manifest-bound flat-start claim is being made. Do not globally ban legacy opening positions.
4. Preserve existing empty-result semantics: no bar record means no opening snapshot to compare; do not manufacture an empty-result failure based solely on the new opening-position invariant.
5. Both supported exact-reuse lookup and authoritative canonical Study aggregation (`EXECUTED` and `REUSED`) must reject or exclude manifest-bound evidence inconsistent with a flat opening position, even when initial cash/equity pass existing tolerance. Preserve existing fail-closed and exception/skip behavior at each caller; do not silently change caller disposition semantics.
6. Valid outputs of the supported engine must continue to validate. A holding arising on a later bar after a valid funded BUY must remain accepted. Do not change engine fills, brokerage, slippage, drawdown, position sizing, WFA/Paper economics, account initialization or data/provider identities.
7. Do not repair, reinterpret, or silently migrate already stored corrupted evidence. If existing persisted artifacts fail the corrected validation, refuse their reuse/result-bearing acceptance according to current semantics, with truthful diagnostics and no invented trade history.

## 4. Required verification and regression coverage

The implementation review and tests must demonstrate, at minimum:

- A fixed, deterministic **negative** test using the auditor's two-BarRecord complete-manifest counterexample. Generic decoding may pass, but manifest binding MUST reject the opening holding; manifest-backed exact-reuse lookup must not return REUSABLE; canonical `EXECUTED` and `REUSED` result-bearing aggregation must not accept the invalid artifact.
- Include a second otherwise valid **whole-share** opening-position counterexample with a **smaller positive initial mark-to-market value** (for example, `position_size=1`, first-bar `close=1e-9`). Prove that generic decoding and the existing initial-capital tolerance checks accept the payload on the uncorrected baseline, while corrected manifest binding rejects the nonzero initial position. Verify that the new position check uses **exact numeric zero**, independently of initial-equity tolerance. Fractional, negative, missing, Boolean, nonfinite and other invalid position-size cases must retain their existing rejection behavior, but an already-rejected invalid quantity **does not** demonstrate the new manifest-bound guard. Preserve whole-share and long-only requirements.
- Positive real-engine and canonical-manifest cases with an initially flat position, including a later properly executed BUY, remain accepted.
- Positive generic legacy-result decoding of an otherwise valid opening-holding payload remains accepted without manifest binding.
- Empty-result manifest binding retains its existing behavior.
- Existing initial cash/equity tolerance behavior remains unchanged; no false rejection from unrelated rounding.
- Direct negative tests of both result dispositions, with preserved aggregation error/fail-closed behavior; assert no fabricated result-bearing return.
- Focused tests and the full applicable Python regression run on the **exact corrected source**, including regression result counts, tests selected, environment, and SHA. Any unavailable suite or infrastructure limitation is stated explicitly rather than converted into PASS.

No test-count increase is prescribed. Tests must exercise the existing supported entry points, not just a helper directly. Independent Review 2 must challenge whether the fix closes the whole acceptance route and preserves legitimate historical payload compatibility.

## 5. Permitted implementation scope

**Primary candidate production file:** `core/research/reproducibility.py`, inside the existing manifest-binding validator. The desired behavior should be achievable through the shared existing boundary; do not edit callers unless an independent, source-grounded demonstration proves additional changes essential.

**Test files:** Existing relevant tests under `tests/research/`, precisely selected by the implementation agent after inspecting their exact current contents. A new focused test module may be proposed only if necessary. Update the minimum authoritative documentation and traceability records needed to report this correction truthfully. All exact files and complete before/after differences require Human Approval 2.

Do **not** modify generic validation semantics, production Backtest/Paper/WFA execution, technical/fundamental strategies, risk economics, brokers, live trading, or M9.5 qualification rules. Do not modify Global SOPs or retroactively change R004 documentation approval history.

## 6. Identity, predecessor, and independent review

RO-01 was introduced as a **new standalone corrective-specification family** in Candidate V001, distinct from completed R004 documentation work. Human Approval 1 of exact V001 is VERIFIED, but its independent Formal Review 1 returned FAIL. **This V002 is a revision of that existing human-approved V001**, not a fresh unrelated specification. The entire approved V001 remains preserved unchanged as the immediate predecessor, and its complete successor wording and exact changes are presented under ACTIVE SOP-G-003-V008 §§7 and 22–27. V002 requires a new exact Human Approval 1 and independent Formal Review 1 PASS before any implementation proposal. Historical M9.4 design contracts and the closed R004 task are not superseded.

After exact-wording Human Approval 1, obtain independent Formal Codex Review 1 PASS; then present **all actual intended file differences** and source identities for separate Human Approval 2. Only after that may precisely authorized edits and separately approved protected Git operations occur. Verify exact published SHA, conduct Formal Review 2 of actual source and tests, present changes for Human Approval 3. No automatic approvals, publication, or milestone closure.

## 7. M9.4q / V002 interaction and deferred evidence

The accepted R004 seven-document publication at `c6e2d3cb199f9bbed606e89f3644f40950aee46c` remains closed. The currently published baseline has a fresh technical FAIL until the corrective candidate is implemented and independently accepted at its exact source identity. Prospective closure Candidate V002, currently **NOT_VERIFIABLE**, pins this deficient published baseline and **must not** be activated unchanged. Its separate governance/§7 decision may only proceed with an independently verified corrected baseline, appropriate candidate revision, the original historical approval gaps preserved as `NOT_VERIFIED`, and all additional independent reviews and human approvals.

Missing original historical audit `F06` is an **evidence gap**, different from the earlier historical runtime defect also labelled `F06`. A future original audit may be recovered and/or a new, attributable adversarial audit may support prospective acceptance if independently found permissible. Neither is fabricated here.

## 8. Closure boundaries

The standalone RO-01 task is complete only when its exact corrected implementation, tests, documents, separate Git authorizations and published-state verification pass both independent reviews and all three human approvals. Its acceptance does not itself close M9.4q, authorize M9.5, grant live-money authority or establish the legality of the prospective closure rule.

**End of full Candidate V001.**
~~~~
