#!/bin/sh
set -eu
# Railway private DNS can resolve to IPv6. Keep local/Compose IPv4 defaults.
default_api_host=0.0.0.0
if [ -n "${RAILWAY_ENVIRONMENT_ID:-}" ]; then
    default_api_host=::
fi
exec uvicorn app.main:app --host "${API_HOST:-$default_api_host}" --port "${PORT:-8000}" --workers "${API_WORKERS:-2}" --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
