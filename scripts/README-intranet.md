# iDeer Intranet Deployment Guide

This guide covers deploying iDeer on an air-gapped (intranet/offline) environment.

## Prerequisites

### On an Internet-Connected Machine (Build Host)

1. Docker and Docker Compose v2 installed
2. This repository cloned
3. Run the packaging script to create an offline bundle:

```bash
scripts/package-intranet-offline.sh --version <version-tag>
```

This produces a self-contained bundle in `dist/intranet/ideer-<version>/` containing:
- Docker images (gateway, frontend, nginx)
- Source code archive
- Deploy and pre-check scripts
- Config templates

### On the Intranet Target Machine

1. Docker and Docker Compose v2 installed
2. At least 10 GB free disk space
3. Ports 80, 3000, 8080 available (or configure a different port)

## Step-by-Step Deployment

### 1. Transfer the Bundle

Copy the entire bundle directory to the target machine:

```bash
scp -r dist/intranet/ideer-<version>/ user@target:/opt/ideer/
```

Or use a USB drive, internal file share, or any approved transfer method.

### 2. Configure the Deployment

Edit the configuration files in the bundle:

```bash
cd /opt/ideer/ideer-<version>/

# Configure LLM endpoint and other settings
vi config.intranet.yaml

# Configure Docker build mirrors (if using internal registry)
vi .env.intranet
```

#### LLM Endpoint Configuration

In `config.intranet.yaml`, set your internal LLM endpoint:

```yaml
models:
  - provider: openai
    name: your-model-name
    base_url: http://your-llm-server:8000/v1
    api_key: your-api-key
```

If using a self-hosted vLLM, Ollama, or similar service, point `base_url` to its OpenAI-compatible endpoint.

### 3. Run Pre-check

Verify the environment is ready:

```bash
./check-intranet.sh
```

This checks Docker, images, config files, ports, and disk space. Fix any errors before proceeding.

To also verify LLM connectivity:

```bash
IDEER_LLM_ENDPOINT=http://your-llm-server:8000 ./check-intranet.sh
```

### 4. Deploy

```bash
./deploy-intranet.sh up
```

This will:
1. Extract source code
2. Seed runtime configuration
3. Load Docker images
4. Start all services
5. Run health checks

To preview what would happen without making changes:

```bash
./deploy-intranet.sh --dry-run up
```

To skip the pre-check (not recommended):

```bash
./deploy-intranet.sh --skip-check up
```

### 5. Verify

After deployment, access iDeer at `http://localhost:2026` (or the port configured in `env.intranet`).

Check service status:

```bash
./deploy-intranet.sh status
```

View logs:

```bash
./deploy-intranet.sh logs
./deploy-intranet.sh logs gateway
./deploy-intranet.sh logs frontend
```

## Managing Services

| Command | Description |
|---------|-------------|
| `./deploy-intranet.sh up` | Start services |
| `./deploy-intranet.sh stop` | Stop services |
| `./deploy-intranet.sh restart` | Restart services |
| `./deploy-intranet.sh status` | Show running containers |
| `./deploy-intranet.sh logs` | Follow all logs |
| `./deploy-intranet.sh logs gateway` | Follow gateway logs |
| `./deploy-intranet.sh prepare` | Extract and seed config only |

## Troubleshooting

### Services fail to start

1. Check logs: `./deploy-intranet.sh logs gateway`
2. Verify config: ensure `config.intranet.yaml` has valid `models` entries
3. Check Docker: `docker ps -a` to see container status and exit codes

### Health check timeout

If the deploy script hangs at health checks:
- The gateway may be crashing -- check `./deploy-intranet.sh logs gateway`
- The LLM endpoint may be unreachable from inside the container
- Try: `docker compose -p ideer down` then `./deploy-intranet.sh up`

### Port conflict

If port 2026 is in use, edit `env.intranet` and change the `PORT` value, then restart:
```bash
./deploy-intranet.sh restart
```

### LLM connection refused

- Verify the LLM server is running and accessible from the Docker network
- Check that `base_url` in `config.intranet.yaml` uses the correct host/port
- For host-network services, use `host.docker.internal` or the host IP

### Container image not found

If Docker reports missing images:
```bash
./deploy-intranet.sh load
```

### Full reset

To completely start over:
```bash
./deploy-intranet.sh stop
rm -rf runtime/ source/ env.intranet
./deploy-intranet.sh up
```

### Stuck containers

If containers are stuck and won't stop:
```bash
docker compose -p ideer down --remove-orphans
docker system prune -f
./deploy-intranet.sh up
```

## Architecture

The intranet deployment runs three containers:

- **nginx** -- Reverse proxy on the configured port (default 2026)
- **frontend** -- Next.js application on port 3000 (internal)
- **gateway** -- Python backend API on port 8001 (internal)

All containers communicate over an internal Docker bridge network (`ideer`).
