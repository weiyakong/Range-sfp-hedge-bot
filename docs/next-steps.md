# Next Steps

Version: **0.2**

This project should be tested slowly and visually before any automation is considered.

## 1. Test visually on BTC

Add the Pine Script indicator to a BTC chart in TradingView. Review multiple timeframes and different market conditions.

## 2. Compare labels with manual analysis

Do not trust the labels automatically. Compare each bullish or bearish SFP label with manual chart reading.

Ask:

- Was an important level swept?
- Did price reclaim the level?
- Was there visible rejection?
- Did price cut straight through instead?
- Was the market stuck in low-amplitude chop?
- Was the candle marked as Conflict, Expansion, Retest, or Re-sweep instead of a primary SFP?

## 3. Adjust settings

Experiment with the indicator settings:

- Swing length.
- Chop lookback.
- Chop range threshold.
- Repeated touch settings.
- Expansion filter settings.
- Swing freshness and clustering settings.

The first values are only starting points.

## 4. Add alerts later

A later version may add TradingView alerts after the visual logic is reviewed. Alerts should be simple and easy to inspect.

## 5. Add paper trading later

Only after visual testing, the project may add a paper trading bot. Paper trading should be used to test rules without real funds.

## 6. Use exchange testnet only after validation

Exchange testnet support should come only after the indicator and paper trading logic are validated. Real trading and real exchange execution are not part of version 0.2.
