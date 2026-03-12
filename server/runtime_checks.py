"""Runtime dependency and credential readiness checks."""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaudeRuntimeCheck:
    python_executable: str
    sdk_module: str
    sdk_available: bool
    api_key_env: str
    api_key_present: bool

    @property
    def ready(self) -> bool:
        return self.sdk_available and self.api_key_present


def check_claude_runtime() -> ClaudeRuntimeCheck:
    sdk_module = "anthropic"
    api_key_env = "ANTHROPIC_API_KEY"

    return ClaudeRuntimeCheck(
        python_executable=sys.executable,
        sdk_module=sdk_module,
        sdk_available=importlib.util.find_spec(sdk_module) is not None,
        api_key_env=api_key_env,
        api_key_present=bool(os.getenv(api_key_env)),
    )

