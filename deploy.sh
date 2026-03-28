#!/usr/bin/env bash
# deploy.sh — Deploy OpenHAB config and Python scripts to the OpenHAB server via SSH/rsync
#
# Usage:
#   ./deploy.sh              # deploy all (items, rules, things, scripts)
#   ./deploy.sh items        # deploy only items/
#   ./deploy.sh rules        # deploy only rules/
#   ./deploy.sh things       # deploy only things/
#   ./deploy.sh scripts      # deploy Python scripts to /opt/openhab-scripts/
#   ./deploy.sh things/KNX_tunnel.things   # deploy a single file
#
# OpenHAB config files → $OPENHAB_CONFIG_PATH (default: /etc/openhab)
# Python scripts       → $OPENHAB_SCRIPTS_PATH (default: /opt/openhab-scripts)
#
# Prerequisites:
#   1. Copy .env.example to .env and fill in your values
#   2. SSH key-based auth recommended: ssh-copy-id $OPENHAB_SSH_USER@$OPENHAB_HOST
#   3. rsync must be installed locally
#   4. First-time scripts deploy: run setup.sh on the server to create venvs

set -euo pipefail

# ── Load .env ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your values."
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

# ── Validate required vars ────────────────────────────────────────────────────
: "${OPENHAB_HOST:?OPENHAB_HOST not set in .env}"
: "${OPENHAB_SSH_USER:?OPENHAB_SSH_USER not set in .env}"
: "${OPENHAB_CONFIG_PATH:?OPENHAB_CONFIG_PATH not set in .env}"

# ── SSH options ───────────────────────────────────────────────────────────────
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
if [[ -n "${OPENHAB_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "$OPENHAB_SSH_KEY")
fi
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

REMOTE="${OPENHAB_SSH_USER}@${OPENHAB_HOST}"
REMOTE_CONFIG="${OPENHAB_CONFIG_PATH%/}"                      # e.g. /etc/openhab
REMOTE_SCRIPTS="${OPENHAB_SCRIPTS_PATH:-/opt/openhab-scripts}" # e.g. /opt/openhab-scripts

# ── Determine what to deploy ──────────────────────────────────────────────────
TARGET="${1:-all}"

deploy_config_dir() {
  local dir="$1"
  echo "Deploying $dir/ → $REMOTE:$REMOTE_CONFIG/$dir/"
  rsync -avz --delete \
    --exclude="*.template" \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/$dir/" \
    "$REMOTE:$REMOTE_CONFIG/$dir/"
}

deploy_scripts() {
  echo "Deploying scripts/ → $REMOTE:$REMOTE_SCRIPTS/"
  rsync -avz --delete \
    --exclude="venv/" \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude=".env" \
    --exclude="openhab/"  \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/scripts/" \
    "$REMOTE:$REMOTE_SCRIPTS/"
  echo ""
  echo "NOTE: First-time deploy? SSH in and run setup.sh in each script directory:"
  echo "  ssh $REMOTE 'cd $REMOTE_SCRIPTS/train-tracker && bash setup.sh'"
  echo "  ssh $REMOTE 'cd $REMOTE_SCRIPTS/battery-monitor && bash setup.sh'"
}

deploy_file() {
  local file="$1"
  local remote_dir
  remote_dir="$(dirname "$file")"
  echo "Deploying $file → $REMOTE:$REMOTE_CONFIG/$file"
  rsync -avz \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/$file" \
    "$REMOTE:$REMOTE_CONFIG/$remote_dir/"
}

case "$TARGET" in
  all)
    deploy_config_dir items
    deploy_config_dir rules
    deploy_config_dir things
    deploy_scripts
    echo ""
    echo "Done. OpenHAB will pick up config changes automatically (file watcher)."
    ;;
  items|rules|things)
    deploy_config_dir "$TARGET"
    ;;
  scripts)
    deploy_scripts
    ;;
  *)
    # Treat as a specific file path relative to repo root
    if [[ -f "$SCRIPT_DIR/$TARGET" ]]; then
      deploy_file "$TARGET"
    else
      echo "ERROR: '$TARGET' is not a valid target (items/rules/things/scripts) or file path."
      exit 1
    fi
    ;;
esac
