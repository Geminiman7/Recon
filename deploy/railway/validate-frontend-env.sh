#!/bin/sh
set -eu

fail() {
    echo "frontend env error: $*" >&2
    exit 1
}

case "${API_HOST:-}" in
    "")
        fail 'API_HOST is required. Set it on the frontend service to ${{api.RAILWAY_PRIVATE_DOMAIN}} or api.railway.internal if the API service is named api.'
        ;;
    *'$'*|*'{'*|*'}'*)
        fail "API_HOST is '${API_HOST}', which looks like an unresolved Railway reference. Use Railway reference syntax, for example API_HOST=\${{api.RAILWAY_PRIVATE_DOMAIN}}, and redeploy."
        ;;
    *://*|*/*)
        fail "API_HOST must be only a private hostname, not a URL: '${API_HOST}'. Use the port separately in API_PORT."
        ;;
esac

case "${API_PORT:-}" in
    ""|*[!0-9]*)
        fail "API_PORT must be numeric; got '${API_PORT:-<empty>}'."
        ;;
esac

case "${PORT:-}" in
    ""|*[!0-9]*)
        fail "PORT must be numeric; got '${PORT:-<empty>}'."
        ;;
esac
