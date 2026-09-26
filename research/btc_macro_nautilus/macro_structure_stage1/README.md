# Macro Structure Stage 1

Unsupervised, label-free diagnostics for the validated futures macro-segment
aggregate table. The pipeline builds an explicit feature registry, audits
confounders, normalizes only algebraically unambiguous direction-sensitive
features, reduces redundancy, and analyzes each timeframe/family separately.

It uses fixed-seed NumPy PCA, distance diagnostics, limited k-means candidates,
and subsampling/feature-subset co-assignment stability. No impulse/correction
labels, classifiers, semantic cluster names, or FibTime artifacts are consumed.

```bash
python3 research/btc_macro_nautilus/macro_structure_stage1/build_macro_structure_stage1.py \
  --data-root /path/to/Range-sfp-hedge-bot-data \
  --repo-root .
```
