# M9.3 - Instrument, Universe and Dataset Truthfulness

## Status

**ACCEPTED DESIGN BASELINE / IMPLEMENTATION IN PROGRESS**

M9.3 defines the identity and truthfulness rules required before Kanasu
can perform reliable multi-instrument research.

It does not implement Study/Trial batch execution, strategy selection,
qualification, WFA progression or Paper campaigns. Those remain later
M9 milestones.

## 1. Why M9.3 exists

The current V1 system is still largely symbol-based.

Examples at the starting baseline:

- `Instrument` contains symbol, exchange, tick size and lot size;
- `DatasetContext` contains symbol, timeframe and timezone;
- historical SQLite dataset keys use symbol, timeframe and timezone;
- dataset fingerprints use that same dataset context;
- AngelOne historical lookup uses a temporary hard-coded
  symbol-to-token map;
- provider request times do not yet have an explicit contract for
  timezone-aware non-India input.

That is sufficient for the validated single-symbol research path, but
not sufficient for truthful universe research.

M9.3 must make instrument identity, universe membership, provider
mapping and dataset limitations explicit without changing accepted
Backtest financial behavior.

## 2. Scope

M9.3 owns:

1. canonical instrument identity;
2. provider-specific instrument mapping;
3. immutable universe definitions and snapshots;
4. existing V1 universe-quality classes;
5. dataset identity evolution required by canonical instrument identity;
6. dataset provenance and quality declarations;
7. provider wall-time handling for AngelOne historical requests;
8. truthful claim limits when universe/data quality is incomplete;
9. deterministic validation of these contracts.

M9.3 does not own:

- Study/Trial batch execution;
- bounded worker pools or job scheduling;
- strategy-search history;
- qualification policy;
- Candidate progression;
- shared-capital multi-symbol portfolio accounting;
- real-money trading;
- corporate-action adjustment implementation unless separately approved.

## 3. Canonical instrument identity

A research instrument must not be identified by ticker text alone.

M9.3 introduces a Kanasu-owned immutable `instrument_id` for one
identified exchange-listed security/listing.

The `instrument_id` is the stable lineage key. It is not derived from a
provider token and must not silently change merely because a trading
symbol changes.

Instrument metadata includes, as applicable:

- exchange;
- market segment/series;
- trading symbol;
- tick size;
- lot size;
- effective dates for attributes that may change.

Two listings that cannot be proven to represent the same continuing
security/listing receive different identities.

A documented symbol change for the same continuing listing may retain
the same `instrument_id` while recording a new effective-dated symbol.

Provider tokens and provider-specific symbols never become Kanasu's
canonical instrument identity.
## 4. Provider instrument binding

Broker/provider identifiers belong in a separate provider-binding
contract.

Each immutable provider binding identifies, at minimum:

- canonical `instrument_id`;
- provider name;
- provider exchange/segment when required;
- provider symbol when required;
- provider token or instrument identifier;
- effective-from/effective-to meaning when the mapping can change;
- immutable binding identity.

A historical request must resolve to one or more explicit provider
bindings whose effective intervals cover the requested period for which
provider retrieval is required.

If one binding changes during the requested period, Kanasu must split
provider retrieval at the applicable transition and use the correct
binding for each subrange.

Bindings used for one instrument/provider timeline must not have
unresolved gaps or conflicting overlaps across the provider-backed
portion being requested.

A gap, conflicting overlap or otherwise ambiguous mapping fails clearly.
Kanasu must not guess a provider token from symbol text.

The ordered provenance of a retrieval must identify every provider
binding used and the exact subrange for which it was applied.

A provider-binding transition does not by itself create a different
canonical instrument. It also does not rewrite the user's canonical
requested range.

The current hard-coded `RELIANCE -> 2885` mapping is a temporary
starting limitation, not the M9.3 target architecture.
## 5. Universe definition and immutable snapshot

`UniverseDefinition` describes how a set of instruments is intended to
be selected.

`UniverseSnapshot` is one immutable resolved membership state actually
used for research at a declared effective/as-of point or interval.

A snapshot must identify:

- its definition or source;
- canonical member `instrument_id` values;
- explicit effective/as-of meaning;
- universe-quality class;
- provenance/evidence references;
- immutable content identity.

Duplicate membership is invalid.

Canonical snapshot identity uses deterministic member ordering and must
not depend on accidental input ordering.

For `CURRENT_SNAPSHOT`, the capture/as-of time must remain explicit.

For rule-based or reconstructed membership, the rule/evidence version
used to derive membership must remain identifiable.

A research period may require membership that changes through historical
time. M9.3 therefore must support an immutable, deterministically ordered
collection of effective-dated snapshots or equivalent effective-dated
membership records.

When research is represented as point-in-time universe evidence, the
membership applied at each research time must correspond to that time
rather than a future membership state.

For point-in-time claims, membership transitions must be explicit. A
company that joins later cannot silently appear in earlier history, and
a company that leaves cannot silently remain in later history.

`CURRENT_SNAPSHOT` and `CUSTOM_FIXED` may still use one declared member
set retrospectively, but that use does not become point-in-time evidence
and its historical-selection or survivorship limitations remain explicit.

Each applied snapshot retains its own quality class and provenance.
If quality differs through the research period, that difference must
remain visible and must not be silently collapsed into a stronger
point-in-time claim.

A fixed `CUSTOM_FIXED` or `CURRENT_SNAPSHOT` universe may legitimately
use one immutable member set across a historical range, but its
historical-selection limitations must remain explicit.

M9.3 defines these membership identities and temporal-resolution rules.
M9.4 remains responsible for actually scheduling and executing
Study/Trial workloads across those resolved members.
## 6. V1 universe-quality classes

M9.3 preserves the existing M9.1 classes:

- `PIT_VERIFIED`
- `PIT_RECONSTRUCTED`
- `RULE_BASED_PIT`
- `CURRENT_SNAPSHOT`
- `CUSTOM_FIXED`

These describe historical-selection quality, not strategy quality or
profitability.

`CURRENT_SNAPSHOT` projected backward must remain visibly limited and
must never be described as survivorship-bias-free evidence.

`CUSTOM_FIXED` must retain the fact that the user selected the fixed
membership rather than implying historical index membership.

## 7. Universe research semantics

M9.3 does not create shared-capital portfolio economics.

Universe research continues to mean:

- one independent simulated account per instrument;
- research aggregation across those independent results;
- explicit denominators and missing/failed instrument counts;
- no summing of independent P&L and presenting it as one portfolio.

Actual Study/Trial execution over a universe remains M9.4 scope.

## 8. Dataset identity evolution

The accepted `kanasu.dataset.v1` identity remains immutable for existing
records.

M9.3 must not silently change the meaning of that schema or silently
change existing SQLite dataset keys.

A successor dataset contract is required for the new instrument/data
semantics.

The successor canonical dataset identity includes, at minimum:

- canonical `instrument_id`;
- requested range;
- timeframe;
- timezone;
- declared price/corporate-action basis such as raw, adjusted or unknown;
- the exact ordered candle content.

Provider name, retrieval time and provider token remain provenance rather
than canonical candle-content identity.

This means identical canonical candles with identical semantic treatment
may retain the same canonical data identity even when obtained from
different trusted sources, while their separate provenance remains
inspectable.

Physical local storage must nevertheless keep incompatible acquisition
streams separate so data from different provider bindings or different
price-adjustment meanings cannot be silently merged.

The existing append-only conflict rule remains: a different candle for
an already stored logical timestamp is not silently overwritten.

If corrected/provider-revised history must later be accepted, it requires
explicit new lineage/versioning or a separately approved migration rather
than invisible replacement.

Any successor dataset serializer, storage key, manifest projection or
reader needed for these semantics must be versioned. Existing v1
databases and evidence are not reinterpreted in place.

The successor identity must preserve the existing separation between:

- canonical input identity;
- retrieval/provider provenance;
- Backtest configuration identity;
- stable result identity.

The exact candle sequence fingerprinted for a Backtest remains the exact
sequence executed, preserving M9.2 behavior.
## 9. Dataset provenance and quality truth

Research evidence must be able to state where market data came from and
what limitations are known.

At minimum, M9.3 design must support truthful declaration of:

- canonical `instrument_id`;
- provider/source;
- every exact provider instrument binding used;
- the exact requested subrange associated with each binding;
- requested canonical range;
- timeframe;
- timezone;
- coverage status;
- retrieval/as-of information where available;
- price-adjustment/corporate-action basis when known;
- explicit unknown status when that basis is not known.

When provider retrieval is split across effective-dated bindings, the
resulting canonical candle sequence may still represent one requested
dataset, but its provenance must preserve all contributing bindings and
their applicable subranges.

Unknown adjustment status must remain unknown. Kanasu must not silently
claim adjusted or unadjusted history without evidence.

Invalid provider rows must not be silently repaired merely to obtain
complete coverage.

The deferred AngelOne negative-volume anomaly remains separately scoped
unless explicitly pulled into an approved M9.3 implementation slice.
## 10. AngelOne historical wall-time contract

AngelOne historical request strings represent India-market wall time.

M9.3 adopts this provider-boundary rule:

- naive request bounds retain the current interpretation as
  `Asia/Kolkata` wall time;
- timezone-aware bounds are converted to `Asia/Kolkata` before provider
  request formatting;
- conversion at the provider boundary does not rewrite the canonical
  dataset request identity or candle timestamps;
- deterministic tests prove the exact `fromdate` and `todate` sent to
  AngelOne.

This design choice is implemented by M9.3d in
`27baa264328432490246730d00a108dcd38916fe`
(`Implement M9.3d AngelOne binding and wall time`) without changing
canonical timestamp/fingerprint semantics.

Deterministic AngelOne historical regression coverage proves that aware
non-India bounds are converted to `Asia/Kolkata` before request
formatting, while naive bounds retain India-wall-time interpretation.
The provider-boundary representation does not rewrite the canonical
requested range or candle timestamps. Explicit provider-binding tests
also prove token/exchange selection and fail-closed binding validation.

M9.3d completed its focused validation and the complete Python regression
passed 1027 tests. DW-019 is therefore resolved at the accepted M9.3d
scope. This closure is limited to the AngelOne historical request-timezone
boundary; it does not claim completion of M9.3 application/research
integration or M9.3 milestone closure.

## 11. Failure and claim semantics

M9.3 must fail clearly when:

- canonical instrument identity is invalid;
- provider binding is missing or ambiguous;
- universe membership contains invalid/duplicate instruments;
- quality/provenance information required by the selected contract is
  missing;
- provider request representation cannot be produced safely.

A technical data retrieval success must not automatically imply:

- point-in-time universe validity;
- survivorship-bias freedom;
- corporate-action correctness;
- research qualification;
- profitability.

## 12. Compatibility rules

M9.3 must preserve:

- accepted M3 historical coverage/source-policy behavior;
- accepted M3/M4 canonical fingerprint discipline;
- accepted Backtest execution and accounting;
- accepted M5 WFA computation behavior;
- accepted M6/M7 Paper causality;
- accepted M9.2 research evidence and execution lineage;
- V1's no-real-money boundary.

Existing historical databases and v1 research evidence must remain
readable unless a separately approved migration is required.

## 13. Planned implementation slices

A proposed implementation order is:

- **M9.3a** - canonical instrument and provider-binding contracts;
- **M9.3b** - universe definition/snapshot identity and quality classes;
- **M9.3c** - successor dataset identity/provenance contract;
- **M9.3d** - AngelOne provider binding and wall-time correction;
- **M9.3e** - application/research integration for truthful instrument
  and dataset references;
- **M9.3f** - validation, traceability and closure synchronization.

These slices are accepted design guidance only. Implementation still requires
separate reviewed authorization for each implementation slice.
## 14. Design acceptance conditions

The M9.3 design baseline is acceptable only when:

1. ticker text alone is not treated as universally sufficient
   instrument identity;
2. Kanasu owns an immutable canonical `instrument_id`;
3. symbol/provider-token changes do not silently rewrite instrument
   lineage;
4. provider token identity remains separate from canonical instrument
   identity;
5. provider mappings are explicit and effective-dated where required,
   and one historical request may resolve across multiple non-overlapping
   applicable bindings;
6. provider-backed requested periods cannot contain unexplained binding
   gaps, conflicting overlaps or ambiguous mappings;
7. retrieval provenance identifies every provider binding used and its
   exact applicable subrange;
8. immutable universe snapshots reference canonical instrument IDs and
   have deterministic identity;
9. point-in-time universe membership changes are effective-dated and
   applied according to the membership state applicable at that research
   time rather than a future membership state;
10. point-in-time membership transitions cannot silently add future
    constituents to earlier history or retain departed constituents
    beyond their declared applicability, while retrospective
    `CURRENT_SNAPSHOT` and `CUSTOM_FIXED` use does not become PIT evidence;
11. each applied snapshot retains its own quality/provenance and mixed
    historical quality cannot be silently upgraded;
12. existing universe-quality classes retain their accepted meanings;
13. current constituents projected backward remain visibly limited;
14. universe research remains independent-account research rather than
    shared-capital portfolio accounting;
15. `kanasu.dataset.v1` and existing storage keys are not silently
    redefined;
16. successor dataset identity includes canonical instrument identity
    and declared price/corporate-action basis without making provider
    provenance part of unrelated canonical content identity;
17. incompatible provider/acquisition streams cannot be silently mixed
    in local storage;
18. conflicting stored candle values are not silently overwritten;
19. exact Backtest input/evidence behavior from M9.2 remains intact;
20. provider/data provenance and known limitations remain inspectable;
21. unknown corporate-action/adjustment state is not silently upgraded
    into a stronger claim;
22. AngelOne aware non-India bounds are converted to India wall time
    before request formatting;
23. naive AngelOne bounds retain explicit India-wall-time interpretation;
24. provider-wall-time conversion does not rewrite canonical dataset
    timestamp/fingerprint semantics;
25. invalid provider rows are not silently repaired to fabricate complete
    valid history;
26. M9.4 continues to own registered Study/Trial batch execution;
27. accepted Backtest/WFA/Paper financial and causal behavior remains
    unchanged;
28. real-money execution remains outside V1; and
29. implementation proceeds only in separately reviewed slices after
    design acceptance.
