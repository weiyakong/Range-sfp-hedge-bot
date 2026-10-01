# Structural contract authority

The standard-library Python validators in
`research/strategy_replications/validation/core.py` are the only authoritative
structural and semantic contract for Strategy Replication Enforcement V1.

The earlier JSON Schema sketches were removed during adversarial-audit
remediation because they were not executed at runtime and could diverge from
the effective validators. No document in this directory is an alternate
machine authority.
