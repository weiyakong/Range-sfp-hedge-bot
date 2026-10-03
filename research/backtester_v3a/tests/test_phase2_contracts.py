from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional

from research.backtester_v3a.contracts import (
    ATTESTATION_SCHEMA,
    DATASET_IDENTITY_SCHEMA,
    INSTRUMENT_METADATA_SCHEMA,
    RECEIPT_SCHEMA,
    RESULT_METADATA_SCHEMA,
    STRATEGY_SPEC_SCHEMA,
    ContractError,
    DatasetIdentity,
    ExecutionAttestationV3A,
    InstrumentMetadata,
    ResultMetadataV3A,
    RunReceiptV3A,
    StrategySpecV2,
    bind_execution_contracts,
    canonical_sha256,
    parse_dataset_identity,
    parse_execution_attestation,
    parse_instrument_metadata,
    parse_result_metadata,
    parse_run_receipt,
    parse_strategy_spec_v2,
    require_dataset_coverage,
    require_downstream_symbol,
    revalidate_identity_chain,
)
from research.backtester_v3a.state import (
    STATE_SCHEMA,
    V3A_STATE_RELATIVE_PATH,
    RunStateIdentity,
    initialize_state,
    insert_run_identity,
    load_run_identity,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
HASH_F = "f" * 64


def execution_identity(symbol: str = "BTCUSDT") -> Dict[str, object]:
    return {
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "execution_timeframe": "1m",
        "timezone": "UTC",
        "timestamp_semantics": "bar open UTC",
    }


def dataset_payload(
    role: str,
    symbol: str = "BTCUSDT",
    *,
    data_timeframe: Optional[str] = None,
) -> Dict[str, object]:
    if data_timeframe is None:
        data_timeframe = "event" if role == "funding" else "1m"
    return {
        "schema_version": DATASET_IDENTITY_SCHEMA,
        "role": role,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "data_timeframe": data_timeframe,
        "timezone": "UTC",
        "timestamp_semantics": (
            "funding event UTC" if role == "funding" else "bar open UTC"
        ),
        "dataset_id": f"FIXTURE-{role}-{symbol}",
        "dataset_sha256": HASH_A,
        "manifest_path": f"/frozen/{symbol}/{role}-manifest.json",
        "manifest_id": f"FIXTURE-{role}-MANIFEST",
        "manifest_sha256": HASH_B,
        "coverage_start_ms": 1_000,
        "coverage_end_ms": 2_000,
    }


def metadata_payload(
    symbol: str = "BTCUSDT",
    *,
    fidelity: str = "HISTORICAL_VERIFIED",
) -> Dict[str, object]:
    historical = fidelity == "HISTORICAL_VERIFIED"
    return {
        "schema_version": INSTRUMENT_METADATA_SCHEMA,
        "exchange": "Binance",
        "market": "USD-M perpetual",
        "symbol": symbol,
        "metadata_id": f"FIXTURE-METADATA-{symbol}",
        "tick_size": "0.10",
        "step_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "5",
        "price_precision": 2,
        "quantity_precision": 3,
        "provenance": {
            "fidelity_classification": fidelity,
            "source": "frozen fixture",
            "source_sha256": HASH_C,
            "effective_start_ms": 1_000 if historical else None,
            "effective_end_ms": 2_000 if historical else None,
        },
    }


def strategy_payload(
    symbol: str = "BTCUSDT",
    *,
    trade_hash: str,
    funding_hash: Optional[str],
    mark_hash: Optional[str],
    metadata_hash: str,
) -> Dict[str, object]:
    parameters = {"fast_length": 10, "slow_length": 20}

    def requirement(contract_hash: Optional[str]) -> Dict[str, object]:
        if contract_hash is None:
            return {
                "mode": "EXPLICITLY_NOT_USED",
                "contract_sha256": None,
                "absence_policy": "EXPLICITLY_NOT_USED_BY_FROZEN_SPEC",
            }
        return {
            "mode": "REQUIRED",
            "contract_sha256": contract_hash,
            "absence_policy": None,
        }

    return {
        "schema_version": STRATEGY_SPEC_SCHEMA,
        "status": "FROZEN",
        "strategy_id": "MA-CROSS",
        "strategy_version": "V2",
        "candidate_id": "C001",
        "variant_id": "C001-V2",
        "execution_identity": execution_identity(symbol),
        "implementation": {
            "strategy_entrypoint": "MaCrossStrategy",
            "parameters": parameters,
            "parameters_sha256": canonical_sha256(parameters),
            "execution_config_sha256": HASH_D,
        },
        "data_requirements": {
            "trade_price": requirement(trade_hash),
            "funding": requirement(funding_hash),
            "mark_price": requirement(mark_hash),
            "instrument_metadata": requirement(metadata_hash),
        },
    }


def bound_fixture(
    symbol: str = "BTCUSDT",
    *,
    require_funding: bool = True,
    require_mark: bool = True,
):
    trade_payload = dataset_payload("trade_price", symbol)
    funding_payload = dataset_payload("funding", symbol) if require_funding else None
    mark_payload = dataset_payload("mark_price", symbol) if require_mark else None
    meta_payload = metadata_payload(symbol)
    spec_payload = strategy_payload(
        symbol,
        trade_hash=canonical_sha256(trade_payload),
        funding_hash=canonical_sha256(funding_payload) if funding_payload else None,
        mark_hash=canonical_sha256(mark_payload) if mark_payload else None,
        metadata_hash=canonical_sha256(meta_payload),
    )
    spec = parse_strategy_spec_v2(spec_payload)
    trade = parse_dataset_identity(trade_payload)
    funding = parse_dataset_identity(funding_payload) if funding_payload else None
    mark = parse_dataset_identity(mark_payload) if mark_payload else None
    metadata = parse_instrument_metadata(meta_payload)
    bound = bind_execution_contracts(
        spec,
        trade_price=trade,
        funding=funding,
        mark_price=mark,
        instrument_metadata=metadata,
    )
    return spec_payload, spec, trade, funding, mark, metadata, bound


def identity_artifacts(spec_payload, spec: StrategySpecV2, bound):
    spec_hash = canonical_sha256(spec_payload)
    result_payload = {
        "schema_version": RESULT_METADATA_SCHEMA,
        "run_id": "RUN-1",
        "execution_identity": spec.execution_identity.to_payload(),
        "strategy_spec_sha256": spec_hash,
        "strategy_entrypoint": spec.strategy_entrypoint,
        "strategy_parameters_sha256": spec.parameters_sha256,
        **bound.contract_hash_payload(),
    }
    result = parse_result_metadata(result_payload)
    attestation_payload = {
        "schema_version": ATTESTATION_SCHEMA,
        "run_id": "RUN-1",
        "execution_id": "EXEC-1",
        "execution_identity": spec.execution_identity.to_payload(),
        "strategy_spec_sha256": spec_hash,
        "strategy_entrypoint": spec.strategy_entrypoint,
        "strategy_parameters_sha256": spec.parameters_sha256,
        **bound.contract_hash_payload(),
        "result_metadata_sha256": canonical_sha256(result_payload),
        "code_identity_sha256": HASH_E,
    }
    attestation = parse_execution_attestation(attestation_payload)
    receipt_payload = {
        "schema_version": RECEIPT_SCHEMA,
        "authority": "ATOMIC_PRODUCTION_RUNNER_V3A",
        "run_id": "RUN-1",
        "execution_id": "EXEC-1",
        "execution_identity": spec.execution_identity.to_payload(),
        "strategy_spec_sha256": spec_hash,
        "strategy_entrypoint": spec.strategy_entrypoint,
        "strategy_parameters_sha256": spec.parameters_sha256,
        **bound.contract_hash_payload(),
        "result_metadata_sha256": canonical_sha256(result_payload),
        "execution_attestation_sha256": canonical_sha256(attestation_payload),
        "code_identity_sha256": HASH_E,
    }
    receipt = parse_run_receipt(receipt_payload)
    state = RunStateIdentity.from_receipt(receipt)
    return (
        result_payload,
        result,
        attestation_payload,
        attestation,
        receipt_payload,
        receipt,
        state,
    )


class StrategySpecV2ContractTests(unittest.TestCase):
    def test_execution_identity_requires_execution_timeframe(self) -> None:
        payload = execution_identity()
        payload["timeframe"] = payload.pop("execution_timeframe")
        trade = dataset_payload("trade_price")
        metadata = metadata_payload()
        spec = strategy_payload(
            trade_hash=canonical_sha256(trade), funding_hash=None,
            mark_hash=None, metadata_hash=canonical_sha256(metadata),
        )
        spec["execution_identity"] = payload
        with self.assertRaisesRegex(ContractError, "execution_timeframe"):
            parse_strategy_spec_v2(spec)

    def test_strategy_entrypoint_is_not_instrument_symbol(self) -> None:
        spec_payload, spec, *_ = bound_fixture(require_funding=False, require_mark=False)
        self.assertEqual(spec.execution_identity.symbol, "BTCUSDT")
        self.assertEqual(spec.strategy_entrypoint, "MaCrossStrategy")
        self.assertNotIn("strategy_symbol", json.dumps(spec_payload))

    def test_parameters_hash_is_verified(self) -> None:
        spec_payload, *_ = bound_fixture(require_funding=False, require_mark=False)
        spec_payload["implementation"]["parameters_sha256"] = HASH_F
        with self.assertRaisesRegex(ContractError, "parameters_sha256"):
            parse_strategy_spec_v2(spec_payload)

    def test_symbol_case_mismatch_is_rejected(self) -> None:
        trade = dataset_payload("trade_price", "btcusdt")
        metadata = metadata_payload("btcusdt")
        spec = strategy_payload(
            "btcusdt", trade_hash=canonical_sha256(trade), funding_hash=None,
            mark_hash=None, metadata_hash=canonical_sha256(metadata),
        )
        with self.assertRaisesRegex(ContractError, "uppercase"):
            parse_strategy_spec_v2(spec)

    def test_strategy_attempt_to_override_symbol_fails(self) -> None:
        with self.assertRaisesRegex(ContractError, "strategy.symbol"):
            require_downstream_symbol("BTCUSDT", "ETHUSDT", "strategy.symbol")

    def test_config_symbol_mismatch_fails(self) -> None:
        with self.assertRaisesRegex(ContractError, "config.symbol"):
            require_downstream_symbol("BTCUSDT", "SOLUSDT", "config.symbol")

    def test_exact_downstream_symbol_passes(self) -> None:
        require_downstream_symbol("SOLUSDT", "SOLUSDT", "result.symbol")


class InputIdentityBindingTests(unittest.TestCase):
    def test_btc_contract_bundle_passes(self) -> None:
        *_, bound = bound_fixture("BTCUSDT")
        self.assertEqual(bound.execution_identity.symbol, "BTCUSDT")

    def test_eth_contract_bundle_passes(self) -> None:
        *_, bound = bound_fixture("ETHUSDT")
        self.assertEqual(bound.execution_identity.symbol, "ETHUSDT")

    def test_sol_contract_bundle_passes(self) -> None:
        *_, bound = bound_fixture("SOLUSDT")
        self.assertEqual(bound.execution_identity.symbol, "SOLUSDT")

    def test_eth_spec_plus_btc_bars_fails(self) -> None:
        spec_payload, spec, _, funding, mark, metadata, _ = bound_fixture("ETHUSDT")
        del spec_payload
        wrong_trade = parse_dataset_identity(dataset_payload("trade_price", "BTCUSDT"))
        with self.assertRaisesRegex(ContractError, "trade_price.symbol"):
            bind_execution_contracts(
                spec, trade_price=wrong_trade, funding=funding,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_sol_spec_plus_eth_funding_fails(self) -> None:
        _, spec, trade, _, mark, metadata, _ = bound_fixture("SOLUSDT")
        wrong_funding = parse_dataset_identity(dataset_payload("funding", "ETHUSDT"))
        with self.assertRaisesRegex(ContractError, "funding.symbol"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=wrong_funding,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_btc_spec_plus_sol_mark_price_fails(self) -> None:
        _, spec, trade, funding, _, metadata, _ = bound_fixture("BTCUSDT")
        wrong_mark = parse_dataset_identity(dataset_payload("mark_price", "SOLUSDT"))
        with self.assertRaisesRegex(ContractError, "mark_price.symbol"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=funding,
                mark_price=wrong_mark, instrument_metadata=metadata,
            )

    def test_wrong_symbol_metadata_fails(self) -> None:
        _, spec, trade, funding, mark, _, _ = bound_fixture("BTCUSDT")
        wrong_metadata = parse_instrument_metadata(metadata_payload("ETHUSDT"))
        with self.assertRaisesRegex(ContractError, "instrument_metadata.symbol"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=funding,
                mark_price=mark, instrument_metadata=wrong_metadata,
            )

    def test_wrong_exchange_or_market_fails(self) -> None:
        _, spec, trade, funding, mark, metadata, _ = bound_fixture("BTCUSDT")
        for field, value in (
            ("exchange", "OtherExchange"),
            ("market", "spot"),
        ):
            with self.subTest(field=field):
                payload = dataset_payload("trade_price")
                payload[field] = value
                wrong_trade = parse_dataset_identity(payload)
                with self.assertRaisesRegex(ContractError, f"trade_price.{field}"):
                    bind_execution_contracts(
                        spec, trade_price=wrong_trade, funding=funding,
                        mark_price=mark, instrument_metadata=metadata,
                    )

    def test_missing_required_funding_fails(self) -> None:
        _, spec, trade, _, mark, metadata, _ = bound_fixture("BTCUSDT")
        with self.assertRaisesRegex(ContractError, "funding is required"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=None,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_missing_required_trade_price_fails(self) -> None:
        _, spec, _, funding, mark, metadata, _ = bound_fixture("BTCUSDT")
        with self.assertRaisesRegex(ContractError, "trade_price is required"):
            bind_execution_contracts(
                spec, trade_price=None, funding=funding,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_missing_required_metadata_fails(self) -> None:
        _, spec, trade, funding, mark, _, _ = bound_fixture("BTCUSDT")
        with self.assertRaisesRegex(ContractError, "instrument_metadata is required"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=funding,
                mark_price=mark, instrument_metadata=None,
            )

    def test_missing_required_mark_price_fails(self) -> None:
        _, spec, trade, funding, _, metadata, _ = bound_fixture("BTCUSDT")
        with self.assertRaisesRegex(ContractError, "mark_price is required"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=funding,
                mark_price=None, instrument_metadata=metadata,
            )

    def test_explicit_not_used_inputs_must_remain_absent(self) -> None:
        _, spec, trade, _, _, metadata, _ = bound_fixture(
            "BTCUSDT", require_funding=False, require_mark=False,
        )
        unexpected_funding = parse_dataset_identity(dataset_payload("funding"))
        with self.assertRaisesRegex(ContractError, "explicitly not used"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=unexpected_funding,
                mark_price=None, instrument_metadata=metadata,
            )

    def test_contract_hash_mismatch_fails(self) -> None:
        spec_payload, _, trade, funding, mark, metadata, _ = bound_fixture("BTCUSDT")
        spec_payload["data_requirements"]["trade_price"]["contract_sha256"] = HASH_F
        spec = parse_strategy_spec_v2(spec_payload)
        with self.assertRaisesRegex(ContractError, "trade_price.contract_sha256"):
            bind_execution_contracts(
                spec, trade_price=trade, funding=funding,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_trade_execution_timeframe_mismatch_fails(self) -> None:
        _, spec, _, funding, mark, metadata, _ = bound_fixture("BTCUSDT")
        wrong_trade_payload = dataset_payload("trade_price", data_timeframe="5m")
        wrong_trade = parse_dataset_identity(wrong_trade_payload)
        with self.assertRaisesRegex(ContractError, "execution_timeframe"):
            bind_execution_contracts(
                spec, trade_price=wrong_trade, funding=funding,
                mark_price=mark, instrument_metadata=metadata,
            )

    def test_dataset_coverage_mismatch_fails(self) -> None:
        _, _, trade, *_ = bound_fixture("BTCUSDT")
        with self.assertRaisesRegex(ContractError, "coverage"):
            require_dataset_coverage(
                trade, required_start_ms=500, required_end_ms=1_500,
                path="trade_price",
            )

    def test_dataset_coverage_containment_passes(self) -> None:
        _, _, trade, *_ = bound_fixture("BTCUSDT")
        require_dataset_coverage(
            trade, required_start_ms=1_100, required_end_ms=1_900,
            path="trade_price",
        )


class InstrumentMetadataContractTests(unittest.TestCase):
    def test_historical_metadata_requires_effective_times(self) -> None:
        payload = metadata_payload()
        payload["provenance"]["effective_end_ms"] = None
        with self.assertRaisesRegex(ContractError, "effective"):
            parse_instrument_metadata(payload)

    def test_static_proxy_is_explicit(self) -> None:
        metadata = parse_instrument_metadata(
            metadata_payload(fidelity="STATIC_CURRENT_PROXY")
        )
        self.assertEqual(
            metadata.provenance.fidelity_classification,
            "STATIC_CURRENT_PROXY",
        )

    def test_non_positive_precision_value_fails(self) -> None:
        payload = metadata_payload()
        payload["step_size"] = "0"
        with self.assertRaisesRegex(ContractError, "step_size"):
            parse_instrument_metadata(payload)


class ArtifactAndStateMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = bound_fixture("BTCUSDT")
        self.spec_payload, self.spec, *rest = self.fixture
        self.bound = rest[-1]
        self.artifacts = identity_artifacts(
            self.spec_payload, self.spec, self.bound,
        )

    def test_complete_identity_chain_passes(self) -> None:
        _, result, _, attestation, _, receipt, state = self.artifacts
        revalidate_identity_chain(
            self.spec, self.bound, result, attestation, receipt, state,
        )

    def test_result_symbol_mutation_fails(self) -> None:
        result_payload, _, _, attestation, _, receipt, state = self.artifacts
        result_payload["execution_identity"]["symbol"] = "ETHUSDT"
        result = parse_result_metadata(result_payload)
        with self.assertRaisesRegex(ContractError, "result.execution_identity"):
            revalidate_identity_chain(
                self.spec, self.bound, result, attestation, receipt, state,
            )

    def test_attestation_symbol_mutation_fails(self) -> None:
        _, result, attestation_payload, _, _, receipt, state = self.artifacts
        attestation_payload["execution_identity"]["symbol"] = "ETHUSDT"
        attestation = parse_execution_attestation(attestation_payload)
        with self.assertRaisesRegex(ContractError, "attestation.execution_identity"):
            revalidate_identity_chain(
                self.spec, self.bound, result, attestation, receipt, state,
            )

    def test_receipt_symbol_mutation_fails(self) -> None:
        _, result, _, attestation, receipt_payload, _, state = self.artifacts
        receipt_payload["execution_identity"]["symbol"] = "ETHUSDT"
        receipt = parse_run_receipt(receipt_payload)
        with self.assertRaisesRegex(ContractError, "receipt.execution_identity"):
            revalidate_identity_chain(
                self.spec, self.bound, result, attestation, receipt, state,
            )

    def test_frozen_spec_symbol_mutation_fails(self) -> None:
        _, result, _, attestation, _, receipt, state = self.artifacts
        mutated = json.loads(json.dumps(self.spec_payload))
        mutated["execution_identity"]["symbol"] = "ETHUSDT"
        spec = parse_strategy_spec_v2(mutated)
        with self.assertRaises(ContractError):
            revalidate_identity_chain(
                spec, self.bound, result, attestation, receipt, state,
            )

    def test_sqlite_symbol_mutation_fails(self) -> None:
        _, result, _, attestation, _, receipt, state = self.artifacts
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3a.sqlite3"
            initialize_state(path)
            insert_run_identity(path, state)
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "UPDATE runs SET symbol='ETHUSDT' WHERE run_id='RUN-1'"
                )
                connection.commit()
            finally:
                connection.close()
            mutated_state = load_run_identity(path, "RUN-1")
            with self.assertRaisesRegex(ContractError, "state.execution_identity"):
                revalidate_identity_chain(
                    self.spec, self.bound, result, attestation, receipt,
                    mutated_state,
                )

    def test_non_complete_sqlite_state_fails(self) -> None:
        _, result, _, attestation, _, receipt, state = self.artifacts
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v3a.sqlite3"
            initialize_state(path)
            insert_run_identity(path, state)
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "UPDATE runs SET status='FAILED' WHERE run_id='RUN-1'"
                )
                connection.commit()
            finally:
                connection.close()
            failed_state = load_run_identity(path, "RUN-1")
            with self.assertRaisesRegex(ContractError, "state.status"):
                revalidate_identity_chain(
                    self.spec, self.bound, result, attestation, receipt,
                    failed_state,
                )

    def test_v3a_state_is_physically_separate_from_v2(self) -> None:
        self.assertEqual(STATE_SCHEMA, "BACKTESTER_V3A_STATE_V1")
        self.assertNotEqual(
            V3A_STATE_RELATIVE_PATH,
            Path(".strategy-replication/enforcement-v2.sqlite3"),
        )
        self.assertIn("v3a", str(V3A_STATE_RELATIVE_PATH).lower())


class CheckedInSchemaTests(unittest.TestCase):
    def test_versioned_schema_files_exist_and_use_approved_names(self) -> None:
        schema_dir = Path(__file__).resolve().parents[1] / "schemas"
        expected = {
            "strategy_spec_v2.schema.json": STRATEGY_SPEC_SCHEMA,
            "dataset_identity_v1.schema.json": DATASET_IDENTITY_SCHEMA,
            "instrument_metadata_v1.schema.json": INSTRUMENT_METADATA_SCHEMA,
            "result_metadata_v1.schema.json": RESULT_METADATA_SCHEMA,
            "execution_attestation_v1.schema.json": ATTESTATION_SCHEMA,
            "run_receipt_v1.schema.json": RECEIPT_SCHEMA,
        }
        for filename, version in expected.items():
            with self.subTest(filename=filename):
                payload = json.loads((schema_dir / filename).read_text(encoding="utf-8"))
                self.assertEqual(payload["properties"]["schema_version"]["const"], version)
        strategy_schema = json.loads(
            (schema_dir / "strategy_spec_v2.schema.json").read_text(encoding="utf-8")
        )
        identity = strategy_schema["$defs"]["execution_identity"]
        self.assertIn("execution_timeframe", identity["required"])
        self.assertNotIn("timeframe", identity["properties"])
        implementation = strategy_schema["properties"]["implementation"]
        self.assertIn("strategy_entrypoint", implementation["required"])
        self.assertNotIn("strategy_symbol", implementation["properties"])


if __name__ == "__main__":
    unittest.main()
