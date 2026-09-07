"""Legacy environment-variable compatibility for enterprise deployments.

Enterprise deploy tooling (``docker-compose*.yaml``, ``scripts/deploy.sh``)
still exports the pre-convergence ``IDEER_*`` variable names, while the
converged ``deerflow`` runtime reads the ``DEER_FLOW_*`` equivalents. Alias
the legacy names (never overriding an explicit new-style value) before any
config resolution runs. Import this module first in every enterprise process
entrypoint (Gateway app, workflow worker).
"""

from __future__ import annotations

import os

# legacy IDEER_* name -> upstream DEER_FLOW_* name
_LEGACY_ENV_ALIASES: dict[str, str] = {
    "IDEER_CONFIG_PATH": "DEER_FLOW_CONFIG_PATH",
    "IDEER_EXTENSIONS_CONFIG_PATH": "DEER_FLOW_EXTENSIONS_CONFIG_PATH",
    "IDEER_SKILLS_PATH": "DEER_FLOW_SKILLS_PATH",
    "IDEER_PROJECT_ROOT": "DEER_FLOW_PROJECT_ROOT",
    "IDEER_HOST_BASE_DIR": "DEER_FLOW_HOST_BASE_DIR",
    "IDEER_HOME": "DEER_FLOW_HOME",
}


def apply_legacy_env_aliases(environ: dict[str, str] | os._Environ | None = None) -> dict[str, str]:
    """Copy legacy ``IDEER_*`` values onto their ``DEER_FLOW_*`` equivalents.

    Returns the mappings that were applied (legacy name -> upstream name).
    """
    environ = os.environ if environ is None else environ
    applied: dict[str, str] = {}
    for legacy, modern in _LEGACY_ENV_ALIASES.items():
        value = environ.get(legacy)
        if value and not environ.get(modern):
            os.environ[modern] = value
            applied[legacy] = modern
    return applied


apply_legacy_env_aliases()
