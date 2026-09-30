# STRATEGY EVALUATION PROTOCOL

**Schema:** `EVALUATION_PROTOCOL_V1`  
**Version:**  
**Frozen UTC:**  
**Git commit:**  
**SHA-256:**  

# 1. Purpose

This protocol defines how external strategy candidates are evaluated consistently.

It must be frozen before individual strategy results are used to decide which metrics or thresholds matter.

# 2. Research Stages

## Stage A — Source eligibility

Question:

Can the strategy be sufficiently reconstructed from available evidence?

Possible outcome:

- `PASS`
- `BLOCKED_SOURCE`

## Stage B — Implementation eligibility

Question:

Are required data and engine capabilities available?

Possible outcome:

- `PASS`
- `BLOCKED_DATA`
- `BLOCKED_ENGINE`

## Stage C — Pure/transfer replication

Run only after frozen spec.

No optimization.

## Stage D — Comparative assessment

Use the common metrics defined below.

## Stage E — Adaptation eligibility

Only after replication results are permanently recorded.

Adaptation creates a separate version.

# 3. Common Historical Window Protocol

**Common start UTC:**  
**Common end UTC:**  

If a strategy cannot use the common window:

**Allowed exception policy:**  

Different windows must be clearly marked and should not be treated as directly equivalent without adjustment.

Also preserve:

- strategy/source publication date;
- pre-publication history;
- post-publication history.

A full-history descriptive run is not automatically untouched OOS validation.

# 4. Common Execution Protocol

Unless a source-faithful requirement overrides it and is explicitly classified:

**Backtester:** Backtester V2  
**Margin mode:** CROSS  
**End-of-data policy:**  
**Maker fee assumption:**  
**Taker fee assumption:**  
**Slippage assumption:**  
**Limit fill policy:**  
**Funding policy:**  
**Liquidation policy:**  

Any exception must be recorded in the Strategy Spec.

# 5. Common Comparison Metrics

Mandatory for every comparable candidate where mathematically applicable:

- number of trades;
- net PnL;
- total return;
- expectancy per trade;
- profit factor;
- win rate;
- average winner;
- average loser;
- close-to-close max drawdown;
- intrabar worst max drawdown;
- return / intrabar-drawdown ratio;
- exposure;
- turnover;
- average holding time;
- total fees;
- estimated slippage cost;
- funding cost/credit;
- worst trade / tail loss;
- ambiguity count;
- ambiguity rate;
- yearly result breakdown.

# 6. Secondary Metrics

Calculate when return-series construction is consistent across candidates:

- Sharpe;
- Sortino;
- recovery factor;
- time under water.

Do not rank strategies using Sharpe/Sortino when the return-series methodology differs between candidates.

# 7. Descriptive Diagnostics

Not primary ranking metrics unless predeclared:

- regime breakdown;
- LONG vs SHORT;
- month/weekday/session analysis;
- performance around volatility regimes;
- parameter sensitivity.

These diagnostics must not silently become selection criteria after results are known.

# 8. Eligibility Gates

Freeze before viewing candidate outcomes.

## Minimum evidence

**Minimum completed trades:**  

## Risk

**Maximum allowed intrabar worst drawdown:**  

## Other hard exclusions

1.
2.
3.

Hard gates should be few and defensible.

If no universal numeric threshold is justified, explicitly state:

`NO PREDECLARED NUMERIC HARD THRESHOLD`

rather than inventing one.

# 9. Ranking Metrics

Define before individual strategy comparison.

Primary comparison dimensions:

1.
2.
3.

Tie-break / secondary dimensions:

1.
2.
3.

Do not change ranking dimensions after seeing which candidate benefits.

# 10. Costs

Every comparison must show separately:

- gross trading result;
- fees;
- slippage;
- funding;
- liquidation cost where applicable;
- final net result.

A strategy that is profitable only before realistic costs must remain identifiable as such.

# 11. Ambiguity Policy

Report:

- total ambiguous bars;
- trades affected;
- ambiguity rate;
- material effect on outcome where measurable.

Worst-admissible Backtester V2 output is used for the primary result.

Lower-level verification, if later performed, must be stored as a separate verified result rather than overwriting the original conservative run.

# 12. Multiple Testing Control

Maintain counts of:

- candidates considered;
- candidates implemented;
- candidates blocked;
- variants tested;
- parameter variants tested;
- adaptations tested.

The research report must never present only the final survivor without disclosing the size of the candidate/variant search.

# 13. Adaptation Rule

A replication strategy may enter adaptation only after:

1. frozen replication exists;
2. historical result is persisted;
3. original run artifacts remain immutable;
4. adaptation hypothesis is documented.

Every adaptation receives a new version and appears in Candidate Registry.

# 14. Protected Final Validation

If later optimization/adaptation is performed, define a protected validation stage before optimization begins.

**Protected period/data rule:**  

The protected period must not be used to choose adaptation parameters.

# 15. Program Lineage

Every assessed run must identify:

- Candidate Registry version/hash;
- Evaluation Protocol version/hash;
- Strategy Spec hash;
- Strategy code hash;
- Backtester commit/config hash;
- Data manifest hash;
- Run ID;
- Output manifest hash.

# 16. Protocol Change Ledger

| Version | Date | Change | Reason | Results already seen? |
|---|---|---|---|---|
| | | | | |

Any protocol change after candidate results are visible must be explicitly labeled and must not retroactively rewrite the original assessment.
