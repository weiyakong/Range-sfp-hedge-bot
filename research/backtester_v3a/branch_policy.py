"""Independent versioned production-branch policy for Backtester V3-A."""

from __future__ import annotations

import subprocess
from pathlib import Path


V3A_BRANCH_POLICY_VERSION = "BACKTESTER_V3A_BRANCH_POLICY_V1"
V3A_PRODUCTION_BRANCH = "backtester-v3a"


class BranchPolicyError(ValueError):
    """Raised when a V3-A production run is attempted on the wrong branch."""


def current_git_branch(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root.resolve(),
        check=True,
        capture_output=True,
        text=True,
    )
    branch = completed.stdout.strip()
    if not branch:
        raise BranchPolicyError("V3-A production research requires an attached branch")
    return branch


def require_v3a_production_branch(repo_root: Path) -> None:
    """Enforce the V3-A branch without consulting V2 enforcement."""
    branch = current_git_branch(repo_root)
    if branch != V3A_PRODUCTION_BRANCH:
        raise BranchPolicyError(
            "V3-A production research requires branch "
            f"{V3A_PRODUCTION_BRANCH}; actual branch is {branch}",
        )


__all__ = [
    "V3A_BRANCH_POLICY_VERSION",
    "V3A_PRODUCTION_BRANCH",
    "BranchPolicyError",
    "current_git_branch",
    "require_v3a_production_branch",
]
