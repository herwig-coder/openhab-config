# Quick Start Guide - OpenHAB Train Tracker

Get your train delay tracker up and running in 5 minutes!

## Prerequisites

- Python 3.8+ installed
- OpenHAB 3.x or 4.x running (for integration only - script can run standalone)
- No API tokens or credentials required

## 1. Setup

Run the setup script:

**Windows:**
```bash
setup.bat
```

**Linux/Mac:**
```bash
# Fix line endings if copied from Windows
sed -i 's/\r$//' setup.sh

# Make executable and run
chmod +x setup.sh
./setup.sh
```

**Note:** If you see "cannot execute: required file not found", run `bash setup.sh` instead.

This creates a virtual environment, installs dependencies, and creates your `.env` file.

## 2. Configure

Edit the `.env` file with your train route:

```ini
# Train Route Configuration
ORIGIN_STATION=Wien Hbf
DESTINATION_STATION=Salzburg Hbf
SCHEDULED_TIME=08:15

# Maximum train changes (0=direct only, 1=one transfer, etc.)
MAX_TRAIN_CHANGES=0
```

**Station Names:**
Use exact names from ÖBB (e.g., "Wien Hbf", "Salzburg Hbf", "Graz Hbf")

**Note:** The script outputs JSON only. For OpenHAB integration, use the ready-made files in the [openhab/](openhab/) folder.

## 3. OpenHAB Integration (Optional)

**Quick method:** Copy ready-made files from [openhab/](openhab/) folder:
1. Copy `trains.items` to OpenHAB `conf/items/`
2. Copy `trains.rules` to OpenHAB `conf/rules/` and update paths
3. Copy `trains.sitemap` to OpenHAB `conf/sitemaps/` (optional)
4. Restart OpenHAB

**Manual method:** Create these items in OpenHAB:

```
Number TrainDelay_Minutes "Train Delay [%d min]" <time>
String TrainStatus_Text "Train Status [%s]" <text>
DateTime TrainDeparture_Time "Departure Time [%1$tH:%1$tM]" <calendar>
DateTime TrainArrival_Time "Arrival Time [%1$tH:%1$tM]" <calendar>
```

See [openhab/README.md](openhab/README.md) for detailed installation instructions and rule configuration.

## 4. Test

**Test station lookup:**
```bash
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux/Mac

python train_tracker.py --test-station "Wien Hbf"
```

Expected output (JSON):
```json
{
  "success": true,
  "station_name": "Wien Hbf",
  "station_id": "1190100"
}
```

**Test train lookup:**
```bash
python train_tracker.py --verbose
```

Expected output (JSON to stdout, logs to stderr):
```json
{
  "success": true,
  "origin": "Wien Hbf",
  "destination": "Salzburg Hbf",
  "scheduled": "08:15",
  "status": "ON_TIME",
  "delay_minutes": 1,
  "planned_time": "08:15",
  "actual_time": "08:16",
  "departure_time": "2026-03-07T08:16:00",
  "arrival_time": "2026-03-07T11:12:00"
}
```

## 5. Run

**Run once:**
```bash
python train_tracker.py --verbose
```

**Run via VS Code:**
1. Open folder in VS Code
2. Press `F5`
3. Choose "Python: Train Tracker"

## Understanding the Output

### Status Values

- `ON_TIME` - Delay ≤ 2 minutes
- `DELAYED` - Train is delayed (see `delay_minutes` in JSON)
- `CANCELLED` - Train is cancelled
- `NOT_FOUND` - No matching train found (wrong time, no direct connection, etc.)
- `ERROR` - API error or connection issue

### Example Output (Train Delayed)

**stdout (JSON):**
```json
{
  "success": true,
  "origin": "Wien Hbf",
  "destination": "Salzburg Hbf",
  "scheduled": "08:15",
  "status": "DELAYED",
  "delay_minutes": 12,
  "planned_time": "08:15",
  "actual_time": "08:27",
  "departure_time": "2026-03-07T08:27:00",
  "arrival_time": "2026-03-07T11:23:00"
}
```

**stderr (logs with --verbose):**
```
2026-03-07 08:30:15 - INFO - Checking train: Wien Hbf → Salzburg Hbf at 08:15
2026-03-07 08:30:15 - INFO - Found station: Wien Hbf (ID: 1190100)
2026-03-07 08:30:15 - INFO - Found station: Salzburg Hbf (ID: 8100002)
2026-03-07 08:30:16 - INFO - Found connection with 0 change(s), duration: 188 min
2026-03-07 08:30:16 - INFO - Train status: DELAYED (delay: 12 min)
```

### OpenHAB Items After Integration

When using OpenHAB rules (from [openhab/](openhab/) folder), items are updated automatically:
- `TrainDelay_Minutes` = `12`
- `TrainStatus_Text` = `"DELAYED"`
- `TrainDeparture_Time` = `2026-03-07T08:27:00`
- `TrainArrival_Time` = `2026-03-07T11:23:00`

## Scheduling (Optional)

### OpenHAB Integration (Recommended)

If you copied the `trains.rules` file, OpenHAB automatically runs the script:
- Every 15 minutes between 6-10 AM on weekdays
- At 6:30 AM for morning summary

**No additional scheduling needed!** OpenHAB handles it via cron expressions in rules.

### Standalone Scheduling

If running without OpenHAB, use system scheduler:

**Windows Task Scheduler:**
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 7:00 AM, repeat every 15 minutes for 4 hours
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `C:\path\to\train_tracker.py`
   - Start in: `C:\path\to\openhab-train-tracker`

**Linux/Mac Cron:**
```bash
crontab -e
# Add:
*/15 7-11 * * 1-5 cd /path/to/openhab-train-tracker && ./venv/bin/python train_tracker.py
```

## Display in OpenHAB

### Use Ready-Made Sitemap

Copy `trains.sitemap` from [openhab/](openhab/) folder for a complete UI with:
- Color-coded status (green/orange/red)
- Conditional visibility (delay shown only when delayed)
- Departure and arrival times
- Multiple sitemap examples (basic, compact, detailed)

### Quick Custom Example

```
sitemap home label="Home" {
    Frame label="My Commute" {
        Text item=TrainStatus_Text icon="train" valuecolor=[
            "ON_TIME"="green",
            "DELAYED"="orange",
            "CANCELLED"="red",
            "NOT_FOUND"="gray"
        ]
        Text item=TrainDelay_Minutes label="Delay [%d min]"
            visibility=[TrainStatus_Text=="DELAYED"]
            icon="time"
        Text item=TrainDeparture_Time label="Departure [%1$tH:%1$tM]" icon="calendar"
        Text item=TrainArrival_Time label="Arrival [%1$tH:%1$tM]" icon="calendar"
    }
}
```

## Troubleshooting

### "./setup.sh: cannot execute" (Linux/Mac)

**Error:** `./setup.sh: cannot execute: required file not found`

**Fix:**
```bash
# Fix Windows line endings
sed -i 's/\r$//' setup.sh

# Make executable
chmod +x setup.sh

# Run normally
./setup.sh
```

Or simply run with bash:
```bash
bash setup.sh
```

### "Station not found"

Use exact ÖBB station names. Test with:
```bash
python train_tracker.py --test-station "Your Station Name"
```

Common stations:
- `Wien Hbf` (not "Vienna")
- `Salzburg Hbf` (not "Salzburg")
- `Graz Hbf`
- `Innsbruck Hbf`

### "No trains found" (NOT_FOUND status)

Possible reasons:
- No trains at that time (check ÖBB website)
- Wrong destination name or spelling
- Scheduled time in the past
- Night time (no trains running)
- MAX_TRAIN_CHANGES too restrictive (try increasing from 0 to 1)

Run with `--verbose` to see detailed logs:
```bash
python train_tracker.py --verbose
```

Try allowing one transfer:
```bash
python train_tracker.py --max-changes 1 --verbose
```

### OpenHAB items not updating

If using OpenHAB integration:
1. Check OpenHAB logs: `tail -f /var/log/openhab/openhab.log | grep TrainTracker`
2. Verify script paths in `trains.rules` are correct
3. Test script manually to verify JSON output
4. Ensure JSONPATH transformations are installed

See [openhab/README.md](openhab/README.md#troubleshooting) for detailed OpenHAB troubleshooting.

## Command-Line Options

```bash
# Test station lookup
python train_tracker.py --test-station "Wien Hbf"

# Run with verbose logging (logs to stderr, JSON to stdout)
python train_tracker.py --verbose

# Override configuration
python train_tracker.py --origin "Graz Hbf" --destination "Wien Hbf" --time "14:30" --verbose

# Allow transfers
python train_tracker.py --max-changes 1 --verbose
```

## What It Does

1. **Looks up stations** - Converts station names to IDs via HAFAS API
2. **Queries connections** - Uses HAFAS TripSearch API to find connections
3. **Filters by transfers** - Only returns connections with ≤ MAX_TRAIN_CHANGES transfers
4. **Calculates delay** - Compares planned vs actual departure times
5. **Outputs JSON** - Prints structured data to stdout
6. **OpenHAB parses** - Rules read JSON and update items (if using integration)
7. **Exits** - Script completes (OpenHAB rules schedule next run)

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Set up scheduling to run automatically
- Create OpenHAB rules to alert on delays
- Customize for multiple routes

## Project Structure

```
openhab-train-tracker/
├── train_tracker.py       # Main script
├── oebb_profile.py        # Custom ÖBB HAFAS profile
├── .env                   # Your config (EDIT THIS!)
├── .env.example           # Template
├── requirements.txt       # Dependencies
├── README.md              # Full documentation
├── QUICK_START.md         # This file
├── API_SOURCES.md         # API references & technical docs
├── setup.bat              # Windows setup
├── setup.sh               # Linux/Mac setup
└── .vscode/
    └── launch.json        # VS Code debug config
```

## Need Help?

1. Run with `--verbose` to see detailed logs (stderr)
2. Test station lookup with `--test-station "Your Station"`
3. Check the full [README.md](README.md) for troubleshooting
4. Verify `.env` configuration is correct
5. For OpenHAB issues, see [openhab/README.md](openhab/README.md)
6. See [API_SOURCES.md](API_SOURCES.md) for API documentation and technical details

---

**Happy train tracking!** 🚆
