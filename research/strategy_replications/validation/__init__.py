"""Validation and immutable-receipt helpers for strategy replication."""

from .core import (
    ValidationReport,
    compute_fidelity_summary,
    create_freeze_receipt,
    create_run_receipt,
    derived_registry_counts,
    validate_candidate_registry,
    validate_capability_manifest,
    validate_evaluation_protocol,
    validate_freeze_receipt,
    validate_freeze_inputs,
    validate_production_preflight,
    validate_run_lineage,
    validate_strategy_spec,
)

__all__ = [
    "ValidationReport",
    "compute_fidelity_summary",
    "create_freeze_receipt",
    "create_run_receipt",
    "derived_registry_counts",
    "validate_candidate_registry",
    "validate_capability_manifest",
    "validate_evaluation_protocol",
    "validate_freeze_receipt",
    "validate_freeze_inputs",
    "validate_production_preflight",
    "validate_run_lineage",
    "validate_strategy_spec",
]
