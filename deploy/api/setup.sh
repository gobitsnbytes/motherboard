#!/usr/bin/env bash
# ==============================================================================
# BNB API - One-time VPS Setup Script (Ubuntu 22.04 Minimal)
# Run this script once on the VPS as root:
# curl -sSL https://raw.githubusercontent.com/gobitsnbytes/motherboard/prod/deploy/api/setup.sh | sudo bash
# ==============================================================================

set -euo pipefail

echo "=== Starting BNB API VPS Setup ==="

# 1. System Updates & Prerequisites
echo "--> Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y git curl ufw fail2ban software-properties-common build-essential libpq-dev

# 2. Install Python 3.12
echo "--> Installing Python 3.12..."
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update -y
apt-get install -y python3.12 python3.12-venv python3.12-dev

# 3. Install UV (Fast Python package manager)
echo "--> Installing uv package manager globally..."
curl -LsSf https://astral.sh/uv/install.sh -o install_uv.sh
INSTALL_DIR="/usr/local/bin" sh install_uv.sh
rm install_uv.sh

# 4. Create Swap File (512MB)
# Crucial for a 300MB VPS to prevent Out-Of-Memory crashes during deploys
if [ ! -f /swapfile ]; then
    echo "--> Creating 512MB swap file..."
    fallocate -l 512M /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "vm.swappiness=10" >> /etc/sysctl.conf
    sysctl -p
else
    echo "--> Swap file already exists."
fi

# 5. Create Deploy User
if ! id -u deploy >/dev/null 2>&1; then
    echo "--> Creating 'deploy' user..."
    useradd -m -s /bin/bash deploy
    usermod -aG sudo deploy
    # Enable passwordless sudo for deploy user for managing the bnb-api service
    echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bnb-api, /usr/bin/systemctl reload caddy, /usr/bin/systemctl status bnb-api" >> /etc/sudoers.d/deploy
    # Copy SSH authorized keys from ubuntu or root to deploy user
    mkdir -p /home/deploy/.ssh
    if [ -f /home/ubuntu/.ssh/authorized_keys ]; then
        cp /home/ubuntu/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    elif [ -f /root/.ssh/authorized_keys ]; then
        # Filter out warning prefixes if root key is restricted
        if grep -q "Please login as the user" /root/.ssh/authorized_keys; then
            grep -o "ssh-rsa .*" /root/.ssh/authorized_keys > /home/deploy/.ssh/authorized_keys || true
        else
            cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
        fi
    fi
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    if [ -f /home/deploy/.ssh/authorized_keys ]; then
        chmod 600 /home/deploy/.ssh/authorized_keys
    fi
else
    echo "--> 'deploy' user already exists."
fi

# 6. Clone Repository
echo "--> Setting up application directory..."
mkdir -p /opt/bnb-api
chown -R deploy:deploy /opt/bnb-api

if [ ! -d /opt/bnb-api/.git ]; then
    echo "--> Cloning motherboard repository..."
    sudo -u deploy git clone -b prod https://github.com/gobitsnbytes/motherboard.git /opt/bnb-api
else
    echo "--> Repository already cloned. Fetching latest prod branch..."
    sudo -u deploy git -C /opt/bnb-api fetch origin prod
    sudo -u deploy git -C /opt/bnb-api reset --hard origin/prod
fi

# 7. Setup Production Environment variables (.env)
if [ ! -f /opt/bnb-api/.env ]; then
    echo "--> Generating production .env file from template..."
    sudo -u deploy cp /opt/bnb-api/deploy/api/.env.production.example /opt/bnb-api/.env
    
    # Generate secrets
    SESSION_SEC=$(openssl rand -hex 32)
    API_INTERNAL_SEC=$(openssl rand -hex 32)
    NEXTAUTH_SEC=$(openssl rand -hex 32)
    
    # Replace secrets in .env
    sudo -u deploy sed -i "s/SESSION_SECRET=\"\"/SESSION_SECRET=\"$SESSION_SEC\"/" /opt/bnb-api/.env
    sudo -u deploy sed -i "s/API_INTERNAL_SECRET=\"\"/API_INTERNAL_SECRET=\"$API_INTERNAL_SEC\"/" /opt/bnb-api/.env
    sudo -u deploy sed -i "s/NEXTAUTH_SECRET=\"\"/NEXTAUTH_SECRET=\"$NEXTAUTH_SEC\"/" /opt/bnb-api/.env
    
    echo "--> .env template created. PLEASE UPDATE /opt/bnb-api/.env WITH YOUR REAL CREDENTIALS (Redis URL)!"
else
    echo "--> .env file already exists."
fi

# 8. Sync Python Dependencies
echo "--> Syncing Python dependencies using uv..."
sudo -u deploy uv sync --project /opt/bnb-api/apps/api --frozen --no-dev --python python3.12

# 9. Configure Caddy (Reverse Proxy + Auto-TLS)
echo "--> Installing Caddy server..."
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

echo "--> Configuring Caddyfile..."
cp /opt/bnb-api/deploy/api/Caddyfile /etc/caddy/Caddyfile
systemctl restart caddy

# 10. Configure Systemd Service
echo "--> Setting up systemd service..."
cp /opt/bnb-api/deploy/api/bnb-api.service /etc/systemd/system/bnb-api.service
systemctl daemon-reload
systemctl enable bnb-api
# Don't start it yet since env vars (like Redis url) need updating.
echo "--> systemd service registered."

# 11. Configure Firewall (UFW)
echo "--> Configuring firewall rules..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ufw status verbose

echo "=== VPS Setup Completed Successfully ==="
echo "Next steps:"
echo "1. Edit /opt/bnb-api/.env with your Upstash Redis URL"
echo "2. Start the service: sudo systemctl start bnb-api"
echo "3. Ensure your DNS points api.gobitsnbytes.org to this IP ($(/usr/bin/curl -s https://ipinfo.io/ip))"
