"""Pytest session-wide configuration.

This file is loaded by pytest BEFORE any test module is collected, so env-var
mutations here are visible to modules imported during the test run.

What we set:

- ``ADMIN_AUTH_SKIP_STARTUP_VALIDATION=true``
  Tells ``src.agent_service.core.config._validate_admin_auth_config`` to return
  immediately on import. Replaces the previous ``"pytest" in sys.modules`` skip
  (review finding #7), which was too broad — it hid validation from tests that
  specifically wanted to cover the validator's failure modes.

Tests that specifically want to exercise the validator (e.g.
``test_validate_admin_auth_config_raises_on_missing_secret``) must:
  1. Delete the env var: ``monkeypatch.delenv("ADMIN_AUTH_SKIP_STARTUP_VALIDATION")``
  2. Reload the module: ``importlib.reload(config)``
"""

from __future__ import annotations

import os

os.environ.setdefault("ADMIN_AUTH_SKIP_STARTUP_VALIDATION", "true")
