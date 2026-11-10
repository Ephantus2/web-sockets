
#!/usr/bin/env bash

set -Eeuo pipefail

echo "Starting Celery worker..."

celery -A config worker --loglevel=info --pool=solo &
CELERY_PID=$!

echo "Starting Daphne ASGI server..."

daphne -b 0.0.0.0 -p "${PORT:-10000}" config.asgi:application &
DAPHNE_PID=$!

cleanup() {
    echo "Stopping application processes..."

    kill -TERM "$CELERY_PID" "$DAPHNE_PID" 2>/dev/null || true

    wait "$CELERY_PID" 2>/dev/null || true
    wait "$DAPHNE_PID" 2>/dev/null || true
}

trap cleanup TERM INT

set +e
wait -n "$CELERY_PID" "$DAPHNE_PID"
EXIT_CODE=$?
set -e

cleanup

exit "$EXIT_CODE"
