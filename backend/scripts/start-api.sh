#!/bin/sh
set -eu
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers "${API_WORKERS:-2}" --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
