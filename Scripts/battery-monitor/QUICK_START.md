# Quick Start Guide

## Setup (Already Done!)

The project is set up and ready to use! Here's what was configured:

- ✅ Virtual environment created
- ✅ Dependencies installed
- ✅ VS Code settings configured
- ✅ Environment file template created

## Next Steps

### 1. Configure Your OpenHAB Connection

Edit the `.env` file with your OpenHAB credentials:

```bash
OPENHAB_URL=http://your-openhab-server:8080
OPENHAB_TOKEN=your_api_token_here
THRESHOLD_HOURS=24
```

**Getting an API Token:**
1. Log into your OpenHAB instance
2. Go to Settings → API Security
3. Create a new API token
4. Copy the token to your `.env` file

### 2. Run the Script

**Option A: Using VS Code (Recommended)**
1. Open this folder in VS Code
2. Make sure you edit the `.env` file first
3. Press `F5` to run with debugging
4. Choose "Python: Battery Monitor" configuration

**Option B: Command Line**

Activate the virtual environment:
```bash
venv\Scripts\activate
```

Run the script:
```bash
python battery_monitor.py --token YOUR_TOKEN
```

With all options:
```bash
python battery_monitor.py --url http://localhost:8080 --token YOUR_TOKEN --threshold 24 --notify --verbose
```

### 3. Understanding the Output

The script will show:
- Total number of devices found
- Battery items detected
- Devices with dead batteries (if any)
- Last activity time for each dead battery device
- Number of inactive items

Example output:
```
⚠️  Found 2 device(s) with dead batteries:

1. Thing: zwave:device:controller:node23
   Battery Item: ZWave_Node23_Battery
   Battery Level: 45%
   Last Activity: 2026-02-15 18:20:10 (40.2h ago)
   Inactive Items: 3/4
```

## How It Works

This script is smarter than just checking battery percentage:

1. **Finds Battery Items**: Scans your OpenHAB server for all battery-related items
2. **Identifies Parent Things**: For each battery, finds the device it belongs to
3. **Checks Activity**: Looks at ALL items from that device (not just battery)
4. **Uses Persistence**: Checks the history to see when items last changed
5. **Flags Dead Batteries**: Reports devices where nothing has changed in X hours

This catches batteries that die at 50% or higher, which percentage checks miss!

## Command Line Arguments

- `--url`: OpenHAB server URL (default: http://localhost:8080)
- `--token`: OpenHAB API token (required)
- `--threshold`: Hours of inactivity to flag (default: 24)
- `--notify`: Send notification via OpenHAB
- `--verbose`: Show detailed logging

## Troubleshooting

### "No persistence data" errors
Make sure persistence is enabled in OpenHAB and items are configured to persist.

### "Failed to fetch items"
Check your API token has correct permissions and the URL is correct.

### False positives
Try adjusting the `--threshold` value. Some devices update less frequently than others.

## Scheduling Regular Checks

### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 8 AM)
4. Action: Start a program
5. Program: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\Python\openhab-battery-monitor\venv\Scripts\python.exe`
6. Arguments: `battery_monitor.py --token YOUR_TOKEN --notify`
7. Start in: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\Python\openhab-battery-monitor`

## Need Help?

Check the full [README.md](README.md) for more detailed documentation.

## Project Files

```
openhab-battery-monitor/
├── battery_monitor.py      # Main script
├── requirements.txt        # Dependencies
├── .env                   # Your config (edit this!)
├── .env.example           # Template
├── README.md             # Full documentation
├── QUICK_START.md        # This file
├── setup.bat             # Windows setup script
└── .vscode/              # VS Code configuration
```
