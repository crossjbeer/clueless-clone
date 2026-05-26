#!/usr/bin/env bash
# deploy/setup.sh — Bootstrap an Amazon Linux 2023 / Ubuntu 22.04 EC2 instance.
#
# Usage (as ec2-user or ubuntu after SSH):
#   chmod +x setup.sh && sudo ./setup.sh
#
# What this script does:
#   1. Installs system dependencies (Python 3.11, nginx, git)
#   2. Installs uv (fast Python package manager)
#   3. Clones the repo and installs Python dependencies
#   4. Writes /etc/clueless.env from prompted values
#   5. Installs a systemd service (clueless.service) for uvicorn
#   6. Installs and enables an nginx reverse-proxy config
#
# Re-running the script is safe — existing files are not overwritten.

set -euo pipefail

APP_USER="clueless"
APP_DIR="/opt/clueless"
REPO_URL="${REPO_URL:-}"          # Set via env or prompted below
BUCKET="${S3_BUCKET:-}"
AWS_REGION="${AWS_DEFAULT_REGION:-us-east-2}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-}"

# ── 0. Must run as root ──────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: please run as root (sudo ./setup.sh)" >&2
  exit 1
fi

# ── 1. Detect distro and install system packages ─────────────────────────────
if command -v dnf &>/dev/null; then
  PKG="dnf"
elif command -v apt-get &>/dev/null; then
  PKG="apt-get"
else
  echo "ERROR: unsupported package manager (expected dnf or apt-get)" >&2
  exit 1
fi

echo "==> Updating package index..."
if [[ "$PKG" == "dnf" ]]; then
  dnf update -y -q
  dnf install -y -q python3.11 python3.11-pip git nginx curl
else
  apt-get update -qq
  apt-get install -y -q python3.11 python3.11-pip git nginx curl
fi

# ── 2. Install uv ────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  echo "==> Installing uv..."
  curl -fsSL https://astral.sh/uv/install.sh | sh
  # Add uv to PATH for the remainder of this session
  export PATH="$HOME/.local/bin:$PATH"
fi

# ── 3. Create app user if it doesn't exist ───────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
  echo "==> Creating system user '$APP_USER'..."
  useradd --system --shell /sbin/nologin --create-home --home-dir "$APP_DIR" "$APP_USER"
fi

# ── 4. Clone / update the repo ───────────────────────────────────────────────
if [[ -z "$REPO_URL" ]]; then
  read -rp "Enter the git repo URL (e.g. https://github.com/you/clueless-clone): " REPO_URL
fi

if [[ -d "$APP_DIR/.git" ]]; then
  echo "==> Repo already cloned — pulling latest..."
  git -C "$APP_DIR" pull --ff-only
else
  echo "==> Cloning repo to $APP_DIR..."
  git clone "$REPO_URL" "$APP_DIR"
fi

# ── 5. Install Python dependencies ───────────────────────────────────────────
echo "==> Installing Python dependencies (this downloads the model on first run)..."
cd "$APP_DIR"
HOME="$APP_DIR" uv sync --no-dev

# ── 6. Write /etc/clueless.env ───────────────────────────────────────────────
ENV_FILE="/etc/clueless.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "==> Writing $ENV_FILE..."

  if [[ -z "$BUCKET" ]]; then
    read -rp "Enter S3 bucket name: " BUCKET
  fi

  if [[ -z "$ALLOWED_ORIGINS" ]]; then
    read -rp "Enter allowed CORS origins (comma-separated, e.g. https://example.com): " ALLOWED_ORIGINS
  fi

  cat > "$ENV_FILE" <<EOF
USE_S3=true
S3_BUCKET=${BUCKET}
AWS_DEFAULT_REGION=${AWS_REGION}
ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
EOF
  chmod 600 "$ENV_FILE"
  echo "    Written. Edit $ENV_FILE to change values later."
else
  echo "==> $ENV_FILE already exists — skipping (edit manually if needed)."
fi

# ── 7. Install systemd service ───────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/clueless.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
  echo "==> Installing systemd service..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Clueless Clone — FastAPI/uvicorn
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=/etc/clueless.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable clueless
  systemctl start clueless
  echo "==> clueless.service started."
else
  echo "==> systemd service already installed — restarting to pick up any changes..."
  systemctl restart clueless
fi

# ── 8. Install nginx reverse-proxy config ────────────────────────────────────
NGINX_CONF="/etc/nginx/conf.d/clueless.conf"
if [[ ! -f "$NGINX_CONF" ]]; then
  echo "==> Writing nginx config..."
  cat > "$NGINX_CONF" <<'EOF'
server {
    listen 80;
    server_name _;          # Matches any hostname / bare IP

    # Serve the static frontend directly from nginx
    location = / {
        root /opt/clueless;
        try_files /index.html =404;
    }

    # Proxy API calls to uvicorn
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
EOF

  # Disable the default nginx site if it exists
  DEFAULT_CONF="/etc/nginx/conf.d/default.conf"
  [[ -f "$DEFAULT_CONF" ]] && mv "$DEFAULT_CONF" "${DEFAULT_CONF}.disabled"

  nginx -t
  systemctl enable nginx
  systemctl restart nginx
  echo "==> nginx configured and restarted."
else
  echo "==> nginx config already exists — reloading nginx..."
  nginx -t && systemctl reload nginx
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " Deployment complete!"
echo " API:      http://<your-ec2-ip>/"
echo " API docs: http://<your-ec2-ip>/docs"
echo ""
echo " Useful commands:"
echo "   sudo systemctl status clueless"
echo "   sudo journalctl -u clueless -f"
echo "   sudo systemctl restart clueless"
echo "======================================================"
