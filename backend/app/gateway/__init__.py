# Keep the submodule available as ``app.gateway.app``.  Do not bind the
# FastAPI instance to the package-level ``app`` name: Python's dotted-import
# form must resolve to the module for tooling and tests that monkeypatch its
# startup seams.
from .app import create_app
from .config import GatewayConfig, get_gateway_config

__all__ = ["create_app", "GatewayConfig", "get_gateway_config"]
