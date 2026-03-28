#!/usr/bin/env bash
# deploy.sh — Deploy OpenHAB config and Python scripts to the OpenHAB server via SSH/rsync
#
# Usage:
#   ./deploy.sh [-n] [target]
#
#   Targets:
#     (none)     deploy all (items, rules, things, scripts)
#     items      deploy only items/
#     rules      deploy only rules/
#     things     deploy only things/
#     scripts    deploy Python scripts to $OPENHAB_SCRIPTS_PATH
#     path/file  deploy a single file (e.g. rules/trains.rules)
#
#   Flags:
#     -n         dry-run — show what WOULD be transferred, make no changes
#
# OpenHAB config files → $OPENHAB_CONFIG_PATH  (default: /etc/openhab)
# Python scripts       → $OPENHAB_SCRIPTS_PATH (default: /opt/openhab-scripts)
#
# ── Prerequisites ──────────────────────────────────────────────────────────────
#  1. Copy .env.example to .env and fill in your values
#  2. SSH key-based auth: ssh-copy-id $OPENHAB_SSH_USER@$OPENHAB_HOST
#  3. rsync must be installed locally (comes with Git for Windows/WSL)
#  4. Sudo-less rsync on the server (needed because /etc/openhab is owned by openhab):
#       Run once on the Debian server:
#         echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/rsync" | sudo tee /etc/sudoers.d/rsync-deploy
#       Then set OPENHAB_SUDO_RSYNC=true in .env
#
# ── Safety notes ───────────────────────────────────────────────────────────────
#  - --delete is NOT used for config dirs. Files on the server that are not in
#    git are left untouched. Remove obsolete files manually via SSH if needed.
#  - OpenHAB's file watcher picks up changes immediately. Use -n first to review.
#  - scripts/ uses --delete because venvs are recreated by setup.sh anyway.

set -euo pipefail

# ── Parse flags ───────────────────────────────────────────────────────────────
DRY_RUN=false
if [[ "${1:-}" == "-n" ]]; then
  DRY_RUN=true
  shift
fi
TARGET="${1:-all}"

# ── Load .env ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in your values."
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

# ── Validate required vars ────────────────────────────────────────────────────
: "${OPENHAB_HOST:?OPENHAB_HOST not set in .env}"
: "${OPENHAB_SSH_USER:?OPENHAB_SSH_USER not set in .env}"
: "${OPENHAB_CONFIG_PATH:?OPENHAB_CONFIG_PATH not set in .env}"

# ── SSH / rsync options ───────────────────────────────────────────────────────
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
if [[ -n "${OPENHAB_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "$OPENHAB_SSH_KEY")
fi
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

REMOTE="${OPENHAB_SSH_USER}@${OPENHAB_HOST}"
REMOTE_CONFIG="${OPENHAB_CONFIG_PATH%/}"                       # e.g. /etc/openhab
REMOTE_SCRIPTS="${OPENHAB_SCRIPTS_PATH:-/opt/openhab-scripts}" # e.g. /opt/openhab-scripts

# Use sudo rsync on the server side if the SSH user lacks write access to /etc/openhab
# Enable with: OPENHAB_SUDO_RSYNC=true in .env
# Requires: echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/rsync" | sudo tee /etc/sudoers.d/rsync-deploy
if [[ "${OPENHAB_SUDO_RSYNC:-false}" == "true" ]]; then
  RSYNC_PATH_OPT="--rsync-path=sudo rsync"
else
  RSYNC_PATH_OPT=""
fi

RSYNC_BASE_OPTS=(-avz)
if $DRY_RUN; then
  RSYNC_BASE_OPTS+=(-n)
  echo "DRY RUN — no changes will be made"
  echo ""
fi

# ── Helper: show what's on the server but not in git (would be left behind) ──
check_server_extras() {
  local remote_dir="$1"
  local local_dir="$2"
  echo "  Checking for server-only files in $remote_dir (files NOT in git that would be left behind)..."
  # shellcheck disable=SC2029
  ssh "${SSH_OPTS[@]}" "$REMOTE" "ls $remote_dir/ 2>/dev/null" | while read -r f; do
    if [[ ! -e "$local_dir/$f" ]]; then
      echo "  [SERVER ONLY] $remote_dir/$f"
    fi
  done
}

# ── Deploy functions ──────────────────────────────────────────────────────────
deploy_config_dir() {
  local dir="$1"
  echo "── Deploying $dir/ → $REMOTE:$REMOTE_CONFIG/$dir/"
  check_server_extras "$REMOTE_CONFIG/$dir" "$SCRIPT_DIR/$dir"
  # No --delete: server-only files are left untouched (safe for OpenHAB UI-created items)
  rsync "${RSYNC_BASE_OPTS[@]}" \
    ${RSYNC_PATH_OPT:+"$RSYNC_PATH_OPT"} \
    --exclude="*.template" \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/$dir/" \
    "$REMOTE:$REMOTE_CONFIG/$dir/"
}

deploy_scripts() {
  echo "── Deploying Scripts/ → $REMOTE:$REMOTE_SCRIPTS/"
  # --delete is safe here: venvs are excluded and recreated by setup.sh
  rsync "${RSYNC_BASE_OPTS[@]}" \
    --delete \
    --exclude="venv/" \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude=".env" \
    --exclude="openhab/" \
    --exclude=".claude/" \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/Scripts/" \
    "$REMOTE:$REMOTE_SCRIPTS/"
  if ! $DRY_RUN; then
    echo ""
    echo "NOTE: First-time deploy? SSH in and run setup.sh in each script directory:"
    echo "  ssh $REMOTE 'cd $REMOTE_SCRIPTS/train-tracker && bash setup.sh'"
    echo "  ssh $REMOTE 'cd $REMOTE_SCRIPTS/battery-monitor && bash setup.sh'"
  fi
}

deploy_file() {
  local file="$1"
  local remote_dir
  remote_dir="$(dirname "$file")"
  echo "── Deploying $file → $REMOTE:$REMOTE_CONFIG/$file"
  rsync "${RSYNC_BASE_OPTS[@]}" \
    ${RSYNC_PATH_OPT:+"$RSYNC_PATH_OPT"} \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/$file" \
    "$REMOTE:$REMOTE_CONFIG/$remote_dir/"
}

# ── Main ─────────────────────────────────────────────────────────────────────
case "$TARGET" in
  all)
    deploy_config_dir items
    deploy_config_dir rules
    deploy_config_dir things
    deploy_scripts
    echo ""
    $DRY_RUN && echo "Dry run complete. Run without -n to apply." \
             || echo "Done. OpenHAB picks up config changes automatically."
    ;;
  items|rules|things)
    deploy_config_dir "$TARGET"
    ;;
  scripts)
    deploy_scripts
    ;;
  *)
    if [[ -f "$SCRIPT_DIR/$TARGET" ]]; then
      deploy_file "$TARGET"
    else
      echo "ERROR: '$TARGET' is not a valid target (items/rules/things/scripts) or file path."
      exit 1
    fi
    ;;
esac
