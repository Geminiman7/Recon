# Production deployment guide

For Railway, follow [RAILWAY.md](RAILWAY.md). The Compose instructions below
apply to a single Docker host.

The root `docker-compose.yml` is the canonical deployment definition. Do not
combine it with `backend/docker-compose.yml` or
`backend/docker-compose.override.yml`; those files are retained only as legacy
references and contain conflicting service names and development overrides.

## Request and failure flow

```text
client -> Nginx :80 -> /api/* -> FastAPI -> PostgreSQL / Redis / Celery
                    502/504       readiness failure
                       \             /
                        -> HTTP 503 + Retry-After: 30
```

`/health/live` checks whether the API process can answer. `/health/ready`
checks PostgreSQL, Redis, and at least one Celery worker. Readiness returns 503
when any critical dependency is unavailable. Nginx also intercepts upstream
500, 502, 503, and 504 responses and returns a stable JSON 503 response.

## Host preparation

1. Install a supported Docker Engine and Docker Compose plugin.
2. Put TLS in front of port 80 using a managed load balancer, CDN, ingress, or a
   host reverse proxy. Redirect HTTP to HTTPS at that edge and enable HSTS only
   after HTTPS is confirmed on every hostname.
3. Copy `.env.production.example` to `.env` and replace every placeholder.
   Keep `.env` out of source control and readable only by the deployment user.
4. Back up the PostgreSQL and upload volumes. Redis is a delivery mechanism and
   must not be treated as the system of record.

Generate suitable secrets, for example:

```sh
openssl rand -hex 32
openssl rand -base64 48
```

## Validate and deploy

Run validation before changing the live stack:

```sh
docker compose --env-file .env config --quiet
docker compose --env-file .env build
docker compose --env-file .env run --rm migrate
docker compose --env-file .env up -d --remove-orphans
docker compose --env-file .env ps
```

The normal `up` command also runs the one-shot migration service. A migration
failure is fatal: API and workers will not start against an unknown schema.
Never use `down -v` in production because it deletes persistent data.

Verify externally:

```sh
curl -i http://localhost/health/live
curl -i http://localhost/health/ready
curl -i http://localhost/api/
```

Healthy readiness returns 200. Stop the API temporarily in a staging system and
repeat an API request; Nginx must return 503, JSON content, `Cache-Control:
no-store`, and `Retry-After: 30` rather than exposing a gateway error.

## Availability and scaling

Two Uvicorn processes protect against a single process crash. For host-level
high availability, run the image on at least two hosts or orchestration nodes
behind a health-checking load balancer; a single Compose host cannot survive a
host outage. Use managed or replicated PostgreSQL and Redis with tested
failover. Shared uploads must move from the local named volume to S3-compatible
object storage before API/worker replicas span hosts.

Within one host, additional API or worker replicas can be tested with:

```sh
docker compose --env-file .env up -d --scale api=2 --scale worker=2
docker compose --env-file .env restart frontend
```

Nginx resolves Compose service endpoints when it starts. Restarting Nginx after
changing replica count refreshes that endpoint set. For continuous dynamic
discovery and zero-downtime host failover, use Kubernetes/ECS/Nomad service
discovery or place a managed load balancer in front of separately deployed API
replicas.

## Nginx stability controls

The production configuration provides bounded connection/read/send timeouts,
upstream keep-alive connections, passive failure detection, limited retry to
another upstream, request-size limits, compression, non-immutable caching for
the current unhashed assets, and security headers. API traffic is same-origin at
`/api`, so port 8000 is not published and browsers do not depend on CORS.

Only retry operations that are safe for the application. Nginx does not retry
non-idempotent requests by default because `proxy_next_upstream_non_idempotent`
is deliberately absent.

## Monitoring and incident response

Alert on:

- `/health/ready` returning 503 for more than two probe intervals;
- Nginx 5xx rate and upstream response time;
- Celery queue depth, oldest task age, retries, and worker heartbeat age;
- PostgreSQL connections, slow queries, storage, and replication lag;
- Redis memory, rejected writes, persistence errors, and queue length;
- container restarts, host disk space, and upload-volume usage.

During a dependency outage, leave liveness independent of dependencies so the
orchestrator does not restart healthy API processes unnecessarily. Readiness
removes unavailable instances from traffic and supplies callers with 503 plus a
retry hint. Clients should use exponential backoff with jitter and must not
automatically replay non-idempotent requests unless they carry an idempotency
key.

## Release and rollback

Use immutable image tags or digests rather than `latest`. Back up the database,
review every Alembic revision, and test upgrades against a copy of production
data. Application rollback is safe only when the previous version supports the
new schema; prefer backward-compatible expand/migrate/contract database
changes. Keep at least one known-good image and the corresponding configuration
available for rollback.
