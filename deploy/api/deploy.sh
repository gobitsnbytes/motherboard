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

# 1. Pull latest code
echo "--> Pulling latest code from prod..."
git -C "$APP_DIR" fetch origin prod
git -C "$APP_DIR" reset --hard origin/prod

NEW_COMMIT=$(git -C "$APP_DIR" rev-parse HEAD)
echo "New commit: $NEW_COMMIT"

if [ "$PREV_COMMIT" = "$NEW_COMMIT" ]; then
    echo "--> No new code changes. Verifying dependencies and restarting..."
fi

# 2. Sync python dependencies
echo "--> Syncing python dependencies..."
uv sync --project "$API_DIR" --frozen --no-dev --python python3.12 || rollback

# 3. Run database migrations
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

# 4. Restart service
echo "--> Restarting bnb-api systemd service..."
sudo systemctl restart "$SERVICE_NAME" || rollback

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
