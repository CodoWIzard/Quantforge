# Docker

Per-service images plus a local compose stack.

Experiment 005's exit gate is **"same result local and in container"** — the backtester
image is the first one that matters, and reproducibility is the whole point of it.

## Planned

    docker/
      backtester.Dockerfile     # finite job: read manifest, write result JSON
      collector.Dockerfile      # long-running WebSocket collector
      api.Dockerfile            # FastAPI backend
      docker-compose.dev.yml    # local postgres + optional local redis + services

Local open-source Redis is free and allowed for development (§28). Azure **Managed**
Redis is what ADR-006 excludes — do not confuse the two.
