# Railway deployment

## API-only reconciliation with persistent local files

For a single API service without Redis or a worker, set `RECONCILIATION_MODE=sync`
and `STORAGE_BACKEND=local`, and attach a Railway volume mounted at
`/app/app/storage`. This covers uploads and exports. Use one service replica;
separate worker services cannot access this service's volume. The existing
asynchronous export workflow still requires a worker and shared S3; this option
is for synchronous reconciliation.

Keep `REDIS_URL` empty. Set `ENVIRONMENT=production`, a strong `SECRET_KEY`,
and your HTTPS `FRONTEND_URL`. Railway supplies `RAILWAY_VOLUME_MOUNT_PATH` when
a volume is attached; the application validates that it covers the storage root.
Keep the API start command and Alembic pre-deploy migration command as documented
below. Volumes mount at runtime, so do not restore files in the pre-deploy command.

The root Dockerfile runs as a non-root user. Railway's documented volume-permission
option is `RAILWAY_RUN_UID=0`; alternatively provision write permissions for the
image's UID 1000. Check for `PermissionError` when testing an upload.

Attach storage before uploading replacement files. A new empty volume does not
restore old container files and can hide files previously written at its mount
path. Back up accessible existing files before attaching it. If originals are
gone, create a new job, upload both original datasets, save mappings, and run
again. Creating a new job avoids old missing-file records and duplicate-upload
checks. If you have a backup, restoring files at their original paths preserves
existing jobs and mappings. No file contents can be recovered from upload metadata.

`FileNotFoundError` for `/app/app/storage/uploads/...` means a saved upload record
points to a file absent from the current container. It is unrelated to Redis.
The API now returns a helpful 422 for reconciliation or 410 for column headers
instead of a generic 500. SQL echo logging is disabled on Railway to avoid
flooding deployment logs even if `ENVIRONMENT` was accidentally left as development.

Readiness currently tracks background-worker availability, so an API-only setup
can still report `/health/ready` as unavailable. Keep `/health/live` as the Railway
deployment healthcheck for this mode; verify reconciliation using a small job.

References: https://docs.railway.com/volumes and
https://docs.railway.com/services#ephemeral-storage

## Running without Redis

Redis is optional. Deploy the latest code to the API and a separate
`fallback-worker` service in the same Railway environment. Both use Root
Directory `/` and `RAILWAY_DOCKERFILE_PATH=Dockerfile`.

- API pre-deploy command: `python -m alembic upgrade head`.
- Keep the API start command `/app/scripts/start-api.sh`.
- Worker start command: `python -m app.workers.fallback_worker`.
- Leave `REDIS_URL` unset or empty on both services. Set
  `RECONCILIATION_MODE=async` on both.
- Share `DATABASE_URL`, `SECRET_KEY`, HTTPS `FRONTEND_URL`, and all S3/storage
  variables with the worker. PostgreSQL and shared S3 storage remain required.
- Start with one worker replica, `DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=0`,
  sleeping disabled and restart-on-failure enabled. Leave its HTTP healthcheck
  and public domain empty.
- Deploy the API/migration before the worker. No Celery worker or beat service
  is needed in this mode: the fallback also performs expiry cleanup.

Check `/api/health/ready` through the frontend (or `/health/ready` on the API).
Expect `status: ready`, `fallback_worker: ok`, and Redis/Celery `disabled`.
Without a fresh worker heartbeat readiness returns 503. Submit a reconciliation
and verify completion before considering the rollout complete.

The Redis/Celery deployment described below is an optional alternative.

The live frontend https://insightful-adventure-production-169c.up.railway.app/
returned 200 during review, but /api/health/live and /api/health/ready returned
404. Deploy the Nginx frontend below to route /api to the private backend.
Keep the same-origin API URL: login and CSRF cookies depend on it.

## Services

Config as Code is deprecated: new services cannot opt in, and existing files
stop being read on 2026-12-01. Configure this deployment directly in the Railway
dashboard using the settings below. Do not select the TOML files in Railway
Config File. They are retained only as legacy references.

Create PostgreSQL and Redis in the same project/environment. Connect frontend,
api, worker and beat to this repository, with Root Directory / for all four.
Keep the existing frontend domain (target port 8080); keep the other services private.

### Build settings

In each service's Variables tab, set RAILWAY_DOCKERFILE_PATH:

| Service | RAILWAY_DOCKERFILE_PATH |
| --- | --- |
| frontend | deploy/railway/Dockerfile.frontend |
| api | Dockerfile |
| worker | Dockerfile |
| beat | Dockerfile |

Leave custom Build Command empty; the Dockerfiles install dependencies.
Remove any obsolete Railway Config File selection after copying its effective
settings into the dashboard, since legacy files override dashboard settings.

### Deploy settings

Enter these in each service's Settings:

| Service | Start Command | Pre-deploy Command | Healthcheck Path | Healthcheck Timeout |
| --- | --- | --- | --- | --- |
| frontend | Leave empty (use image default) | Empty | /nginx-health | 60 seconds |
| api | /app/scripts/start-api.sh | python -m alembic upgrade head | /health/live | 120 seconds |
| worker | celery -A app.core.celery_app worker --loglevel=INFO --concurrency=2 --max-tasks-per-child=100 | Empty | Empty | Not applicable |
| beat | celery -A app.core.celery_app beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule | Empty | Empty | Not applicable |

Set Restart Policy to On Failure with 10 retries on all four services.
Keep exactly one beat replica. Disable serverless sleeping for API, worker and
beat. Use the root Dockerfile for Python services, not the legacy backend Dockerfiles.

### Optional Infrastructure as Code

Railway's replacement is project-level .railway/railway.ts evaluated by its CLI.
For this existing project, import actual services rather than recreating them:
install/update the Railway CLI, then run railway login, railway link,
railway config pull, and railway config plan. Confirm the correct project and
environment when linking. Review the plan before railway config apply.
Do not use --include-variables when pulling: the default preserves remote
secrets instead of writing their values into source. Existing legacy config
management must be migrated before IaC can manage those services.
The dashboard setup above does not require IaC.

## Variables

Set the following on api, worker and beat. Replace Postgres/Redis reference names
with your actual Railway service names. Enter references in Railway Variables.

```dotenv
ENVIRONMENT=production
FRONTEND_URL=https://insightful-adventure-production-169c.up.railway.app
CORS_ORIGINS=https://insightful-adventure-production-169c.up.railway.app
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
SECRET_KEY=<one random secret shared across all three services, at least 32 characters>
RECONCILIATION_MODE=async
STORAGE_BACKEND=s3
S3_BUCKET=<private bucket name>
S3_REGION=<bucket region>
S3_PREFIX=recon
AWS_ACCESS_KEY_ID=<storage access key>
AWS_SECRET_ACCESS_KEY=<storage secret key>
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=0
DB_POOL_TIMEOUT=10
```

Use AWS S3 supporting AES256 server-side encryption, or a compatible provider
verified with this application's upload/download flow. For another provider set
S3_ENDPOINT_URL. All three services need the same bucket/prefix with read, write
and delete permissions. Separate service disks or volumes cannot provide the
shared filesystem needed by API and workers. Existing local uploads must be
copied and their database references migrated before switching a populated
installation to S3; these changes do not move data.

Additional api variables:

```dotenv
PORT=8000
API_HOST=::
API_WORKERS=2
FORWARDED_ALLOW_IPS=*
```

Trusting forwarded headers assumes no public domain or TCP proxy on the API and
only trusted services in its private network. The frontend proxy sets HTTPS and
preserves /api on backend redirects. Binding :: supports private IPv6 networking.

Additional frontend variables (replace api if named differently):

```dotenv
PORT=8080
API_HOST=${{api.RAILWAY_PRIVATE_DOMAIN}}
API_PORT=${{api.PORT}}
```

Use Railway reference syntax exactly: `${{service.VARIABLE}}`, where `service`
is the API service name as shown in Railway. `${api_host}` or
`${{api_host}}` will be passed through as literal text and Nginx will try to
resolve it as a hostname. `API_HOST` must evaluate to a hostname only, such as
`api.railway.internal`; keep `http://` and `:8000` out of this variable.

Never put database, storage or application secrets on the frontend service.
Leave frontend RECON_API_URL unset; /api is the intended URL.

If Nginx reports `connect() failed (111: Connection refused)` to an IPv6
upstream, check that the API deployment is running and listening on `::` at
the same port as frontend `API_PORT`. The startup script defaults to `::` on
Railway; remove any API `API_HOST=0.0.0.0` override or change it to `::`.
The frontend's own `PORT=8080` is independent of the API port. With the API
`PORT=8000` above, the upstream must use port 8000. Redeploy the API and then
the frontend after updating variables. If it still refuses connections,
inspect API startup logs for crashes before testing CSRF again.

Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
and SMTP_USE_TLS on the API for password-reset email. Configure PAYSTACK_SECRET_KEY,
PAYSTACK_PRO_PLAN_CODE and PAYSTACK_PRO_ANNUAL_PLAN_CODE for paid billing.
The Paystack webhook URL is:
https://insightful-adventure-production-169c.up.railway.app/api/billing/webhooks/paystack

## Deploy and verify

1. Provision PostgreSQL, Redis and the bucket, then set variables.
2. Deploy API first. Its pre-deploy command runs python -m alembic upgrade head;
   failure prevents rollout. Back up existing databases before schema changes.
3. Deploy worker and beat after migration succeeds, then frontend. Worker
   concurrency starts at two; check memory and database connection budgets
   before increasing it. Beat schedules expired-export cleanup.
4. Check these paths on the frontend domain:
   - /nginx-health: 200.
   - /api/health/live: 200.
   - /api/health/ready: 200, database, Redis and Celery all ok.
   - /api/auth/csrf: 200 with a Secure __Host-recon_csrf cookie.
5. Register/login with a test account, upload both files, reconcile, generate
   and download an export, then check logout and password reset. Browser API
   requests must stay on the frontend domain; session cookies must be HttpOnly.
6. Redeploy API/worker and confirm stored uploads and exports remain accessible.

Rollout checks liveness to avoid worker deployment ordering deadlocks. Monitor
/api/health/ready externally. A green deployment does not by itself verify
object storage, email, billing or complete reconciliation behavior.

## Local verification

All 20 existing unittest tests passed using the local Python environment after
temporarily supplying the missing defusedxml dependency. Python compilation,
TOML parsing and targeted database URL/storage configuration checks passed.
Docker is not installed locally, so container builds and Nginx runtime behavior
remain to be checked in Railway. Local package versions differ from the pinned
container environment. No Railway services or credentials were changed.

## References

- https://docs.railway.com/infrastructure-as-code
- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/networking/private-networking
- https://docs.railway.com/guides/fastapi
