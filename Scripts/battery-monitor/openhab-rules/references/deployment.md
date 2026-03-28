# Deployment & Rollback Procedures

Development on Windows → Deployment to OpenHAB Linux server with Git-based version control and automated rollback.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Windows Development Machine (VSCode)                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Local Git Repo                                          │ │
│ │ ├── rules/              (*.rules files)                 │ │
│ │ ├── items/              (*.items files)                 │ │
│ │ ├── scripts/            (Python scripts)                │ │
│ │ ├── transform/          (*.map files for secrets)       │ │
│ │ └── deploy/             (deployment scripts)            │ │
│ └─────────────────────────────────────────────────────────┘ │
│          ↓ git push                                          │
└──────────┼───────────────────────────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────────────────────────┐
│ GitHub Repository (Optional)                                 │
│ - Version history                                            │
│ - Backup                                                     │
│ - Collaboration                                              │
└──────────┼───────────────────────────────────────────────────┘
           │
           ↓ git pull (via deploy script)
┌──────────────────────────────────────────────────────────────┐
│ OpenHAB Server (Debian/Linux)                                │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ /home/openhab/openhab-config (git clone)              │   │
│ │ └── Staging area for deployment                       │   │
│ └────────────────────────────────────────────────────────┘   │
│          ↓ deploy.sh (with backup)                           │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ /etc/openhab/                                          │   │
│ │ ├── rules/             (production rules)             │   │
│ │ ├── items/             (production items)             │   │
│ │ └── transform/         (production secrets)           │   │
│ └────────────────────────────────────────────────────────┘   │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ /opt/                                                  │   │
│ │ └── script-name/       (Python scripts with venv)     │   │
│ └────────────────────────────────────────────────────────┘   │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ /var/backups/openhab/  (timestamped backups)          │   │
│ │ ├── 2026-03-11_14-30-00/                              │   │
│ │ ├── 2026-03-11_15-45-12/                              │   │
│ │ └── latest → 2026-03-11_15-45-12                      │   │
│ └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
openhab-config/
├── .gitignore
├── README.md
├── rules/
│   ├── ulanzimessages.rules
│   ├── senddewpointalert.rules
│   ├── washing.rules
│   └── ...
├── items/
│   ├── Ulanzi.items
│   ├── washing.items
│   └── ...
├── transform/
│   ├── secrets.map.example      # Template, not actual secrets
│   └── README.md                # Instructions for secrets
├── scripts/
│   ├── battery-monitor/
│   │   ├── battery_monitor.py
│   │   ├── requirements.txt
│   │   ├── .env.example         # Template
│   │   └── README.md
│   └── other-script/
│       └── ...
└── deploy/
    ├── deploy.sh                # Main deployment script
    ├── rollback.sh              # Rollback script
    ├── validate.sh              # Pre-deployment validation
    └── config.sh                # Configuration (paths, etc.)
```

### .gitignore

```gitignore
# Secrets - NEVER commit
*.env
transform/secrets.map
**/token*
**/password*

# Python
__pycache__/
*.py[cod]
**/venv/
*.so

# IDE
.vscode/settings.json
.idea/

# Backups
*.backup
*.bak
*~

# Logs
*.log

# OS
.DS_Store
Thumbs.db
```

---

## Personal User Setup (Debian)

**Using your own user account instead of openhab user** — allows deployment without switching users.

### 1. Add Your User to openhab Group

```bash
# SSH with your personal account
ssh yourusername@your-debian-server

# Add yourself to openhab group
sudo usermod -a -G openhab yourusername

# Verify group membership
groups yourusername
# Should show: yourusername : yourusername openhab ...

# Log out and back in for group changes to take effect
exit
ssh yourusername@your-debian-server

# Confirm openhab group is active
groups
# Should now include 'openhab'
```

### 2. Configure Sudo for OpenHAB Service

Allow your user to manage OpenHAB service without password:

```bash
# Create sudoers file for OpenHAB management
sudo visudo -f /etc/sudoers.d/openhab-deploy

# Add these lines (replace 'yourusername' with your actual username):
# Allow user to manage OpenHAB service without password
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl start openhab
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl stop openhab
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl restart openhab
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl status openhab
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl is-active openhab

# Allow user to change file ownership to openhab
yourusername ALL=(ALL) NOPASSWD: /bin/chown -R openhab\:openhab *
yourusername ALL=(ALL) NOPASSWD: /bin/chown openhab\:openhab *

# Allow user to change file permissions
yourusername ALL=(ALL) NOPASSWD: /bin/chmod * *

# Save and exit (Ctrl+X, Y, Enter in nano)
```

Verify sudo access:
```bash
# These should work without asking for password
sudo systemctl status openhab
sudo chown openhab:openhab /tmp/test.txt
```

### 3. Set Directory Permissions

Allow your user to write to OpenHAB directories:

```bash
# Make openhab group writable
sudo chmod g+w /etc/openhab/rules
sudo chmod g+w /etc/openhab/items
sudo chmod g+w /etc/openhab/transform

# Set group sticky bit (new files inherit openhab group)
sudo chmod g+s /etc/openhab/rules
sudo chmod g+s /etc/openhab/items
sudo chmod g+s /etc/openhab/transform

# Allow writing to scripts directory
sudo chmod g+w /opt
sudo chmod g+s /opt

# Create and configure backup directory
sudo mkdir -p /var/backups/openhab
sudo chown root:openhab /var/backups/openhab
sudo chmod g+w /var/backups/openhab
sudo chmod g+s /var/backups/openhab

# Create user's working directory
mkdir -p /home/yourusername/openhab-config
```

### 4. SSH Key Setup (Passwordless Deployment)

**On Windows:**

```powershell
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your.email@example.com"

# Copy public key to Debian server
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh yourusername@your-debian-server "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**On Debian server:**

```bash
# Set correct permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

**Test passwordless login:**
```powershell
# From Windows - should connect without password
ssh yourusername@your-debian-server
```

### 5. Update Deployment Scripts for Personal User

Edit `deploy/config.sh`:

```bash
#!/bin/bash
# Deployment configuration

# User (will be detected automatically)
DEPLOY_USER="${USER}"

# Paths
REPO_DIR="${HOME}/openhab-config"
OPENHAB_CONF="/etc/openhab"
BACKUP_DIR="/var/backups/openhab"
SCRIPTS_DIR="/opt"

# OpenHAB service
OPENHAB_SERVICE="openhab"

# Backup retention (days)
BACKUP_RETENTION_DAYS=30

# Validation
VALIDATE_SYNTAX=true

# Dry run mode (set to true for testing)
DRY_RUN=false
```

### 6. Update deploy.sh User Check

Find this section in `deploy/deploy.sh`:

```bash
# Check if running as correct user
if [ "$(whoami)" != "openhab" ] && [ "$(whoami)" != "root" ]; then
    echo -e "${RED}❌ ERROR: Must run as openhab or root user${NC}"
    exit 1
fi
```

Replace with:

```bash
# Check if user is in openhab group
if ! groups | grep -q "\bopenhab\b"; then
    echo -e "${RED}❌ ERROR: User $(whoami) is not in openhab group${NC}"
    echo "Run: sudo usermod -a -G openhab $(whoami)"
    echo "Then log out and back in"
    exit 1
fi
```

Apply same change to `rollback.sh` and `validate.sh`.

### 7. Update File Ownership Commands

In `deploy.sh`, change ownership commands from:

```bash
chown openhab:openhab "${OPENHAB_CONF}/rules"/*.rules
```

To:

```bash
sudo chown openhab:openhab "${OPENHAB_CONF}/rules"/*.rules
```

Apply to all `chown` commands in the script.

### 8. Update Service Restart Commands

In `deploy.sh`, change restart commands from:

```bash
systemctl restart "${OPENHAB_SERVICE}"
```

To:

```bash
sudo systemctl restart "${OPENHAB_SERVICE}"
```

Apply to all `systemctl` commands in the script.

---

## Initial Setup

### 1. Initialize Git Repository on Windows

```powershell
# In your OpenHAB config directory
cd C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\Openhab\Config

# Initialize git
git init

# Create structure
New-Item -ItemType Directory -Force deploy, scripts, transform

# Copy .gitignore
# (content from above)

# Initial commit
git add .
git commit -m "Initial commit: OpenHAB configuration"

# Optional: Create GitHub repository and push
git remote add origin https://github.com/yourusername/openhab-config.git
git branch -M main
git push -u origin main
```

### 2. Setup OpenHAB Server

```bash
# SSH into OpenHAB server
ssh openhab@your-openhab-server

# Create directories
sudo mkdir -p /var/backups/openhab
sudo mkdir -p /home/openhab/openhab-config
sudo chown -R openhab:openhab /var/backups/openhab
sudo chown -R openhab:openhab /home/openhab/openhab-config

# Clone repository
cd /home/openhab
git clone https://github.com/yourusername/openhab-config.git
# OR for private SSH access:
git clone git@github.com:yourusername/openhab-config.git

# Make deployment scripts executable
cd /home/openhab/openhab-config/deploy
chmod +x deploy.sh rollback.sh validate.sh
```

---

## Deployment Scripts

### deploy/config.sh

```bash
#!/bin/bash
# Deployment configuration

# Paths
REPO_DIR="/home/openhab/openhab-config"
OPENHAB_CONF="/etc/openhab"
BACKUP_DIR="/var/backups/openhab"
SCRIPTS_DIR="/opt"

# OpenHAB service
OPENHAB_SERVICE="openhab"

# Backup retention (days)
BACKUP_RETENTION_DAYS=30

# Validation
VALIDATE_SYNTAX=true

# Dry run mode (set to true for testing)
DRY_RUN=false
```

### deploy/validate.sh

```bash
#!/bin/bash
# Pre-deployment validation

set -e

# Source config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "=== OpenHAB Configuration Validation ==="
echo ""

# Check if running as openhab user
if [ "$(whoami)" != "openhab" ] && [ "$(whoami)" != "root" ]; then
    echo "❌ ERROR: Must run as openhab or root user"
    exit 1
fi

# Validate rules syntax
echo "Validating rules files..."
RULES_VALID=true
for rule_file in "${REPO_DIR}/rules"/*.rules; do
    if [ -f "$rule_file" ]; then
        filename=$(basename "$rule_file")

        # Basic syntax checks
        if grep -q "rule \".*\"" "$rule_file"; then
            echo "  ✅ $filename: Basic structure OK"
        else
            echo "  ⚠️  $filename: No rules found (might be empty)"
        fi

        # Check for common errors
        if grep -q "\.state as DecimalType" "$rule_file"; then
            echo "  ⚠️  $filename: Uses DecimalType (should be Number or QuantityType)"
        fi

        if grep -q "executeCommandLine.*\$" "$rule_file"; then
            echo "  ⚠️  $filename: Possible command injection risk (variable in command)"
        fi
    fi
done

# Validate Python scripts
echo ""
echo "Validating Python scripts..."
for script_dir in "${REPO_DIR}/scripts"/*; do
    if [ -d "$script_dir" ]; then
        script_name=$(basename "$script_dir")

        # Check for requirements.txt
        if [ -f "$script_dir/requirements.txt" ]; then
            echo "  ✅ $script_name: requirements.txt found"
        else
            echo "  ⚠️  $script_name: No requirements.txt"
        fi

        # Check for .env.example
        if [ -f "$script_dir/.env.example" ]; then
            echo "  ✅ $script_name: .env.example template found"
        else
            echo "  ⚠️  $script_name: No .env.example"
        fi

        # Check Python syntax
        for py_file in "$script_dir"/*.py; do
            if [ -f "$py_file" ]; then
                if python3 -m py_compile "$py_file" 2>/dev/null; then
                    echo "  ✅ $(basename "$py_file"): Python syntax OK"
                else
                    echo "  ❌ $(basename "$py_file"): Python syntax ERROR"
                    RULES_VALID=false
                fi
            fi
        done
    fi
done

echo ""
if [ "$RULES_VALID" = true ]; then
    echo "✅ Validation passed"
    exit 0
else
    echo "❌ Validation failed - fix errors before deploying"
    exit 1
fi
```

### deploy/deploy.sh

```bash
#!/bin/bash
# OpenHAB deployment script with backup and rollback support

set -e

# Source config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_VALIDATION=false
SKIP_RESTART=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --skip-restart)
            SKIP_RESTART=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-validation] [--skip-restart] [--dry-run]"
            exit 1
            ;;
    esac
done

echo "=== OpenHAB Deployment Script ==="
echo ""

# Check if running as correct user
if [ "$(whoami)" != "openhab" ] && [ "$(whoami)" != "root" ]; then
    echo -e "${RED}❌ ERROR: Must run as openhab or root user${NC}"
    exit 1
fi

# Pull latest changes
echo "📥 Pulling latest changes from repository..."
cd "${REPO_DIR}"
if ! git pull; then
    echo -e "${RED}❌ ERROR: Failed to pull from repository${NC}"
    exit 1
fi

# Validate configuration
if [ "$SKIP_VALIDATION" = false ]; then
    echo ""
    echo "🔍 Validating configuration..."
    if ! bash "${SCRIPT_DIR}/validate.sh"; then
        echo -e "${RED}❌ ERROR: Validation failed${NC}"
        exit 1
    fi
fi

# Create backup
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

echo ""
echo "💾 Creating backup at ${BACKUP_PATH}..."
if [ "$DRY_RUN" = false ]; then
    mkdir -p "${BACKUP_PATH}"

    # Backup rules
    if [ -d "${OPENHAB_CONF}/rules" ]; then
        cp -r "${OPENHAB_CONF}/rules" "${BACKUP_PATH}/"
        echo "  ✅ Rules backed up"
    fi

    # Backup items
    if [ -d "${OPENHAB_CONF}/items" ]; then
        cp -r "${OPENHAB_CONF}/items" "${BACKUP_PATH}/"
        echo "  ✅ Items backed up"
    fi

    # Backup transform
    if [ -d "${OPENHAB_CONF}/transform" ]; then
        cp -r "${OPENHAB_CONF}/transform" "${BACKUP_PATH}/"
        echo "  ✅ Transform backed up"
    fi

    # Backup scripts
    for script_dir in "${SCRIPTS_DIR}"/*/; do
        if [ -d "$script_dir" ]; then
            script_name=$(basename "$script_dir")
            mkdir -p "${BACKUP_PATH}/scripts"
            cp -r "$script_dir" "${BACKUP_PATH}/scripts/"
            echo "  ✅ Script ${script_name} backed up"
        fi
    done

    # Update 'latest' symlink
    ln -sfn "${BACKUP_PATH}" "${BACKUP_DIR}/latest"

    # Save git commit hash
    git rev-parse HEAD > "${BACKUP_PATH}/git-commit.txt"

    echo "  📝 Backup complete: ${BACKUP_PATH}"
else
    echo "  🏃 DRY RUN: Would create backup at ${BACKUP_PATH}"
fi

# Deploy rules
echo ""
echo "📦 Deploying rules..."
if [ "$DRY_RUN" = false ]; then
    if [ -d "${REPO_DIR}/rules" ]; then
        cp "${REPO_DIR}/rules"/*.rules "${OPENHAB_CONF}/rules/" 2>/dev/null || true
        chown openhab:openhab "${OPENHAB_CONF}/rules"/*.rules
        echo "  ✅ Rules deployed"
    fi
else
    echo "  🏃 DRY RUN: Would deploy rules"
fi

# Deploy items
echo ""
echo "📦 Deploying items..."
if [ "$DRY_RUN" = false ]; then
    if [ -d "${REPO_DIR}/items" ]; then
        cp "${REPO_DIR}/items"/*.items "${OPENHAB_CONF}/items/" 2>/dev/null || true
        chown openhab:openhab "${OPENHAB_CONF}/items"/*.items
        echo "  ✅ Items deployed"
    fi
else
    echo "  🏃 DRY RUN: Would deploy items"
fi

# Deploy transform files (excluding secrets.map)
echo ""
echo "📦 Deploying transform files..."
if [ "$DRY_RUN" = false ]; then
    if [ -d "${REPO_DIR}/transform" ]; then
        # Copy all .map files except secrets.map
        for map_file in "${REPO_DIR}/transform"/*.map; do
            if [ -f "$map_file" ] && [ "$(basename "$map_file")" != "secrets.map" ]; then
                cp "$map_file" "${OPENHAB_CONF}/transform/"
                chown openhab:openhab "${OPENHAB_CONF}/transform/$(basename "$map_file")"
                echo "  ✅ $(basename "$map_file") deployed"
            fi
        done
    fi
else
    echo "  🏃 DRY RUN: Would deploy transform files"
fi

# Deploy Python scripts
echo ""
echo "📦 Deploying Python scripts..."
if [ "$DRY_RUN" = false ]; then
    for script_dir in "${REPO_DIR}/scripts"/*; do
        if [ -d "$script_dir" ]; then
            script_name=$(basename "$script_dir")
            target_dir="${SCRIPTS_DIR}/${script_name}"

            echo "  📝 Deploying ${script_name}..."

            # Create target directory
            mkdir -p "${target_dir}"

            # Copy Python files
            cp "${script_dir}"/*.py "${target_dir}/" 2>/dev/null || true

            # Copy requirements.txt
            if [ -f "${script_dir}/requirements.txt" ]; then
                cp "${script_dir}/requirements.txt" "${target_dir}/"
            fi

            # DO NOT copy .env (must be created manually on server)
            # Warn if .env doesn't exist
            if [ ! -f "${target_dir}/.env" ]; then
                echo -e "  ${YELLOW}⚠️  No .env file found in ${target_dir}${NC}"
                echo "     Create it manually from .env.example"
            fi

            # Set up virtual environment if it doesn't exist
            if [ ! -d "${target_dir}/venv" ]; then
                echo "  🔧 Creating virtual environment..."
                python3 -m venv "${target_dir}/venv"
            fi

            # Install/update requirements
            if [ -f "${target_dir}/requirements.txt" ]; then
                echo "  📦 Installing Python dependencies..."
                "${target_dir}/venv/bin/pip" install -q -r "${target_dir}/requirements.txt"
            fi

            # Set permissions
            chown -R openhab:openhab "${target_dir}"
            chmod 755 "${target_dir}"
            chmod 644 "${target_dir}"/*.py 2>/dev/null || true
            chmod 600 "${target_dir}/.env" 2>/dev/null || true

            echo "  ✅ ${script_name} deployed"
        fi
    done
else
    echo "  🏃 DRY RUN: Would deploy Python scripts"
fi

# Restart OpenHAB
if [ "$SKIP_RESTART" = false ]; then
    echo ""
    echo "🔄 Restarting OpenHAB..."
    if [ "$DRY_RUN" = false ]; then
        systemctl restart "${OPENHAB_SERVICE}"
        echo "  ⏳ Waiting for OpenHAB to start..."
        sleep 10

        if systemctl is-active --quiet "${OPENHAB_SERVICE}"; then
            echo -e "  ${GREEN}✅ OpenHAB restarted successfully${NC}"
        else
            echo -e "  ${RED}❌ ERROR: OpenHAB failed to start${NC}"
            echo "  💡 Run: journalctl -u ${OPENHAB_SERVICE} -n 50"
            echo "  💡 To rollback: bash ${SCRIPT_DIR}/rollback.sh"
            exit 1
        fi
    else
        echo "  🏃 DRY RUN: Would restart OpenHAB"
    fi
else
    echo ""
    echo "⏩ Skipping OpenHAB restart (--skip-restart)"
fi

# Clean old backups
echo ""
echo "🧹 Cleaning old backups (keeping ${BACKUP_RETENTION_DAYS} days)..."
if [ "$DRY_RUN" = false ]; then
    find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime +${BACKUP_RETENTION_DAYS} ! -name "latest" -exec rm -rf {} \;
    echo "  ✅ Old backups cleaned"
else
    echo "  🏃 DRY RUN: Would clean old backups"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "📊 Summary:"
echo "  Backup: ${BACKUP_PATH}"
echo "  Git commit: $(cat "${BACKUP_PATH}/git-commit.txt" 2>/dev/null || echo 'N/A')"
echo ""
echo "💡 To rollback: bash ${SCRIPT_DIR}/rollback.sh"
echo "💡 To view logs: tail -f /var/log/openhab/openhab.log"
```

### deploy/rollback.sh

```bash
#!/bin/bash
# OpenHAB rollback script

set -e

# Source config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== OpenHAB Rollback Script ==="
echo ""

# Check if running as correct user
if [ "$(whoami)" != "openhab" ] && [ "$(whoami)" != "root" ]; then
    echo -e "${RED}❌ ERROR: Must run as openhab or root user${NC}"
    exit 1
fi

# List available backups
echo "📂 Available backups:"
BACKUPS=($(ls -1dt "${BACKUP_DIR}"/*/ 2>/dev/null | head -10))

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo -e "${RED}❌ ERROR: No backups found${NC}"
    exit 1
fi

# Display backups
for i in "${!BACKUPS[@]}"; do
    backup_dir="${BACKUPS[$i]}"
    backup_name=$(basename "$backup_dir")

    # Read git commit if available
    git_commit=""
    if [ -f "${backup_dir}/git-commit.txt" ]; then
        git_commit=$(cat "${backup_dir}/git-commit.txt" | cut -c1-8)
    fi

    # Check if it's the latest
    if [ "$(readlink -f "${BACKUP_DIR}/latest")" = "$(readlink -f "$backup_dir")" ]; then
        echo "  $i) $backup_name [LATEST] (commit: $git_commit)"
    else
        echo "  $i) $backup_name (commit: $git_commit)"
    fi
done

# Select backup
echo ""
read -p "Select backup number to restore [0]: " backup_num
backup_num=${backup_num:-0}

if [ $backup_num -lt 0 ] || [ $backup_num -ge ${#BACKUPS[@]} ]; then
    echo -e "${RED}❌ ERROR: Invalid backup number${NC}"
    exit 1
fi

RESTORE_PATH="${BACKUPS[$backup_num]}"
echo ""
echo -e "${YELLOW}⚠️  Will restore from: ${RESTORE_PATH}${NC}"
echo ""
read -p "Continue? (yes/no) [no]: " confirm
if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

# Create backup of current state before rollback
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
PRE_ROLLBACK_BACKUP="${BACKUP_DIR}/pre-rollback-${TIMESTAMP}"
echo ""
echo "💾 Creating pre-rollback backup..."
mkdir -p "${PRE_ROLLBACK_BACKUP}"
cp -r "${OPENHAB_CONF}/rules" "${PRE_ROLLBACK_BACKUP}/" 2>/dev/null || true
cp -r "${OPENHAB_CONF}/items" "${PRE_ROLLBACK_BACKUP}/" 2>/dev/null || true
echo "  ✅ Pre-rollback backup created: ${PRE_ROLLBACK_BACKUP}"

# Restore rules
echo ""
echo "🔄 Restoring rules..."
if [ -d "${RESTORE_PATH}/rules" ]; then
    rm -f "${OPENHAB_CONF}/rules"/*.rules
    cp "${RESTORE_PATH}/rules"/*.rules "${OPENHAB_CONF}/rules/" 2>/dev/null || true
    chown openhab:openhab "${OPENHAB_CONF}/rules"/*.rules
    echo "  ✅ Rules restored"
fi

# Restore items
echo ""
echo "🔄 Restoring items..."
if [ -d "${RESTORE_PATH}/items" ]; then
    rm -f "${OPENHAB_CONF}/items"/*.items
    cp "${RESTORE_PATH}/items"/*.items "${OPENHAB_CONF}/items/" 2>/dev/null || true
    chown openhab:openhab "${OPENHAB_CONF}/items"/*.items
    echo "  ✅ Items restored"
fi

# Restore transform
echo ""
echo "🔄 Restoring transform files..."
if [ -d "${RESTORE_PATH}/transform" ]; then
    cp "${RESTORE_PATH}/transform"/*.map "${OPENHAB_CONF}/transform/" 2>/dev/null || true
    chown openhab:openhab "${OPENHAB_CONF}/transform"/*.map
    echo "  ✅ Transform files restored"
fi

# Restore scripts
echo ""
echo "🔄 Restoring Python scripts..."
if [ -d "${RESTORE_PATH}/scripts" ]; then
    for script_backup in "${RESTORE_PATH}/scripts"/*; do
        if [ -d "$script_backup" ]; then
            script_name=$(basename "$script_backup")
            target_dir="${SCRIPTS_DIR}/${script_name}"

            echo "  📝 Restoring ${script_name}..."
            rm -rf "${target_dir}"
            cp -r "$script_backup" "${SCRIPTS_DIR}/"
            chown -R openhab:openhab "${target_dir}"
            echo "  ✅ ${script_name} restored"
        fi
    done
fi

# Restart OpenHAB
echo ""
echo "🔄 Restarting OpenHAB..."
systemctl restart "${OPENHAB_SERVICE}"
echo "  ⏳ Waiting for OpenHAB to start..."
sleep 10

if systemctl is-active --quiet "${OPENHAB_SERVICE}"; then
    echo -e "  ${GREEN}✅ OpenHAB restarted successfully${NC}"
else
    echo -e "  ${RED}❌ ERROR: OpenHAB failed to start${NC}"
    echo "  💡 Run: journalctl -u ${OPENHAB_SERVICE} -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Rollback complete!${NC}"
echo ""
echo "📊 Summary:"
echo "  Restored from: ${RESTORE_PATH}"
echo "  Pre-rollback backup: ${PRE_ROLLBACK_BACKUP}"
echo ""
echo "💡 To view logs: tail -f /var/log/openhab/openhab.log"
```

---

## VSCode Configuration

### .vscode/tasks.json

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Deploy to OpenHAB",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "git add . && git commit -m 'Deploy: ${input:commitMessage}' && git push && ssh openhab@${input:serverAddress} 'cd /home/openhab/openhab-config && bash deploy/deploy.sh'"
            ],
            "problemMatcher": [],
            "group": {
                "kind": "build",
                "isDefault": false
            }
        },
        {
            "label": "Validate Configuration",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "ssh openhab@${input:serverAddress} 'cd /home/openhab/openhab-config && bash deploy/validate.sh'"
            ],
            "problemMatcher": [],
            "group": {
                "kind": "test",
                "isDefault": true
            }
        },
        {
            "label": "Rollback OpenHAB",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "ssh -t openhab@${input:serverAddress} 'cd /home/openhab/openhab-config && bash deploy/rollback.sh'"
            ],
            "problemMatcher": []
        },
        {
            "label": "View OpenHAB Logs",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "ssh openhab@${input:serverAddress} 'tail -f /var/log/openhab/openhab.log'"
            ],
            "problemMatcher": [],
            "isBackground": true
        }
    ],
    "inputs": [
        {
            "id": "serverAddress",
            "type": "promptString",
            "description": "OpenHAB server address",
            "default": "your-openhab-server"
        },
        {
            "id": "commitMessage",
            "type": "promptString",
            "description": "Commit message",
            "default": "Configuration update"
        }
    ]
}
```

### .vscode/settings.json (add to existing)

```json
{
    "files.associations": {
        "*.rules": "java",
        "*.items": "properties",
        "*.map": "properties"
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/venv": true
    }
}
```

---

## Deployment Procedures

### Standard Deployment

**From Windows VSCode:**

1. **Make changes** to rules/items/scripts
2. **Test locally** (if possible with OpenHAB extension)
3. **Commit changes**:
   ```powershell
   git add .
   git commit -m "Update: dewpoint alert thresholds"
   git push
   ```
4. **Deploy via VSCode Task**:
   - Press `Ctrl+Shift+P`
   - Type "Tasks: Run Task"
   - Select "Deploy to OpenHAB"
   - Enter server address and commit message

**OR manually via SSH:**

```bash
ssh openhab@your-openhab-server
cd /home/openhab/openhab-config
bash deploy/deploy.sh
```

### Emergency Rollback

**Via VSCode Task:**
- Press `Ctrl+Shift+P`
- Type "Tasks: Run Task"
- Select "Rollback OpenHAB"
- Select backup to restore

**OR manually:**

```bash
ssh openhab@your-openhab-server
cd /home/openhab/openhab-config
bash deploy/rollback.sh
```

### Validation Only (No Deployment)

```bash
ssh openhab@your-openhab-server
cd /home/openhab/openhab-config
bash deploy/validate.sh
```

### Dry Run Deployment (Test)

```bash
ssh openhab@your-openhab-server
cd /home/openhab/openhab-config
bash deploy/deploy.sh --dry-run
```

---

## Secrets Management

### Initial Setup on Server

1. **Create secrets.map**:
   ```bash
   ssh openhab@your-openhab-server
   sudo nano /etc/openhab/transform/secrets.map
   ```

2. **Add secrets** (example):
   ```properties
   api_token=your_actual_token_here
   telegram_token=your_telegram_bot_token
   weather_api_key=your_api_key
   ```

3. **Set permissions**:
   ```bash
   sudo chmod 600 /etc/openhab/transform/secrets.map
   sudo chown openhab:openhab /etc/openhab/transform/secrets.map
   ```

4. **Create .env for Python scripts**:
   ```bash
   cd /opt/battery-monitor
   cp .env.example .env
   nano .env
   # Add actual values
   chmod 600 .env
   ```

**IMPORTANT**: Never commit actual secrets to git!

---

## GitHub Actions (Optional Automation)

### .github/workflows/validate.yml

```yaml
name: Validate OpenHAB Configuration

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Validate Python scripts
      run: |
        for script_dir in scripts/*/; do
          if [ -d "$script_dir" ]; then
            echo "Validating $script_dir"
            for py_file in "$script_dir"/*.py; do
              if [ -f "$py_file" ]; then
                python3 -m py_compile "$py_file"
                echo "✅ $(basename "$py_file") syntax OK"
              fi
            done
          fi
        done

    - name: Check for secrets in code
      run: |
        if grep -r "Bearer [a-zA-Z0-9]" rules/ items/ scripts/; then
          echo "❌ Found hardcoded Bearer tokens"
          exit 1
        fi
        if grep -r "password.*=.*['\"]" scripts/; then
          echo "❌ Found hardcoded passwords"
          exit 1
        fi
        echo "✅ No hardcoded secrets found"

    - name: Validate .gitignore
      run: |
        if [ ! -f .gitignore ]; then
          echo "❌ Missing .gitignore"
          exit 1
        fi
        if ! grep -q "\.env" .gitignore; then
          echo "❌ .gitignore missing .env"
          exit 1
        fi
        echo "✅ .gitignore OK"
```

---

## Troubleshooting

### Deployment Failed

```bash
# Check OpenHAB logs
ssh openhab@your-server
tail -n 100 /var/log/openhab/openhab.log

# Check service status
systemctl status openhab

# View recent journal entries
journalctl -u openhab -n 50
```

### Rollback Failed

```bash
# Check backup exists
ls -la /var/backups/openhab/

# Manual restore
sudo cp -r /var/backups/openhab/latest/rules/* /etc/openhab/rules/
sudo cp -r /var/backups/openhab/latest/items/* /etc/openhab/items/
sudo systemctl restart openhab
```

### Git Conflicts

```bash
# On server
cd /home/openhab/openhab-config
git stash
git pull
git stash pop
# Resolve conflicts manually
```

---

## Best Practices

### Commit Messages

Follow conventional commits:
```
feat: Add battery monitor script
fix: Correct NULL guard in dewpoint alert
refactor: Simplify Ulanzi message formatting
docs: Update deployment instructions
chore: Update Python dependencies
```

### Before Deploying

- [ ] Commit all changes with clear message
- [ ] Run validation locally if possible
- [ ] Review diff: `git diff HEAD~1`
- [ ] Push to GitHub
- [ ] Deploy during low-activity period

### After Deploying

- [ ] Monitor logs for 5-10 minutes
- [ ] Test critical automations
- [ ] Check OpenHAB UI for errors
- [ ] Keep terminal open for quick rollback

### Backup Strategy

- Automatic backups before each deployment
- 30-day retention policy
- Manual backup before major changes:
  ```bash
  bash deploy/deploy.sh --skip-restart
  # Test manually, then restart if OK
  sudo systemctl restart openhab
  ```

---

## Quick Reference

| Task | Command |
|------|---------|
| Deploy | `bash deploy/deploy.sh` |
| Rollback | `bash deploy/rollback.sh` |
| Validate | `bash deploy/validate.sh` |
| Dry run | `bash deploy/deploy.sh --dry-run` |
| View logs | `tail -f /var/log/openhab/openhab.log` |
| List backups | `ls -lh /var/backups/openhab/` |
| Restart OpenHAB | `sudo systemctl restart openhab` |
