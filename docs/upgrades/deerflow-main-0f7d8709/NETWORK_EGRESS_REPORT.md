# Network egress acceptance report

## Default policy

`config.intranet.yaml` configures the sandbox with:

```yaml
network:
  mode: isolated
  allow_domains: []
  approval: deny
```

Community Web/MCP providers are not enabled by the intranet tool projection.
Any internal endpoint must be added explicitly by the deployment operator.

## Evidence collected

| Check | Result | Evidence |
|---|---|---|
| Intranet config contract | passed | `backend/tests/test_intranet_config_contract.py` |
| Sandbox network schema | passed | `backend/tests/test_sandbox_network_config.py` (13 tests combined with the intranet contract) |
| Compose/launcher readiness boundary | passed | `backend/tests/test_gateway_startup.py` (5 tests) plus startup extension checks (9 tests) |
| Offline pre-check | environment-blocked | `scripts/check-intranet.sh` correctly reports missing Docker Compose, images and generated `env.intranet`; config and port checks pass |
| Offline bundle build | environment-blocked | `scripts/package-intranet-offline.sh` exits immediately with `docker compose v2 is required` |
| Air-gapped fresh install | not run | Requires a prepared bundle and disconnected deployment host |

## Gate status

The default-deny policy is implemented and locally verified. The network
egress and offline delivery gate remains **open** until a real bundle is
prepared, checked, and installed in a disconnected environment.

The deployment-script unit suite was started with plugin autoload disabled;
its first fourteen tests completed before a subprocess-backed case produced no
output within the guarded window. It is recorded as incomplete rather than
green; no deployment code was changed to accommodate the restricted sandbox.
