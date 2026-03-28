# OpenHAB Battery Monitor

A Python tool to monitor battery-powered devices on an OpenHAB server and detect dead batteries by checking device activity rather than just battery percentage.

## Features

- Scans all battery-powered devices on your OpenHAB server
- Detects dead batteries by monitoring device activity (not just battery level)
- Configurable inactivity threshold (default: 24 hours)
- Sends notifications via OpenHAB cloud notification system
- Detailed reporting of device status
- REST API integration with authentication

## How It Works

The script uses a smarter approach to detecting dead batteries:

1. Finds all battery items on your OpenHAB server
2. For each battery item, identifies the parent Thing and all its items
3. Checks the persistence history to see when items last updated
4. Flags devices where no items have changed within the threshold period
5. Sends notifications about devices that need battery replacement

This approach is more reliable than checking battery percentage alone, as batteries can die before reaching 0%.

## Installation

### 1. Clone or download this project

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your OpenHAB credentials:
```
OPENHAB_URL=http://your-openhab-server:8080
OPENHAB_TOKEN=your_api_token_here
THRESHOLD_HOURS=24
```

## Getting an OpenHAB API Token

1. Log into your OpenHAB instance
2. Go to Settings → API Security
3. Create a new API token
4. Copy the token to your `.env` file

## Usage

### Command Line

Basic usage:
```bash
python battery_monitor.py --token YOUR_TOKEN
```

With all options:
```bash
python battery_monitor.py \
    --url http://localhost:8080 \
    --token YOUR_TOKEN \
    --threshold 24 \
    --notify \
    --verbose
```

### Arguments

- `--url`: OpenHAB server URL (default: http://localhost:8080)
- `--token`: OpenHAB API token (required)
- `--threshold`: Hours of inactivity to consider device dead (default: 24)
- `--notify`: Send notification for dead batteries
- `--verbose`: Enable verbose logging

### VS Code Debugging

The project includes VS Code debug configurations:

1. Press `F5` or go to Run → Start Debugging
2. Select "Python: Battery Monitor" configuration
3. Set breakpoints as needed

Debug configurations available:
- **Python: Battery Monitor**: Basic monitoring without notifications
- **Python: Battery Monitor (with notification)**: Includes notification sending
- **Python: Current File**: Debug any Python file

## Example Output

```
============================================================
BATTERY MONITOR REPORT - 2026-02-17 10:30:45
============================================================

⚠️  Found 2 device(s) with dead batteries:

1. Thing: zwave:device:controller:node23
   Battery Item: ZWave_Node23_Battery
   Battery Level: 45%
   Last Activity: 2026-02-15 18:20:10 (40.2h ago)
   Inactive Items: 3/4

2. Thing: zigbee:xiaomi_sensor:00158d0001a2b3c4
   Battery Item: XiaomiSensor_Battery
   Battery Level: 62%
   Last Activity: Never recorded
   Inactive Items: 2/2

============================================================
```

## Scheduling Regular Checks

### Windows Task Scheduler

1. Open Task Scheduler
2. Create a new task
3. Set trigger (e.g., daily at 8 AM)
4. Set action: Run your Python script with arguments

### Linux Cron

Add to crontab:
```bash
0 8 * * * cd /path/to/project && ./venv/bin/python battery_monitor.py --token YOUR_TOKEN --notify
```

## Project Structure

```
openhab-battery-monitor/
├── battery_monitor.py      # Main script
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .env                   # Your actual config (not in git)
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── .vscode/              # VS Code settings
    ├── settings.json     # Python interpreter, formatting, linting
    ├── launch.json       # Debug configurations
    └── extensions.json   # Recommended extensions
```

## Requirements

- Python 3.8+
- OpenHAB 3.x or 4.x with persistence enabled
- API token with read access to items and things
- Persistence service configured (e.g., rrd4j, influxdb, jdbc)

## Troubleshooting

### "No persistence data" errors

Make sure:
1. Persistence is enabled in OpenHAB
2. Items are configured to persist
3. The persistence service is running

### Items not found

Check that:
1. Your API token has correct permissions
2. Battery items follow naming conventions (contain "battery" in name/label)
3. Items are linked to Things properly

### False positives

Adjust the `--threshold` value:
- Increase for devices that update infrequently
- Decrease for more frequent checks
- Consider different thresholds for different device types

## Future Enhancements

Possible improvements:
- [ ] Per-device threshold configuration
- [ ] Email notifications
- [ ] Telegram/Slack integration
- [ ] Web dashboard
- [ ] Historical tracking
- [ ] Battery life predictions

## License

Free to use and modify for personal and commercial purposes.

## Contributing

Feel free to submit issues and enhancement requests!
