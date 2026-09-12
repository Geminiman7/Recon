# Railway deployment

The live frontend https://insightful-adventure-production-169c.up.railway.app/
returned 200 during review, but /api/health/live and /api/health/ready returned
404. Deploy the Nginx frontend below to route /api to the private backend.
Keep the same-origin API URL: login and CSRF cookies depend on it.

## Services

Create PostgreSQL and Redis in the same Railway project/environment. Connect
four repository services, each with Root Directory / and these Config File paths:

| Service | Config File | Public domain |
| --- | --- | --- |
| frontend (existing) | /deploy/railway/frontend.toml | Keep existing domain; target port 8080 |
| api | /deploy/railway/api.toml | None |
| worker | /deploy/railway/worker.toml | None |
| beat | /deploy/railway/beat.toml | None |

Clear conflicting dashboard build/start commands and Dockerfile overrides.
Remove worker/beat HTTP healthchecks. Keep one beat replica. Disable serverless
sleeping on API, worker and beat. These files do not provision services or variables.
Use the root Dockerfile for Python services, not the legacy backend Dockerfiles.

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
API_PORT=8000
```

Never put database, storage or application secrets on the frontend service.
Leave frontend RECON_API_URL unset; /api is the intended URL.

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

- https://docs.railway.com/config-as-code/reference
- https://docs.railway.com/networking/private-networking
- https://docs.railway.com/guides/fastapi
