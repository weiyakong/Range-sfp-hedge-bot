# Strategy Overview

Version: **0.1**

The Range SFP Hedge Bot concept is based on visually studying how BTC reacts around important price levels. In this version, the project is only an indicator and documentation. It is not a trading bot and does not execute orders.

## Core idea

The strategy looks for possible reactions near important levels where traders may have placed stops or where liquidity may be resting.

Important levels include:

- Daily high and daily low.
- Weekly high and weekly low.
- Monthly high and monthly low.
- Recent swing high and swing low.

## Sweep and reclaim

A possible SFP setup happens when price briefly moves beyond an important level and then reclaims the level.

Examples:

- **Bearish SFP idea:** price sweeps above a previous high, then closes back below that high.
- **Bullish SFP idea:** price sweeps below a previous low, then closes back above that low.

The reclaim matters because it shows that the breakout may have failed.

## When to avoid a trade idea

A setup should be ignored if price simply cuts through the level without rejection. A clean break through a level is different from a sweep and reclaim.

A setup should also be avoided in low-amplitude chop. If price keeps touching the same small zone without meaningful expansion or rejection, the signal may not be useful.

## Risk rules

Confluence can make a level more interesting, but it must not increase risk. For example, if a daily level and swing level are close together, the idea may be more visible, but the risk should not be increased because of that.

Risk per trade must not exceed **1%** of the account. Lower risk may be more appropriate, especially while testing.

## Future additions

Possible future analysis tools include:

- Value Area High (VAH).
- Value Area Low (VAL).
- Point of Control (POC).
- Anchored VWAP.
- Low Volume Nodes (LVN).
- Fibonacci levels.
- Protected runner logic for partially managing a position after initial profit.

These additions should be tested visually first before any paper trading or automation is considered.
