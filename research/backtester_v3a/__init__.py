"""Symbol-agnostic single-instrument contracts for Backtester V3-A."""

from .contracts import (
    ContractError,
    DatasetIdentity,
    ExecutionIdentity,
    InstrumentMetadata,
    StrategySpecV2,
    bind_execution_contracts,
)

__all__ = [
    "ContractError",
    "DatasetIdentity",
    "ExecutionIdentity",
    "InstrumentMetadata",
    "StrategySpecV2",
    "bind_execution_contracts",
]
