#!/usr/bin/env bash
# ==============================================================================
# BNB API - Continuous Deployment script
# Triggered by GitHub Actions on push/merge to prod branch.
# ==============================================================================

set -euo pipefail

APP_DIR="/opt/bnb-api"
TARGET_COMMIT="${1:-}"
API_DIR="$APP_DIR/apps/api"
LEGACY_SERVICE_NAME="bnb-api"
NGINX_SITE="/etc/nginx/sites-available/api.gobitsnbytes.org"
ACTIVE_PORT_FILE="/var/lib/bnb-api/active-port"
MAX_HEALTH_ATTEMPTS=30
HEALTH_DELAY_SECONDS=2
OPENAPI_MAX_ATTEMPTS=2
OPENAPI_TIMEOUT_SECONDS=40
OPENAPI_RETRY_DELAY_SECONDS=2
CANDIDATE_SERVICE=""
CANDIDATE_STARTED_AT=""
NGINX_BACKUP=""
SWITCHED=0
BOOT_CONFIG_CHANGED=0
LEGACY_WAS_ENABLED=0
PREVIOUS_PORT_WAS_ENABLED=0
ACTIVE_PORT_FILE_EXISTED=0
ACTIVE_PORT_FILE_UPDATED=0

echo "=== Deployment Started: $(date) ==="

# The server checkout can contain locally edited legal knowledge. Never let
# the rollout's hard reset silently discard those changes.
DIRTY_PATHS=$(git -C "$APP_DIR" status --porcelain=v1 --untracked-files=normal) || {
    echo "!!! DEPLOYMENT STOPPED: could not inspect $APP_DIR."
    exit 1
}
if [ -n "$DIRTY_PATHS" ]; then
    echo "!!! DEPLOYMENT STOPPED: $APP_DIR has local changes. Preserve or reconcile them before deploying."
    printf '%s\n' "$DIRTY_PATHS" | head -30
    exit 1
fi

# Store current commit hash for rollback
PREV_COMMIT=$(git -C "$APP_DIR" rev-parse HEAD)
echo "Current commit: $PREV_COMMIT"

# Helper function to rollback
rollback() {
    echo "!!! DEPLOYMENT FAILED. Rolling back to commit $PREV_COMMIT !!!"
    if [ "$SWITCHED" -eq 1 ] && [ -n "$NGINX_BACKUP" ] && [ -f "$NGINX_BACKUP" ]; then
        sudo cp "$NGINX_BACKUP" "$NGINX_SITE"
        sudo nginx -t && sudo systemctl reload nginx
    fi
    if [ "$BOOT_CONFIG_CHANGED" -eq 1 ]; then
        echo "--> Restoring the previous API unit enablement..."
        if [ "$LEGACY_WAS_ENABLED" -eq 1 ]; then
            sudo systemctl enable "$LEGACY_SERVICE_NAME" || true
        else
            sudo systemctl disable "$LEGACY_SERVICE_NAME" || true
        fi
        if [ "$PREVIOUS_PORT_WAS_ENABLED" -eq 1 ]; then
            sudo systemctl enable "$PREVIOUS_PORT_SERVICE" || true
        else
            sudo systemctl disable "$PREVIOUS_PORT_SERVICE" || true
        fi
        sudo systemctl disable "$CANDIDATE_SERVICE" || true
    fi
    if [ "$ACTIVE_PORT_FILE_UPDATED" -eq 1 ]; then
        if [ "$ACTIVE_PORT_FILE_EXISTED" -eq 1 ]; then
            echo "$ACTIVE_PORT" | sudo tee "$ACTIVE_PORT_FILE" >/dev/null || true
        else
            sudo rm -f "$ACTIVE_PORT_FILE" || true
        fi
    fi
    if [ -n "$CANDIDATE_SERVICE" ]; then
        sudo systemctl stop "$CANDIDATE_SERVICE" || true
    fi
    git -C "$APP_DIR" reset --hard "$PREV_COMMIT"
    
    echo "--> Restoring dependencies..."
    sudo /home/ubuntu/.bun/bin/bun install --cwd "$APP_DIR" --frozen-lockfile
    sudo chown -R deploy:deploy "$APP_DIR"
    uv sync --project "$API_DIR" --frozen --no-dev --python python3.12
    
    echo "--> Rollback complete; the previous API process remained active."
    exit 1
}

# 1. Ensure working directory ownership & pull latest code
echo "--> Fixing directory ownership and pulling the authorized revision..."
sudo chown -R $(whoami):$(id -gn) "$APP_DIR"
sudo chmod -R u+rwX "$APP_DIR/.git"
if [ -n "$TARGET_COMMIT" ]; then
    git -C "$APP_DIR" fetch origin "$TARGET_COMMIT"
else
    git -C "$APP_DIR" fetch origin prod
    TARGET_COMMIT="origin/prod"
fi
git -C "$APP_DIR" reset --hard "$TARGET_COMMIT"

NEW_COMMIT=$(git -C "$APP_DIR" rev-parse HEAD)
echo "New commit: $NEW_COMMIT"

if [ "$PREV_COMMIT" = "$NEW_COMMIT" ]; then
    echo "--> No new code changes. Verifying dependencies and restarting..."
fi

# 1.4. Install the production DOCX renderer used by digital onboarding packets.
if ! command -v soffice >/dev/null 2>&1 && ! command -v libreoffice >/dev/null 2>&1; then
    echo "--> Installing LibreOffice Writer for onboarding document rendering..."
    sudo apt-get update
    sudo apt-get install -y libreoffice-writer
fi

# 1.5. Install monorepo JS dependencies only when manifests changed or install state is missing
if [ ! -d "$APP_DIR/node_modules" ] || ! git -C "$APP_DIR" diff --quiet "$PREV_COMMIT" "$NEW_COMMIT" -- package.json bun.lock apps/bot/package.json apps/bot/bun.lock; then
    echo "--> JavaScript dependency manifests changed; installing with Bun..."
    sudo /home/ubuntu/.bun/bin/bun install --cwd "$APP_DIR" --frozen-lockfile || rollback
    sudo chown -R deploy:deploy "$APP_DIR"
    sudo chown -R $(whoami):$(id -gn) "$APP_DIR/.git"
else
    echo "--> JavaScript dependency manifests unchanged; skipping Bun install."
fi

# 2. Sync Python dependencies only when manifests changed or the environment is missing
if [ ! -x "$API_DIR/.venv/bin/python" ] || ! git -C "$APP_DIR" diff --quiet "$PREV_COMMIT" "$NEW_COMMIT" -- apps/api/pyproject.toml apps/api/uv.lock; then
    echo "--> Python dependency manifests changed; syncing with uv..."
    uv sync --project "$API_DIR" --frozen --no-dev --python python3.12 || rollback
else
    echo "--> Python dependency manifests unchanged; skipping uv sync."
fi

# 3. Run reviewed database migrations
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

# 4. Set runtime ownership and install the dual-port service template
echo "--> Ensuring runtime directory permissions..."
sudo chown -R deploy:deploy "$APP_DIR"
sudo chown -R $(whoami):$(id -gn) "$APP_DIR/.git"
sudo chmod -R u+rwX "$APP_DIR/.git"

sudo cp "$APP_DIR/deploy/api/bnb-api@.service" /etc/systemd/system/bnb-api@.service
sudo systemctl daemon-reload
sudo mkdir -p "$(dirname "$ACTIVE_PORT_FILE")"

if [ -f "$ACTIVE_PORT_FILE" ]; then
    ACTIVE_PORT_FILE_EXISTED=1
    ACTIVE_PORT=$(cat "$ACTIVE_PORT_FILE")
else
    ACTIVE_PORT=8000
fi
if [ "$ACTIVE_PORT" != "8000" ] && [ "$ACTIVE_PORT" != "8001" ]; then
    echo "--> Invalid active API port state: $ACTIVE_PORT"
    rollback
fi
if [ "$ACTIVE_PORT" = "8000" ]; then
    CANDIDATE_PORT=8001
else
    CANDIDATE_PORT=8000
fi
CANDIDATE_SERVICE="bnb-api@${CANDIDATE_PORT}.service"
PREVIOUS_PORT_SERVICE="bnb-api@${ACTIVE_PORT}.service"
if sudo systemctl is-enabled --quiet "$LEGACY_SERVICE_NAME"; then
    LEGACY_WAS_ENABLED=1
fi
if sudo systemctl is-enabled --quiet "$PREVIOUS_PORT_SERVICE"; then
    PREVIOUS_PORT_WAS_ENABLED=1
fi
CANDIDATE_HEALTH_URL="http://127.0.0.1:${CANDIDATE_PORT}/health"
CANDIDATE_READY_URL="http://127.0.0.1:${CANDIDATE_PORT}/health/ready"
CANDIDATE_OPENAPI_URL="http://127.0.0.1:${CANDIDATE_PORT}/api/openapi.json"

echo "--> Starting replacement API on port $CANDIDATE_PORT..."
CANDIDATE_STARTED_AT=$(date --iso-8601=seconds)
sudo systemctl reset-failed "$CANDIDATE_SERVICE" || true
sudo systemctl restart "$CANDIDATE_SERVICE" || rollback

# 5. Verify the replacement before switching Nginx
echo "--> Performing replacement health checks..."
ATTEMPT=1
SUCCESS=0

while [ $ATTEMPT -le $MAX_HEALTH_ATTEMPTS ]; do
    echo "Health check attempt $ATTEMPT/$MAX_HEALTH_ATTEMPTS..."
    LIVE_CODE=$(curl --max-time 2 -s -o /dev/null -w "%{http_code}" "$CANDIDATE_HEALTH_URL" || true)
    READY_CODE=$(curl --max-time 3 -s -o /dev/null -w "%{http_code}" "$CANDIDATE_READY_URL" || true)
    
    if [ "$LIVE_CODE" = "200" ] && [ "$READY_CODE" = "200" ]; then
        echo "--> Replacement passed liveness and readiness checks."
        SUCCESS=1
        break
    else
        echo "Health checks returned live=${LIVE_CODE:-000} ready=${READY_CODE:-000}. Retrying in ${HEALTH_DELAY_SECONDS}s..."
        sleep "$HEALTH_DELAY_SECONDS"
        ATTEMPT=$((ATTEMPT + 1))
    fi
done

if [ $SUCCESS -ne 1 ]; then
    echo "--> Health check failed after $MAX_HEALTH_ATTEMPTS attempts."
    echo "--> Candidate service status:"
    sudo systemctl status "$CANDIDATE_SERVICE" --no-pager --full || true
    echo "--> Candidate logs from this rollout:"
    sudo journalctl -u "$CANDIDATE_SERVICE" --since "$CANDIDATE_STARTED_AT" --no-pager -n 100 || true
    rollback
fi

# OpenAPI generation can be the first expensive request on a cold worker. Exercise
# it on the candidate before cutover so it warms the schema cache and regressions
# fail while the old API is still serving traffic.
echo "--> Verifying candidate OpenAPI schema..."
OPENAPI_SUCCESS=0
OPENAPI_ATTEMPT=1
while [ "$OPENAPI_ATTEMPT" -le "$OPENAPI_MAX_ATTEMPTS" ]; do
    OPENAPI_CODE=$(curl --connect-timeout 2 --max-time "$OPENAPI_TIMEOUT_SECONDS" -s -o /dev/null -w "%{http_code}" "$CANDIDATE_OPENAPI_URL" || true)
    if [ "$OPENAPI_CODE" = "200" ]; then
        echo "--> Candidate OpenAPI schema returned HTTP 200."
        OPENAPI_SUCCESS=1
        break
    fi
    echo "--> OpenAPI check attempt $OPENAPI_ATTEMPT/$OPENAPI_MAX_ATTEMPTS returned ${OPENAPI_CODE:-000}."
    if [ "$OPENAPI_ATTEMPT" -lt "$OPENAPI_MAX_ATTEMPTS" ]; then
        sleep "$OPENAPI_RETRY_DELAY_SECONDS"
    fi
    OPENAPI_ATTEMPT=$((OPENAPI_ATTEMPT + 1))
done

if [ "$OPENAPI_SUCCESS" -ne 1 ]; then
    echo "--> Candidate OpenAPI check failed."
    echo "--> Candidate service status:"
    sudo systemctl status "$CANDIDATE_SERVICE" --no-pager --full || true
    echo "--> Candidate logs from this rollout:"
    sudo journalctl -u "$CANDIDATE_SERVICE" --since "$CANDIDATE_STARTED_AT" --no-pager -n 100 || true
    rollback
fi

# 6. Atomically switch Nginx, verify public traffic, then retire the old worker
NGINX_BACKUP=$(mktemp)
sudo cp "$NGINX_SITE" "$NGINX_BACKUP"
sudo sed -E -i "s#proxy_pass http://127\.0\.0\.1:(8000|8001)#proxy_pass http://127.0.0.1:${CANDIDATE_PORT}#g" "$NGINX_SITE" || rollback
sudo grep -q "proxy_pass http://127.0.0.1:${CANDIDATE_PORT}" "$NGINX_SITE" || rollback
sudo nginx -t || rollback
sudo systemctl reload nginx || rollback
SWITCHED=1

PUBLIC_CODE="000"
for attempt in 1 2 3 4 5; do
    PUBLIC_CODE=$(curl -4 --connect-timeout 2 --max-time 5 -s -o /dev/null -w "%{http_code}" https://api.gobitsnbytes.org/health || true)
    if [ "$PUBLIC_CODE" = "200" ]; then
        break
    fi
    echo "--> Public health check attempt $attempt/5 returned ${PUBLIC_CODE:-000}."
    if [ "$attempt" -lt 5 ]; then
        sleep 2
    fi
done
if [ "$PUBLIC_CODE" != "200" ]; then
    echo "--> Public health check failed with ${PUBLIC_CODE:-000}."
    rollback
fi

echo "--> Restarting bnb-bot systemd service..."
sudo systemctl restart bnb-bot || rollback

# Update boot enablement only after the cutover and public health check succeed.
# If any persistence step fails, rollback restores the previous boot target.
BOOT_CONFIG_CHANGED=1
sudo systemctl enable "$CANDIDATE_SERVICE" || rollback
sudo systemctl disable "$LEGACY_SERVICE_NAME" || rollback
sudo systemctl disable "$PREVIOUS_PORT_SERVICE" || rollback

ACTIVE_PORT_FILE_UPDATED=1
echo "$CANDIDATE_PORT" | sudo tee "$ACTIVE_PORT_FILE" >/dev/null || rollback

sudo systemctl stop "$LEGACY_SERVICE_NAME" || true
sudo systemctl stop "$PREVIOUS_PORT_SERVICE" || true

if [ -f "$NGINX_BACKUP" ]; then
    sudo rm -f "$NGINX_BACKUP"
fi

echo "=== Deployment Completed Successfully! ==="
