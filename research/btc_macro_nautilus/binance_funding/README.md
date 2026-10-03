# Official Binance BTCUSDT funding collector

Run a one-page real-data smoke, then resume the full collection:

```bash
python3 research/btc_macro_nautilus/binance_funding/collect_binance_funding.py \
  --mode smoke --data-root /path/to/Range-sfp-hedge-bot-data

python3 research/btc_macro_nautilus/binance_funding/collect_binance_funding.py \
  --mode collect --data-root /path/to/Range-sfp-hedge-bot-data
```

Rebuild and independently revalidate the normalized CSV without network use:

```bash
python3 research/btc_macro_nautilus/binance_funding/collect_binance_funding.py \
  --mode validate --data-root /path/to/Range-sfp-hedge-bot-data

python3 research/btc_macro_nautilus/binance_funding/validate_binance_funding.py \
  --data-root /path/to/Range-sfp-hedge-bot-data
```

See `CONTRACTS.md` for the source, precision, pagination, checkpoint, and
interval-review rules.
