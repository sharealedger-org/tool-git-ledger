"""
Git hooks integration for validating double-entry invariants before commit.
"""

from __future__ import annotations
import stat
import sys
from pathlib import Path
from .ledger import Ledger


PRE_COMMIT_SCRIPT = """#!/usr/bin/env bash
# git-ledger pre-commit hook: ensure double-entry integrity
set -e

echo "[git-ledger] Validating accounting ledger invariants..."
if command -v git-ledger >/dev/null 2>&1; then
    git-ledger check
elif command -v python3 >/dev/null 2>&1; then
    python3 -m gitledger.cli check
else
    echo "Warning: git-ledger not found in PATH, skipping ledger check."
fi
"""


def install_hook(repo_root: Path) -> Tuple[bool, str]:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return False, f"Not a git repository: {repo_root}"

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    with open(hook_file, "w", encoding="utf-8") as f:
        f.write(PRE_COMMIT_SCRIPT)

    # Make executable
    st = hook_file.stat()
    hook_file.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return True, f"Successfully installed pre-commit hook at {hook_file}"
