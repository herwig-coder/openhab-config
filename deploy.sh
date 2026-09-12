#!/usr/bin/env bash
# deploy.sh — Push changes to GitHub; the OpenHAB server pulls from there.
#
# Workflow:
#   1. Edit files on Windows
#   2. git add / git commit
#   3. ./deploy.sh          ← pushes to GitHub
#   4. On server: sudo git pull   (or set up auto-pull via webhook/cron)
#
# One-time server setup: see CLAUDE.md → "Server Setup"

set -euo pipefail

echo "Pushing to GitHub..."
git push

echo ""
echo "Done. Now pull on the server:"
echo "  ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'"
