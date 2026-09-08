# External acceptance handoff — deerflow-main-0f7d8709

This round closed every convergence item executable in the development
sandbox. Three acceptance items remain that require environments this
sandbox does not have. Each entry below states the precondition, the exact
commands, the expected evidence, and where to record the result so the
integration PR (§28) can be completed.

Upstream lock: `0f7d8709d3bbf0be26460b6277fbad9329302243`.

---

## 1. Offline bundle build + intranet pre-deploy checks (Gate 8, §24-J)

**Precondition:** Docker Engine + Compose v2 reachable from the shell
(`docker info` succeeds). This sandbox has no Docker daemon.

```bash
# 1. Build the air-gapped bundle (images + wheels + frontend + resources).
bash scripts/package-intranet-offline.sh          # add --incremental for deltas

# 2. Pre-deploy checks run from the bundle root next to the tars.
cp config.intranet.yaml env.intranet              # per deploy-intranet.sh prepare
bash scripts/check-intranet.sh
```

**Expected evidence:** `package-intranet-offline.sh` exits 0 and prints the
bundle directory with SHA256 checksums; `check-intranet.sh` passes all 8
steps (images loaded, `env.intranet` present, port free, disk ≥ 10GB).

**Then — air-gap fresh install (§24-J, hard §29 DoD):** on an isolated host
with no public DNS/routes, install the bundle, then walk the §24-J checklist:
install → login → vLLM → file upload → Office → Resource → Workflow → Memory
→ Subagent → history/restart.

**Record to:** `BASELINE_REPORT.md` new session addendum + `PR_MATERIALS.md`
lane table (`check-intranet`, `offline fresh install` rows).

## 2. PostgreSQL migration acceptance (Gate 5) — **CLOSED 2026-09-08** (see MIGRATION_ACCEPTANCE_REPORT.md)

<details><summary>Original instructions</summary>

**Precondition:** any PostgreSQL 14+ endpoint reachable from the backend
(`psql` or Docker `postgres:16`).

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://ideer:secret@127.0.0.1:5432/ideer_test"

# C1 — fresh database:
psql ... -c "CREATE DATABASE ideer_fresh;"       # empty
uv run alembic -c app/agentplatform/persistence/migrations/alembic.ini upgrade head
uv run python -c "from deerflow.persistence.bootstrap import bootstrap_schema; ..."   # deerflow tree → 0018_oauth_identity_pg_partial
uv run python ../scripts/seed_bundled_resources.py  # then one canonical run

# C2 — existing-style database:
#   restore a copy of backend/.ideer/data/ideer.db into PostgreSQL via
#   pgloader or the SQLite→PG migration fixture, then repeat both upgrades.
```

**Expected evidence:** both heads reach their tips on PostgreSQL
(`20260828_run_snapshot_selection_role` / `0018_oauth_identity_pg_partial`);
schema, constraints, and JSON semantics match the SQLite fixtures;
`ResourceService` + `RunRepository` + scheduler + durable batch smoke pass.

</details>

## 3. Fault-zeroing live end-to-end (§24-H, §28 material #9)

**Status:** still `incomplete (environmental)` — network RTT to the
DeepSeek endpoint is fine (~90ms), but the `deductive_tree` node's
multi-round reasoning cannot finish inside any reasonable node budget
against this sandbox's generation latency (900s/1800s/3600s, and 10800s in
the bounded attempt of 2026-09-07 — see BASELINE_REPORT closing addendum).

**Where to run:** an environment with a low-latency model endpoint
(ideally the intranet vLLM, `http://vllm.internal.com:8000/v1`, which is
unreachable from this sandbox).

```bash
cd backend
DEER_FLOW_CONFIG_PATH=<config with reachable model> \
  uv run python ../scripts/run_fault_zeroing_acceptance.py --user-id super_admin
# user_id must match ^[A-Za-z0-9_-]{1,64}$ (paths validator rejects emails)
```

**Expected evidence:** all three checked-in cases report
`COMPLETION_STATUS_COMPLETED` with the 9 terminal action nodes and non-empty
artifacts in `{paths.base_dir}/acceptance/fault-zeroing/<session>/`.

**Record to:** `BASELINE_REPORT.md` fault-zeroing acceptance row +
`SUBAGENT/PR_MATERIALS` material #9.

## 4. Also note

- `scripts/serve.sh`, deploy and docker scripts compare upstream provider
  strings (`deerflow.*`) and keep the `.ideer` data-dir + `IDEER_*` env
  compatibility aliases by design — do not "fix" them during deployment.
- The two Alembic trees are intentionally separate (control plane vs
  `deerflow_alembic_version`); deploy `serve.sh` upgrades both in order.
