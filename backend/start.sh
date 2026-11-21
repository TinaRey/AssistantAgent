#!/bin/sh
# Container entrypoint: apply database migrations, then serve.
# Render's free plan has no pre-deploy command, so migrations run here (single instance).
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
