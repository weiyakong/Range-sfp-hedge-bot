from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from research.backtester_v2.engine import BacktestEngine
from research.backtester_v2.models import BacktestConfig, Bar
from research.backtester_v3a.data import InputContractLocators
from research.backtester_v3a.differential import (
    DifferentialError,
    assert_v2_v3a_equivalent,
)
from research.backtester_v3a.runner import (
    NormalizingStrategy,
    ProductionRunRequestV3A,
    RunnerError,
    canonical_config_sha256,
    run_production_v3a,
    validate_v3a_run,
)
from research.backtester_v3a.synthetic import (
    OneShotGeometryStrategy,
    synthetic_profiles,
)
from research.backtester_v3a.tests.phase3_support import (
    build_input_contracts,
    strategy_spec_payload,
    sha256_file,
    write_json,
)


class RunnerAndDifferentialTests(unittest.TestCase):
    def test_grid_valid_btc_differential_is_exact(self) -> None:
        bars = [
            Bar(0, 30_000, 30_020, 29_980, 30_010, 10),
            Bar(60_000, 30_010, 30_040, 30_000, 30_030, 10),
            Bar(120_000, 30_030, 30_050, 30_010, 30_040, 10),
        ]
        config = BacktestConfig(
            initial_cash=10_000,
            maker_fee_rate=0.0002,
            taker_fee_rate=0.0004,
            slippage_rate=0.0001,
            end_of_data_policy="force_close",
            funding_rate_by_time={120_000: 0.001},
            funding_price_by_time={120_000: 30_030.0},
            funding_data_verified=True,
        )
        v2_strategy = OneShotGeometryStrategy("long", 0.01)
        raw_v3_strategy = OneShotGeometryStrategy("long", 0.01)
        profile = synthetic_profiles()["BTC-like"]
        v3_strategy = NormalizingStrategy(raw_v3_strategy, profile.metadata)
        v2 = BacktestEngine(config).run(bars, v2_strategy)
        v3 = BacktestEngine(config).run(bars, v3_strategy)
        assert_v2_v3a_equivalent(
            v2,
            v3,
            v2_intents=v2_strategy.emitted_intents,
            v3a_intents=v3_strategy.normalized_intents,
        )

    def test_unexplained_numeric_difference_fails(self) -> None:
        bars = [Bar(0, 100, 101, 99, 100, 10)]
        result = BacktestEngine(BacktestConfig()).run(
            bars, OneShotGeometryStrategy("long", 1.0),
        )
        changed = replace(result, final_cash=result.final_cash + 0.01)
        with self.assertRaises(DifferentialError):
            assert_v2_v3a_equivalent(result, changed, [], [])

    def test_three_synthetic_profiles_have_distinct_microstructure(self) -> None:
        profiles = synthetic_profiles()
        self.assertEqual(set(profiles), {"BTC-like", "ETH-like", "SOL/alt-like"})
        tuples = {
            (
                item.base_price,
                item.metadata.tick_size,
                item.metadata.step_size,
                item.metadata.min_qty,
                item.metadata.min_notional,
            )
            for item in profiles.values()
        }
        self.assertEqual(len(tuples), 3)

    def test_synthetic_profiles_have_same_logical_behavior(self) -> None:
        signatures = []
        for profile in synthetic_profiles().values():
            bars = profile.bars()
            raw_strategy = OneShotGeometryStrategy("long", profile.grid_valid_qty)
            strategy = NormalizingStrategy(raw_strategy, profile.metadata)
            result = BacktestEngine(
                BacktestConfig(end_of_data_policy="force_close"),
            ).run(bars, strategy)
            signatures.append((
                len(result.trades),
                result.trades[0].side,
                result.trades[0].entry_bar_time,
                result.trades[0].exit_reason,
                result.qa_status,
            ))
        self.assertEqual(len(set(signatures)), 1)

    def test_atomic_runner_persists_and_revalidates_identity_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = build_input_contracts(root)
            config = BacktestConfig(
                end_of_data_policy="force_close",
                funding_rate_by_time={120_000: 0.001},
                funding_price_by_time={120_000: 102.0},
                mark_price_data_verified=True,
                funding_data_verified=True,
            )
            spec_payload = strategy_spec_payload(
                paths,
                execution_config_sha256=canonical_config_sha256(config),
            )
            spec_path = root / "strategy-spec-v2.json"
            config_path = root / "config.json"
            write_json(spec_path, spec_payload)
            write_json(config_path, json.loads(json.dumps(config, default=lambda x: x.__dict__)))
            output_dir = root / "run-output"
            request = ProductionRunRequestV3A(
                repo_root=Path.cwd(),
                spec_path=spec_path,
                config_path=config_path,
                inputs=InputContractLocators(
                    trade_price=paths["trade_price"],
                    funding=paths["funding"],
                    mark_price=paths["mark_price"],
                    instrument_metadata=paths["instrument_metadata"],
                ),
                required_start_ms=0,
                required_end_ms=120_000,
                output_dir=output_dir,
                state_path=root / "v3a-state.sqlite3",
            )
            with patch(
                "research.backtester_v3a.runner.require_v3a_production_branch",
            ):
                outcome = run_production_v3a(request)
            self.assertTrue(outcome.receipt_path.is_file())
            self.assertTrue((output_dir / "result.json").is_file())
            validate_v3a_run(
                repo_root=Path.cwd(),
                output_dir=output_dir,
                spec_path=spec_path,
                inputs=request.inputs,
                state_path=request.state_path,
            )
            result_path = output_dir / "result.json"
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            result_payload["result"]["final_cash"] += 1.0
            write_json(result_path, result_payload)
            manifest_path = output_dir / "output_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checksums"]["result.json"] = sha256_file(result_path)
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(RunnerError, "execution_id"):
                validate_v3a_run(
                    repo_root=Path.cwd(),
                    output_dir=output_dir,
                    spec_path=spec_path,
                    inputs=request.inputs,
                    state_path=request.state_path,
                )
