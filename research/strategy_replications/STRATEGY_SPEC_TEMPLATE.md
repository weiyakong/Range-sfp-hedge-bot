# STRATEGY SPEC

## 1. Machine-readable Identity Header

**Schema:** `STRATEGY_SPEC_V1`  
**Strategy name:**  
**Strategy ID:**  
**Strategy version:** `PURE_REPLICATION_V1`  
**Status:** `DRAFT / BLOCKED / FROZEN / TESTED`

**Candidate registry ID:**  
**Evaluation protocol version:**  

**Spec created UTC:**  
**Spec frozen UTC:**  

**Spec Git commit:**  
**Spec SHA-256:**  

No empty value, `TBD`, placeholder or unresolved machine-critical field is permitted when Status = `FROZEN`.

---

# 2. Fidelity Classification

Replication fidelity is described on separate axes.

Do not compress these into one label.

## 2.1 Rule fidelity

Choose one:

- `VERBATIM`
- `FORMALIZED_INTERPRETATION`
- `ADAPTED`

**Rule fidelity:**  

## 2.2 Market relation

Choose one:

- `SAME_MARKET`
- `TARGET_MARKET_TRANSFER`

**Market relation:**  

## 2.3 Parameter fidelity

Choose one:

- `SOURCE_FIXED`
- `SOURCE_RANGE`
- `RESEARCH_ASSUMPTION`
- `ADAPTED`

**Parameter fidelity:**  

## 2.4 Execution fidelity

Choose one:

- `SOURCE_SPECIFIED`
- `TARGET_VENUE_MAPPING`
- `RESEARCH_ASSUMPTION`
- `PROXY`
- `ADAPTED`

**Execution fidelity:**  

`PROXY` must be explicitly justified and may change replication classification.

## 2.5 Sizing fidelity

Choose one:

- `SOURCE_DEFINED`
- `STANDARDIZED_RESEARCH_OVERLAY`
- `ASSUMED`
- `ADAPTED`

**Sizing fidelity:**  

## 2.6 Summary classification

Choose:

- `PURE_REPLICATION`
- `TRANSFER_REPLICATION`
- `ADAPTED`

**Summary classification:**  

`PURE_REPLICATION` is allowed only when no material axis contains an adaptation incompatible with the original strategy contract.

---

# 3. Replication Goal

**Exact research question:**  

State precisely what is being tested.

Examples of distinctions that must remain explicit:

- whether original trading rules work as published;
- whether those rules transfer to BTCUSDT;
- whether standardized sizing changes risk;
- whether a later adaptation improves results.

For a frozen replication:

- no parameter optimization after seeing results;
- no new filters after seeing results;
- no deletion of losing trades;
- no favorable ambiguity resolution;
- no silent proxy;
- no changing historical window after results;
- no changing assessment criteria after results.

Any material post-result change requires a new version.

---

# 4. Source Evidence

## 4.1 Primary source

**Author:**  
**Title:**  
**Edition/version:**  
**Publication date:**  
**URL / book / paper:**  
**Exact page / chapter / timestamp:**  

## 4.2 Immutable source evidence

**Snapshot path/reference:**  
**Snapshot SHA-256:**  

If copyright or technical constraints prevent storing a complete source snapshot, store sufficient immutable metadata and hashes for the evidence actually used.

## 4.3 Knowledge cutoff

**Source publication/knowledge cutoff date:**  

This date must be preserved separately from the historical backtest period.

A historical run over data the original author could already have observed must not be described as untouched out-of-sample validation.

## 4.4 Secondary sources

| Source ID | Source | Version/date | Purpose |
|---|---|---|---|
| S02 | | | |

## 4.5 Conflict register

| Conflict ID | Rule | Source A | Source B | Resolution |
|---|---|---|---|---|
| C01 | | | | |

Allowed resolution:

- `UNRESOLVED`
- `SOURCE_CLARIFIED`
- `PREDECLARED_INTERPRETATION`

Required unresolved conflicts block freeze.

---

# 5. Original Strategy Scope

**Original instrument:**  
**Original market:**  
**Original market type:**  
**Original timeframe:**  
**Original session:**  
**Original timezone:**  
**Original LONG/SHORT scope:**  
**Original position sizing:**  
**Original leverage:**  
**Original execution venue/model:**  

If source does not specify:

`UNSPECIFIED`

---

# 6. Target Test Scope

**Target instrument:**  
**Reference market/exchange:**  
**Market type:**  
**Timeframe:**  
**Timezone:** `UTC`

**LONG allowed:**  
**SHORT allowed:**  
**Simultaneous LONG + SHORT required:**  
**Same-side pyramiding required:**  

Every material difference from Original Strategy Scope must be reflected in Fidelity Classification.

---

# 7. Predeclared Historical Window

Must be frozen before first full historical result.

**Start UTC:**  
**End UTC:**  

**Window type:**

- `FULL_HISTORY_DESCRIPTIVE`
- `POST_PUBLICATION`
- `PRE_PUBLICATION`
- `HOLDOUT`
- `OTHER`

**Reason for selecting window:**  

**Dataset:**  
**Expected manifest:**  
**Manifest SHA-256 when frozen:**  

Changing the window after seeing results requires a new run/version and must remain visible in the history.

---

# 8. Data Contract

For every input classify:

- `REQUIRED`
- `OPTIONAL`
- `FORBIDDEN`
- `NOT_USED`

and availability:

- `AVAILABLE`
- `NOT_AVAILABLE`

## Price data

| Field | Requirement | Availability | Source |
|---|---|---|---|
| OHLC | | | |
| Volume | | | |

## Additional data

| Field | Requirement | Availability | Source |
|---|---|---|---|
| Mark Price | | | |
| Funding | | | |
| Open Interest | | | |
| Liquidations | | | |
| Order book | | | |
| Other | | | |

`missing ≠ zero`

Required missing data block freeze unless a proxy is explicitly declared and the Fidelity Classification is updated.

---

# 9. Timeframe / Session Contract

**Source timeframe:**  
**Strategy timeframe:**  

Define exactly:

- aggregation boundary;
- UTC alignment;
- exchange/session boundary;
- DST treatment if applicable;
- OHLC aggregation;
- volume aggregation;
- incomplete candle policy;
- higher-timeframe visibility timing.

A completed HTF candle becomes usable only after that candle has actually closed.

No historical code may use a partially formed higher-timeframe candle as a completed observation unless the original strategy explicitly uses intrabar HTF state and appropriate granular data exist.

---

# 10. Missing Data / Gap Contract

Define behavior for:

- missing base bars;
- missing HTF bars;
- duplicates;
- malformed bars;
- off-grid timestamps;
- unavailable indicator input;
- exchange data gaps.

Also define separately:

**Indicator state across gap:**  
**Strategy state across gap:**  
**Pending orders across gap:**  
**Open positions across gap:**  
**Holding-period counters across gap:**  
**Maximum tolerated gap:**  

Synthetic interpolation is forbidden unless explicitly declared and justified.

---

# 11. Indicators / Derived Features

For every feature:

**Indicator ID:**  
**Name:**  
**Exact formula:**  
**Input:**  
**Lookback:**  
**Smoothing:**  
**Initialization/seed:**  
**Warm-up:**  
**Rolling-window inclusivity:**  
**NaN policy:**  
**Rounding:**  
**Available-at timestamp:**  
**Source rule/reference:**  

Indicator names alone are insufficient.

Examples requiring exact definition:

- ATR;
- RSI;
- EMA;
- Bollinger Bands;
- pivots;
- swings;
- support/resistance.

---

# 12. Human Rule Formalization

Every discretionary or qualitative term must be mapped before freeze.

| Rule ID | Source term | Formal machine definition | Alternatives rejected | Source evidence |
|---|---|---|---|---|
| R01 | | | | |

Examples:

- strong trend;
- significant level;
- rejection;
- clear breakout;
- momentum;
- consolidation;
- false breakout;
- swing high/low.

Unformalized machine-critical terms block freeze.

---

# 13. Setup Definition

## LONG

1.
2.
3.

## SHORT

1.
2.
3.

Every condition must be machine-testable.

---

# 14. Entry Signal

## LONG

Exact Boolean/machine condition:

## SHORT

Exact Boolean/machine condition:

---

# 15. Causal Event Timeline

Define the timing of every material event.

| Event | Information becomes available | Strategy evaluates | Order becomes eligible | State changes |
|---|---|---|---|---|
| | | | | |

At minimum cover:

- raw market data;
- HTF completion;
- indicator update;
- setup creation;
- signal creation;
- order creation;
- earliest legal execution;
- fill;
- stop/TP activation;
- exit;
- strategy state update.

Default:

`signal known at bar close → earliest market execution = next available bar open`

Current H/L/C cannot be used before it exists.

Pivot/swing definitions requiring future/right-side confirmation must use the confirmation timestamp rather than the historical pivot timestamp as signal availability.

---

# 16. Entry Order Contract

## LONG

**Order type:**  
**Price rule:**  
**TIF:**  
**Expiration:**  
**Cancellation:**  
**Gap behavior:**  

## SHORT

**Order type:**  
**Price rule:**  
**TIF:**  
**Expiration:**  
**Cancellation:**  
**Gap behavior:**  

---

# 17. State × Signal Decision Table

Every reachable combination must have an explicit outcome.

| Current state | Incoming event/signal | Required action |
|---|---|---|
| Flat | LONG | |
| Flat | SHORT | |
| LONG open | LONG | |
| LONG open | SHORT | |
| SHORT open | SHORT | |
| SHORT open | LONG | |
| LONG pending | LONG | |
| LONG pending | SHORT | |
| SHORT pending | SHORT | |
| SHORT pending | LONG | |
| Position open | Exit + new entry same timestamp | |
| After SL | New signal | |
| After TP | New signal | |

Add strategy-specific states where required.

No state/action cell required by the strategy may remain undefined at freeze.

---

# 18. Stop Loss

## LONG

**Exists:**  
**Initial rule:**  
**Movement:**  
**Trigger source:**  
**Gap rule:**  
**Execution assumption:**  

## SHORT

**Exists:**  
**Initial rule:**  
**Movement:**  
**Trigger source:**  
**Gap rule:**  
**Execution assumption:**  

---

# 19. Take Profit

## LONG

**Exists:**  
**Target rule:**  
**Multiple targets:**  
**Partial exits:**  
**Gap rule:**  

## SHORT

**Exists:**  
**Target rule:**  
**Multiple targets:**  
**Partial exits:**  
**Gap rule:**  

---

# 20. Other Exit Rules

Declare all applicable rules:

- signal exit;
- opposite signal;
- time exit;
- maximum holding period;
- session exit;
- trailing stop;
- break-even;
- indicator exit;
- emergency exit;
- other.

Every enabled exit requires a machine rule.

---

# 21. Position Sizing

## Source sizing

**Source-defined sizing:**  
**Source evidence:**  

## Research sizing overlay

If source sizing is unavailable or unsuitable for standardized comparison:

**Research sizing model:**  
**Reason:**  

**Fixed qty / notional / equity % / risk % / other:**  
**Risk per trade:**  
**Minimum:**  
**Maximum:**  

## Precision

**Price tick:**  
**Quantity step:**  
**Minimum notional:**  
**Rounding rule:**  

Source strategy performance and standardized research sizing performance must remain distinguishable.

---

# 22. Leverage / Margin

**Source leverage:**  
**Research leverage:**  

**Margin mode:** `CROSS`  
**Liquidation relevant:**  
**Hedge mode relevant:**  

A leverage assumption introduced by research is not part of the original strategy rule set.

---

# 23. Execution Assumptions

Freeze before historical run.

**Maker fee:**  
**Taker fee:**  
**Slippage:**  
**Funding treatment:**  
**Mark Price treatment:**  
**Liquidation treatment:**  
**Limit fill policy:**  
**End-of-data policy:**  

Every assumption must record:

**Origin:** `SOURCE / EXCHANGE / COMMON_RESEARCH_PROTOCOL / STRATEGY_SPECIFIC_ASSUMPTION`

---

# 24. Intrabar Contract

Use the audited Backtester V2 conservative causal model.

When OHLC permits multiple admissible event sequences:

- evaluate admissible paths;
- select worst admissible strategy outcome;
- record material disagreement as `AMBIGUOUS_INTRABAR`;
- never select favorable ordering because it improves performance.

If OHLC cannot resolve an event:

`REQUIRES_LOWER_LEVEL_VERIFICATION`

Do not claim tick-level certainty from OHLC.

---

# 25. Strategy State

| State variable | Meaning | Creation | Update | Reset |
|---|---|---|---|---|
| | | | | |

Every state variable must be causal.

---

# 26. Engine Compatibility Gate

Check against the exact Backtester commit used for the run.

| Requirement | Needed? | Supported by exact V2 commit? | Resolution |
|---|---|---|---|
| Market entry | | | |
| Limit entry | | | |
| Stop-entry | | | |
| GTC | | | |
| IOC | | | |
| Multiple same-side pending orders | | | |
| Same-side pyramiding | | | |
| Simultaneous LONG + SHORT | | | |
| Partial exits | | | |
| Multiple TP | | | |
| Trailing stop | | | |
| Dynamic order amendment | | | |
| Same-bar callback/re-entry | | | |
| Mark Price liquidation | | | |
| Funding | | | |
| HTF data | | | |
| External feature feed | | | |

Resolution:

- `SUPPORTED`
- `NOT_REQUIRED`
- `BLOCKED_UNSUPPORTED_ENGINE_CAPABILITY`

No silent approximation is allowed.

If mandatory behavior is unsupported:

`SPEC STATUS = BLOCKED`

A proxy requires an explicit new fidelity classification/version.

---

# 27. Unspecified / Ambiguity Register

| ID | Issue | Material? | Required for implementation? | Resolution |
|---|---|---|---|---|
| U01 | | | | |

Allowed resolution:

- `UNRESOLVED`
- `SOURCE_CLARIFIED`
- `PREDECLARED_INTERPRETATION`
- `NOT_REQUIRED`

Material unresolved fields block freeze.

---

# 28. Parameter Registry

| Parameter | Value | Units | Origin | Allowed source range | Frozen? |
|---|---:|---|---|---|---|
| | | | | | YES |

Origin:

- `SOURCE_EXACT`
- `SOURCE_RANGE`
- `DETERMINISTIC_MARKET_TRANSLATION`
- `RESEARCH_ASSUMPTION`
- `POST_RESULT_ADAPTATION`

`POST_RESULT_ADAPTATION` cannot occur inside frozen replication version.

---

# 29. Rule Traceability Matrix

Every material source rule must connect to executable behavior and a test.

| Rule ID | Source evidence | Interpretation | Executable predicate/state transition | Test ID |
|---|---|---|---|---|
| R01 | | | | |

No material source rule may disappear between source and code.

---

# 30. Machine Rules

## LONG setup

## LONG entry

## SHORT setup

## SHORT entry

## LONG exit

## SHORT exit

## Position sizing

## Order lifecycle

## State transitions

This section is the authoritative implementation contract for `strategy.py`.

---

# 31. Pre-Backtest / Golden Tests

Before freeze require tests for:

- valid LONG;
- invalid LONG;
- valid SHORT;
- invalid SHORT;
- indicator warm-up;
- boundaries/equality;
- timeframe alignment;
- HTF availability;
- missing data;
- signal timing;
- earliest execution;
- repeated signals;
- conflicting signals;
- state transitions;
- entry;
- stop;
- TP;
- gap;
- exit;
- re-entry;
- no-lookahead.

## Golden source examples

If the source contains worked examples/charts:

| Example ID | Source reference | Expected interpretation/result | Test ID |
|---|---|---|---|
| G01 | | | |

Tests validate rules, not profitability.

---

# 32. Program Evaluation Link

**Candidate registry version:**  
**Evaluation protocol version:**  

Common program-wide eligibility/ranking rules live outside this individual strategy spec.

Strategy-specific additional metrics:

1.
2.
3.

They must be declared before seeing this strategy's full historical result.

---

# 33. Automated Freeze Gate

`FROZEN` must be rejected if any of these exist:

- machine-critical empty fields;
- `TBD`;
- unresolved material source conflict;
- unresolved machine-critical ambiguity;
- unformalized discretionary term;
- unknown parameter origin;
- missing mandatory data;
- undeclared proxy;
- unsupported mandatory engine capability;
- incomplete causal timeline;
- incomplete required state/signal decision;
- unfrozen sizing;
- unfrozen execution assumptions;
- unfrozen historical window;
- missing evaluation protocol version;
- missing candidate registry ID/version;
- missing rule traceability;
- missing golden/causality tests;
- failed synthetic tests.

After validation:

**SPEC STATUS:** `FROZEN`

**Frozen UTC:**  
**Spec Git commit:**  
**Spec SHA-256:**  

---

# 34. Run Lineage

Every run must identify:

**Run ID:**  

**Candidate registry version:**  
**Evaluation protocol version:**  

**Strategy Spec SHA-256:**  
**Strategy code Git commit/SHA:**  
**Strategy code SHA-256:**  

**Backtester Git commit:**  
**Backtester config SHA-256:**  

**Data manifest SHA-256:**  

**Output manifest SHA-256:**  

Required lineage:

`Candidate Registry → Evaluation Protocol → Strategy Spec → Strategy Code → Backtester Config → Data Manifest → Run ID → Output Manifest`

---

# 35. First Historical Run

Fill only after freeze.

**Run ID:**  
**Actual start UTC:**  
**Actual end UTC:**  

Confirm:

**Actual range matches frozen range:** `YES / NO`

If NO, run is not the predeclared replication run.

---

# 36. Post-result Change Ledger

Any material change after seeing results must remain visible.

| Change ID | Previous version | Change | Reason | New version |
|---|---|---|---|---|
| | | | | |

Examples:

- parameter changes;
- additional filters;
- market changes;
- timeframe changes;
- altered sizing;
- changed stop/TP;
- changed execution;
- new interpretation.

Such changes create a new `ADAPTED_*` or other explicitly classified version.

They never overwrite the frozen replication record.
