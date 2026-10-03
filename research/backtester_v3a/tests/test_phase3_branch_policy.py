from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

from research.backtester_v3a.branch_policy import (
    V3A_BRANCH_POLICY_VERSION,
    V3A_PRODUCTION_BRANCH,
    BranchPolicyError,
    require_v3a_production_branch,
)
from research.backtester_v3a.run_production_v3a import build_parser


class V3ABranchPolicyTests(unittest.TestCase):
    def test_policy_is_independent_and_versioned(self) -> None:
        self.assertEqual(V3A_BRANCH_POLICY_VERSION, "BACKTESTER_V3A_BRANCH_POLICY_V1")
        self.assertEqual(V3A_PRODUCTION_BRANCH, "backtester-v3a")

    def test_v3a_branch_passes(self) -> None:
        with patch(
            "research.backtester_v3a.branch_policy.current_git_branch",
            return_value="backtester-v3a",
        ):
            require_v3a_production_branch(Path("/repo"))

    def test_v2_branch_fails(self) -> None:
        with patch(
            "research.backtester_v3a.branch_policy.current_git_branch",
            return_value="backtester-v2",
        ):
            with self.assertRaisesRegex(BranchPolicyError, "backtester-v3a"):
                require_v3a_production_branch(Path("/repo"))

    def test_policy_does_not_import_v2_enforcement(self) -> None:
        source = inspect.getsource(
            __import__(
                "research.backtester_v3a.branch_policy",
                fromlist=["branch_policy"],
            ),
        )
        self.assertNotIn("strategy_replications", source)
        self.assertNotIn("backtester_v2", source)

    def test_v3a_cli_has_no_symbol_override(self) -> None:
        destinations = {action.dest for action in build_parser()._actions}
        self.assertNotIn("symbol", destinations)
