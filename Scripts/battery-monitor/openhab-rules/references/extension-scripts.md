# Python Standalone Scripts

## Overview

Python scripts are deployed at `/opt/script-name/` with isolated virtual environments.
Scripts update OpenHAB items via REST API; separate rules handle notifications.
Every script is delivered as a complete set:
**script file + requirements.txt + .env + calling rule + notification rule + deployment commands**.

## Architecture

```
Python Script ────REST API───> OpenHAB Items ────changed───> Notification Rule ────> Telegram
  /opt/script/                  MyScript_Status                (action service)
```

**Benefits**:
- Scripts remain standalone (can run from cron or rules)
- Centralized notification config in OpenHAB
- Virtual environment isolation prevents dependency conflicts

---

## Standardized Script Header (use every time)

```python
#!/usr/bin/env python3
"""
Script:  script_name.py
Purpose: One-sentence description
"""

import logging
import sys

LOG_FILE   = "/var/log/openhab/scripts.log"
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(filename)s] %(message)s"
DATE_FMT   = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FMT,
    handlers=[logging.FileHandler(LOG_FILE)]
)
log = logging.getLogger(__name__)

def main():
    log.info("Script started")
    try:
        result = run()
        print(result)           # stdout captured by OH rule
        log.info("Done: %s", result)
        sys.exit(0)
    except Exception as e:
        log.error("Failed: %s", str(e))
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

Log line format produced:
```
[2024-03-11 07:30:01] [INFO]  [script_name.py] Script started
[2024-03-11 07:30:02] [ERROR] [script_name.py] HTTP timeout
```

---

## REST API Integration - Updating OpenHAB Items

Scripts update OpenHAB items via REST API instead of sending notifications directly.

### Environment configuration (.env file)
```env
OPENHAB_URL=http://localhost:8080
OPENHAB_TOKEN=oh.scriptname.your_token_here
```

### Load environment variables without external dependencies
```python
from pathlib import Path

def load_env_file(env_path: str = '.env'):
    """Load environment variables from .env file without python-dotenv."""
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load at module level
script_dir = Path(__file__).parent
load_env_file(str(script_dir / '.env'))
```

### Update OpenHAB items
```python
import requests
import os

OPENHAB_URL = os.getenv('OPENHAB_URL', 'http://localhost:8080')
OPENHAB_TOKEN = os.getenv('OPENHAB_TOKEN')

headers = {
    'Authorization': f'Bearer {OPENHAB_TOKEN}',
    'Content-Type': 'text/plain'
}

def update_status(status: str):
    """Update script status item in OpenHAB."""
    requests.post(
        f'{OPENHAB_URL}/rest/items/MyScript_Status',
        headers=headers,
        data=status,
        timeout=5
    )

def update_result(value: int):
    """Update result item in OpenHAB."""
    requests.post(
        f'{OPENHAB_URL}/rest/items/MyScript_Result',
        headers=headers,
        data=str(value),
        timeout=5
    )

# Usage in main()
try:
    update_status("RUNNING")
    result = do_work()
    update_result(result)
    update_status("SUCCESS")
except Exception as e:
    update_status("ERROR")
    raise
```

### requirements.txt
```
requests>=2.31.0
```

---

## Calling from a Rule

```xtend
import org.openhab.core.model.script.actions.Exec
import java.time.Duration

rule "Call Script"
when
    Time cron "0 30 6 * * ?"
then
    logInfo("ScriptCaller", "Starting script execution")

    // Update status item to RUNNING
    if (MyScript_Status.state != NULL) {
        MyScript_Status.postUpdate("RUNNING")
    }

    // Call script using venv Python
    val String result = Exec.executeCommandLine(
        Duration.ofSeconds(60),
        "/opt/script-name/venv/bin/python",
        "/opt/script-name/script_name.py",
        "--verbose"
    )

    if (result === null || result.empty) {
        logError("ScriptCaller", "Script returned nothing")
        MyScript_Status.postUpdate("ERROR")
        return;
    }
    if (result.startsWith("ERROR")) {
        logError("ScriptCaller", "Script error: {}", result)
        MyScript_Status.postUpdate("ERROR")
        return;
    }

    logInfo("ScriptCaller", "Script completed: {}", result)
    // Status updated by script via REST API
end
```

**Note**: The script updates items itself via REST API. This rule just triggers execution and handles errors.

---

## Notification Rule (Separate)

Create a separate rule to watch status items and send Telegram notifications.
This keeps notification config centralized in OpenHAB.

```xtend
rule "Script Notifications"
when
    Item MyScript_Status changed to "SUCCESS" or
    Item MyScript_Status changed to "ERROR"
then
    val String status = MyScript_Status.state.toString
    val telegramAction = getActions("telegram", "telegram:telegramBot:homeAlerts")

    if (status == "ERROR") {
        telegramAction.sendTelegram("⚠️ Script failed: MyScript")
        logWarn("ScriptNotif", "Script error notification sent")
    } else if (status == "SUCCESS") {
        // Optional: only notify on specific conditions
        val result = MyScript_Result.state as Number
        if (result > 0) {
            telegramAction.sendTelegram("✅ Script completed: " + result + " items processed")
        }
    }
end
```

**Benefits**:
- Telegram bot configuration only in OpenHAB (one place)
- Easy to change notification logic without touching Python
- Can add more notification channels (Awtrix, email) without script changes

---

## Deployment: Windows → Linux with Virtual Environment

### Step 1: Transfer files via SCP
```bash
# From Windows, copy to temp location
scp script_name.py requirements.txt .env user@openhab-server:/tmp/
```

### Step 2: Setup on Linux server
```bash
# SSH to server
ssh user@openhab-server

# Create project directory
sudo mkdir -p /opt/script-name
sudo mv /tmp/script_name.py /tmp/requirements.txt /tmp/.env /opt/script-name/
sudo chown -R openhab:openhab /opt/script-name

# Create virtual environment
cd /opt/script-name
python3 -m venv venv

# Install dependencies
./venv/bin/pip install -r requirements.txt

# Make script executable
chmod +x script_name.py

# Verify
ls -la /opt/script-name/
./venv/bin/python script_name.py --help  # Test it works
```

### Step 3: Deploy OpenHAB files
```bash
# Copy items and rules
sudo cp script_items.items /etc/openhab/items/
sudo cp script_rules.rules /etc/openhab/rules/
sudo chown openhab:openhab /etc/openhab/items/script_items.items
sudo chown openhab:openhab /etc/openhab/rules/script_rules.rules

# Restart OpenHAB to load new rules
sudo systemctl restart openhab
```

### Standard permissions
| Resource | Owner | Group | Mode |
|----------|-------|-------|------|
| `/opt/script-name/` | `openhab` | `openhab` | `755` |
| `script_name.py` | `openhab` | `openhab` | `755` |
| `.env` | `openhab` | `openhab` | `600` (sensitive) |
| `venv/` | `openhab` | `openhab` | `755` |

### Delivery template
Always include this deployment block with every script:
```bash
# ── Deploy to OpenHAB Server ──────────────────────────────────────
# 1. Transfer files
#    scp script_name.py requirements.txt .env user@server:/tmp/
#
# 2. SSH and setup
#    ssh user@server
#    sudo mkdir -p /opt/script-name
#    sudo mv /tmp/script_name.py /tmp/requirements.txt /tmp/.env /opt/script-name/
#    sudo chown -R openhab:openhab /opt/script-name
#    cd /opt/script-name && python3 -m venv venv
#    ./venv/bin/pip install -r requirements.txt
#    chmod +x script_name.py
#
# 3. Deploy OpenHAB files
#    sudo cp script_items.items /etc/openhab/items/
#    sudo cp script_rules.rules /etc/openhab/rules/
#    sudo chown openhab:openhab /etc/openhab/items/script_items.items
#    sudo chown openhab:openhab /etc/openhab/rules/script_rules.rules
#    sudo systemctl restart openhab
```

---

## Argument Handling

```python
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--position", type=int, required=True)
    parser.add_argument("--room",     type=str, default="living")
    return parser.parse_args()
```

## stdout Output Convention

| Scenario | Print |
|----------|-------|
| Single value | `print("42")` |
| Success status | `print("OK")` |
| Error | `print("ERROR: reason")` |
| Multiple values | `print("power=45.2 energy=1200")` |

The calling rule parses stdout with string operations.
