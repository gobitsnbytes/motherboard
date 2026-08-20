#!/usr/bin/env bash
# ==============================================================================
# BNB API - Continuous Deployment script
# Triggered by GitHub Actions on push/merge to prod branch.
# ==============================================================================

set -euo pipefail

APP_DIR="/opt/bnb-api"
API_DIR="$APP_DIR/apps/api"
SERVICE_NAME="bnb-api"
HEALTH_CHECK_URL="http://127.0.0.1:8000/health"
MAX_HEALTH_ATTEMPTS=15
HEALTH_DELAY_SECONDS=5

echo "=== Deployment Started: $(date) ==="

# Store current commit hash for rollback
PREV_COMMIT=$(git -C "$APP_DIR" rev-parse HEAD)
echo "Current commit: $PREV_COMMIT"

# Helper function to rollback
rollback() {
    echo "!!! DEPLOYMENT FAILED. Rolling back to commit $PREV_COMMIT !!!"
    git -C "$APP_DIR" reset --hard "$PREV_COMMIT"
    
    echo "--> Restoring dependencies..."
    uv sync --project "$API_DIR" --frozen --no-dev --python python3.12
    
    echo "--> Restarting service..."
    sudo systemctl restart "$SERVICE_NAME"
    
    echo "--> Rollback complete."
    exit 1
}

# 1. Ensure working directory ownership & pull latest code
echo "--> Fixing directory ownership and pulling latest code from prod..."
sudo chown -R $(whoami):$(id -gn) "$APP_DIR"
git -C "$APP_DIR" fetch origin prod
git -C "$APP_DIR" reset --hard origin/prod

NEW_COMMIT=$(git -C "$APP_DIR" rev-parse HEAD)
echo "New commit: $NEW_COMMIT"

if [ "$PREV_COMMIT" = "$NEW_COMMIT" ]; then
    echo "--> No new code changes. Verifying dependencies and restarting..."
fi

# 1.5. Install monorepo JS dependencies
echo "--> Installing monorepo Node/Bun dependencies..."
sudo /home/ubuntu/.bun/bin/bun install --cwd "$APP_DIR" || rollback
sudo chown -R deploy:deploy "$APP_DIR"

# 2. Sync python dependencies
echo "--> Syncing python dependencies..."
uv sync --project "$API_DIR" --frozen --no-dev --python python3.12 || rollback

# 3. Run database migrations & auto-sync missing tables
echo "--> Running database migrations..."
if [ -f "$APP_DIR/.env" ]; then
    echo "--> Loading environment variables from .env..."
    # Read line by line, split on first '=', strip outer quotes, and export safely
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ ! "$line" =~ ^# ]] && [[ ! "$line" =~ ^[[:space:]]*$ ]]; then
            key=$(echo "$line" | cut -d'=' -f1)
            val=$(echo "$line" | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
            export "$key=$val" 2>/dev/null || true
        fi
    done < "$APP_DIR/.env"
fi
# Set path to include virtualenv bin
export PATH="$API_DIR/.venv/bin:$PATH"
(cd "$API_DIR" && alembic upgrade head) || rollback

echo "--> Auto-syncing missing database table schemas..."
(cd "$API_DIR" && PYTHONPATH=. "$API_DIR/.venv/bin/python" -c "
import asyncio
from app.db.session import engine
from app.db.models import Base

async def sync_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('--> Database schema metadata synced successfully.')

asyncio.run(sync_db())
") || rollback

# 3.5 Pre-flight SMTP Credential Check
echo "--> Verifying SMTP mail server credentials..."
(cd "$API_DIR" && PYTHONPATH=. "$API_DIR/.venv/bin/python" -c "
import os, smtplib
host = os.getenv('SMTP_HOST', 'mail.gobitsnbytes.org')
port = int(os.getenv('SMTP_PORT', '587'))
user = os.getenv('SMTP_USER')
password = os.getenv('SMTP_PASS')

if user and password:
    try:
        s = smtplib.SMTP(host, port, timeout=10)
        s.starttls()
        s.login(user, password)
        s.quit()
        print(f'--> SMTP Pre-flight PASSED for {user}@{host}:{port}')
    except Exception as e:
        print(f'⚠️ WARNING: SMTP Pre-flight failed for {user}@{host}:{port} - Error: {e}')
else:
    print('--> SMTP credentials not specified in .env, skipping live auth test.')
") || true

# 4. Restart services
echo "--> Restarting bnb-api systemd service..."
sudo systemctl restart "$SERVICE_NAME" || rollback
echo "--> Restarting bnb-bot systemd service..."
sudo systemctl restart bnb-bot || rollback

# 5. Health check loop
echo "--> Performing health checks..."
ATTEMPT=1
SUCCESS=0

while [ $ATTEMPT -le $MAX_HEALTH_ATTEMPTS ]; do
    echo "Health check attempt $ATTEMPT/$MAX_HEALTH_ATTEMPTS..."
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_CHECK_URL" || echo "000")
    
    if [ "$STATUS_CODE" = "200" ]; then
        echo "--> Health check passed! Application is running."
        SUCCESS=1
        break
    else
        echo "Health check returned status $STATUS_CODE. Retrying in ${HEALTH_DELAY_SECONDS}s..."
        sleep "$HEALTH_DELAY_SECONDS"
        ATTEMPT=$((ATTEMPT + 1))
    fi
done

if [ $SUCCESS -ne 1 ]; then
    echo "--> Health check failed after $MAX_HEALTH_ATTEMPTS attempts."
    # Dump journalctl logs for context before rollback
    echo "--> Last 30 lines of service logs:"
    journalctl -u "$SERVICE_NAME" -n 30
    rollback
fi

# 6. Reload Nginx (in case configuration changed)
echo "--> Reloading Nginx configuration..."
sudo systemctl reload nginx

echo "=== Deployment Completed Successfully! ==="
