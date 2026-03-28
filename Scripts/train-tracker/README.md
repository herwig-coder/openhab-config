# OpenHAB Train Tracker

Track train delays from Austrian Railways (ÖBB/Scotty) and display the information in OpenHAB.

## Overview

This Python script checks real-time train status (on time, delayed, or cancelled) from ÖBB and updates OpenHAB items with the delay information. Perfect for integrating train status into your smart home automation.

**Features:**
- Real-time delay tracking from ÖBB/Scotty system via HAFAS API
- Configurable origin, destination, and scheduled departure time
- Supports direct connections or connections with specified number of transfers
- Outputs JSON with delay minutes, status, departure time, and arrival time
- Clean architecture: Script outputs JSON, OpenHAB handles all integration
- Runs on demand or via scheduled tasks (Windows Task Scheduler, cron)
- Test modes for validating configuration
- Fully configurable via environment variables or command-line arguments

## How It Works

1. Script loads configuration (train route, scheduled time, maximum train changes)
2. Looks up station IDs from station names using HAFAS API
3. Queries connections using HAFAS TripSearch API
4. Finds next connection matching criteria (direct or with transfers)
5. Calculates delay (difference between planned and actual departure)
6. Outputs JSON with status, delay, departure time, and arrival time to stdout
7. OpenHAB rules parse JSON and update items accordingly

**Data Source:** Uses the [HAFAS API](https://fahrplan.oebb.at/bin/mgate.exe) via the `pyhafas` library with custom ÖBB profile. This is the same API used by the official ÖBB Scotty app.

## Requirements

- Python 3.8 or higher
- OpenHAB 3.x or 4.x (for integration only - script can run standalone)
- Internet connection to access HAFAS API
- No API keys or tokens required

## Quick Start

### 1. Setup

**Windows:**
```bash
setup.bat
```

**Linux/Mac:**
```bash
# Fix line endings if copied from Windows
sed -i 's/\r$//' setup.sh

# Make executable
chmod +x setup.sh

# Run setup
./setup.sh
```

**Note:** If you get "cannot execute: required file not found", the script likely has Windows line endings. Run `sed -i 's/\r$//' setup.sh` to fix it, or use `bash setup.sh` directly.

This will:
- Create a Python virtual environment
- Install dependencies
- Create `.env` file from template

### 2. Configure

Edit the `.env` file with your settings:

```ini
# Train Route Configuration
ORIGIN_STATION=Wien Hbf
DESTINATION_STATION=Salzburg Hbf
SCHEDULED_TIME=08:15

# Optional: Maximum number of train changes (0 = direct only, 1 = one transfer, etc.)
MAX_TRAIN_CHANGES=0
```

**Note:** The script outputs JSON only. OpenHAB integration is handled via rules (see [openhab/](openhab/) folder).

### 3. Create OpenHAB Items (Optional)

If using OpenHAB integration, create these items (via UI or `.items` file):

```
Number TrainDelay_Minutes "Train Delay [%d min]" <time>
String TrainStatus_Text "Train Status [%s]" <text>
DateTime TrainDeparture_Time "Departure Time [%1$tH:%1$tM]" <calendar>
DateTime TrainArrival_Time "Arrival Time [%1$tH:%1$tM]" <calendar>
```

**Ready-to-use OpenHAB configuration files are provided in the [openhab/](openhab/) folder:**
- `trains.items` - Complete item definitions with all required items
- `trains.rules` - Automation rules that execute the script and parse JSON output
- `trains.sitemap` - UI examples for displaying train information
- See [openhab/README.md](openhab/README.md) for installation instructions

**Status Values:**
- `ON_TIME` - Train delay is 2 minutes or less
- `DELAYED` - Train is delayed (delay shown in TrainDelay_Minutes)
- `CANCELLED` - Train is cancelled
- `NOT_FOUND` - No matching train found
- `ERROR` - API error or connection issue

### 4. Test

Test station lookup:
```bash
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux/Mac

python train_tracker.py --test-station "Wien Hbf"
```

Test train lookup:
```bash
python train_tracker.py --verbose
```

The script outputs JSON to stdout and logs to stderr. Example output:
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

### 5. Run

```bash
python train_tracker.py --verbose
```

**For OpenHAB integration:** The script is designed to be called by OpenHAB rules, which parse the JSON output and update items. See [openhab/README.md](openhab/README.md).

## Configuration

### Environment Variables

All configuration can be set via `.env` file or environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ORIGIN_STATION` | Origin station name | `Wien Hbf` |
| `DESTINATION_STATION` | Destination station name | `Salzburg Hbf` |
| `SCHEDULED_TIME` | Scheduled departure time (HH:MM) | `08:15` |
| `MAX_TRAIN_CHANGES` | Maximum train changes allowed (0=direct only) | `0` |

### Command-Line Arguments

Override environment variables with command-line arguments:

```bash
python train_tracker.py \
  --origin "Wien Hbf" \
  --destination "Salzburg Hbf" \
  --time "08:15" \
  --max-changes 0 \
  --verbose
```

**Available Arguments:**
- `--origin` - Origin station name
- `--destination` - Destination station name
- `--time` - Scheduled departure time (HH:MM format)
- `--max-changes` - Maximum number of train changes (0=direct only, 1=one transfer, etc.)
- `--test-station NAME` - Test station lookup and exit (outputs JSON)
- `--verbose` - Enable debug logging (to stderr, JSON still goes to stdout)

## Station Names

Use exact station names as shown on ÖBB:

**Common Austrian Stations:**
- `Wien Hbf` - Vienna Main Station
- `Salzburg Hbf` - Salzburg Main Station
- `Graz Hbf` - Graz Main Station
- `Innsbruck Hbf` - Innsbruck Main Station
- `Linz Hbf` - Linz Main Station
- `Klagenfurt Hbf` - Klagenfurt Main Station
- `Wien Westbahnhof` - Vienna West Station
- `Wien Meidling` - Vienna Meidling Station

**Testing Station Names:**
```bash
python train_tracker.py --test-station "Wien Hbf"
```

## Scheduling

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., Daily at 7:00 AM, repeat every 15 minutes for 4 hours)
4. Action: Start a program
   - Program: `C:\path\to\openhab-train-tracker\venv\Scripts\python.exe`
   - Arguments: `C:\path\to\openhab-train-tracker\train_tracker.py`
   - Start in: `C:\path\to\openhab-train-tracker`

### Linux/Mac Cron

Add to crontab (`crontab -e`):

```bash
# Run every 15 minutes between 7 AM and 11 AM on weekdays
*/15 7-11 * * 1-5 cd /path/to/openhab-train-tracker && ./venv/bin/python train_tracker.py

# Or run at specific times
0 7 * * 1-5 cd /path/to/openhab-train-tracker && ./venv/bin/python train_tracker.py
15 7 * * 1-5 cd /path/to/openhab-train-tracker && ./venv/bin/python train_tracker.py
30 7 * * 1-5 cd /path/to/openhab-train-tracker && ./venv/bin/python train_tracker.py
```

## OpenHAB Integration

The script outputs JSON to stdout, which OpenHAB rules parse to update items. This clean architecture means:
- No OpenHAB credentials needed in Python script
- Script can be tested standalone
- OpenHAB handles all authentication and state management

### Complete OpenHAB Setup

Ready-to-use files are in the [openhab/](openhab/) folder:

1. **trains.items** - Defines all items (TrainDelay_Minutes, TrainStatus_Text, etc.)
2. **trains.rules** - Contains 10 automation rules including:
   - Periodic execution (every 15 min, 6-10 AM, weekdays)
   - JSON parsing and item updates
   - Delay alerts (>5 min)
   - Cancellation alerts
   - Morning summary
3. **trains.sitemap** - UI examples with color-coded status

See [openhab/README.md](openhab/README.md) for installation instructions.

### Quick Example

The OpenHAB rule executes the script and parses JSON:

```java
rule "Update Train Status"
when
    Time cron "0 */15 6-10 ? * MON-FRI"
then
    val results = executeCommandLine(
        Duration.ofSeconds(30),
        "/path/to/venv/bin/python",
        "/path/to/train_tracker.py",
        "--origin", "Wien Hbf",
        "--destination", "Salzburg Hbf",
        "--time", "08:15",
        "--max-changes", "0"
    )

    val status = transform("JSONPATH", "$.status", results)
    val delay = transform("JSONPATH", "$.delay_minutes", results)

    TrainStatus_Text.postUpdate(status)
    TrainDelay_Minutes.postUpdate(Integer::parseInt(delay))
end
```

## Troubleshooting

### Setup Script Issues (Linux/Mac)

**Error:** `./setup.sh: cannot execute: required file not found`

**Cause:** The script has Windows line endings (CRLF) instead of Unix line endings (LF).

**Solution:**
```bash
# Fix line endings
sed -i 's/\r$//' setup.sh

# Make executable
chmod +x setup.sh

# Run normally
./setup.sh
```

Or run directly with bash:
```bash
bash setup.sh
```

**Prevent this issue:** Add a `.gitattributes` file:
```bash
echo "*.sh text eol=lf" > .gitattributes
git add .gitattributes
git commit -m "Ensure Unix line endings for shell scripts"
```

### Station Not Found

**Error:** `Station 'xyz' not found`

**Solution:** Use exact station names. Test with:
```bash
python train_tracker.py --test-station "Wien Hbf"
```

Try variations:
- `Wien Hbf` instead of `Vienna`
- `Salzburg Hbf` instead of `Salzburg`

### No Trains Found

**Error:** Status shows `NOT_FOUND` in JSON output

**Possible causes:**
- No trains running at scheduled time (check ÖBB website)
- Wrong destination name (check spelling)
- Scheduled time is in the past
- Night time (no trains available)
- MAX_TRAIN_CHANGES too restrictive (no direct connections available)

**Solution:** Try with `--verbose` to see detailed logs:
```bash
python train_tracker.py --verbose
```

Try increasing max changes:
```bash
python train_tracker.py --max-changes 1 --verbose
```

### API Connection Issues

**Error:** `Failed to lookup station` or `Failed to get connections`

**Possible causes:**
- No internet connection
- HAFAS API is temporarily unavailable
- Firewall blocking outgoing connections to fahrplan.oebb.at

**Solution:**
- Check internet connection
- Try accessing https://fahrplan.oebb.at in browser
- Check firewall settings (allow HTTPS to fahrplan.oebb.at)
- Wait a few minutes and retry (API may be temporarily down)

### OpenHAB Integration Issues

For OpenHAB-specific troubleshooting (items not updating, rules not executing, etc.), see [openhab/README.md](openhab/README.md#troubleshooting).

## Development

### VS Code Debugging

Debug configuration is available in `.vscode/launch.json`:

1. **Python: Train Tracker** - Run with verbose logging

Press `F5` to start debugging.

### Testing

```bash
# Test station lookup
python train_tracker.py --test-station "Wien Hbf"

# Test with verbose logging
python train_tracker.py --verbose

# Test with different max changes
python train_tracker.py --max-changes 1 --verbose

# Test specific route
python train_tracker.py --origin "Strasshof/Nordbahn" --destination "Wien Praterstern" --time "07:55" --verbose
```

### Project Structure

```
openhab-train-tracker/
├── train_tracker.py       # Main script
├── oebb_profile.py        # Custom ÖBB HAFAS profile
├── requirements.txt       # Python dependencies
├── .env.example           # Configuration template
├── .env                   # Your configuration (not in git)
├── setup.bat              # Windows setup script
├── setup.sh               # Linux/Mac setup script
├── README.md              # This file
├── QUICK_START.md         # Quick setup guide
├── API_SOURCES.md         # API references and documentation
├── .gitattributes         # Git line ending configuration
├── openhab/               # OpenHAB configuration files
│   ├── README.md          # OpenHAB setup instructions
│   ├── trains.items       # Item definitions
│   ├── trains.rules       # Automation rules
│   └── trains.sitemap     # UI examples
└── .vscode/
    └── launch.json        # VS Code debug configurations
```

## API Information

This project uses the **ÖBB HAFAS API** with direct TripSearch calls:

- **API Endpoint**: `https://fahrplan.oebb.at/bin/mgate.exe`
- **Data Source**: ÖBB (Österreichische Bundesbahnen - Austrian Federal Railways)
- **Method**: HAFAS mgate protocol with TripSearch method
- **Authentication**: Uses official ÖBB Android app credentials
- **Library Support**: pyhafas for station lookup, direct API calls for connections

**Features:**
- Station lookup by name (exact matching)
- Connection search with transfer filtering (maxChg parameter)
- Real-time delay information (planned vs actual times)
- Arrival time tracking
- Cancellation detection

**Architecture:**
- Station IDs retrieved via pyhafas `locations()` method
- Connections retrieved via direct HAFAS TripSearch API POST request
- Bypasses pyhafas journey parsing for better control and reliability
- Uses same API as official ÖBB Scotty mobile app

**For detailed API documentation, authentication parameters, and troubleshooting:**
- See [API_SOURCES.md](API_SOURCES.md) for complete API references and technical details

## Additional Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture, design decisions, data flow diagrams
- **[CHANGELOG.md](CHANGELOG.md)** - Version history, migration guide, breaking changes
- **[QUICK_START.md](QUICK_START.md)** - Quick setup guide for getting started in 5 minutes
- **[openhab/README.md](openhab/README.md)** - OpenHAB integration setup and troubleshooting
- **[API_SOURCES.md](API_SOURCES.md)** - HAFAS API documentation and technical references

## License

This project is provided as-is for personal use with OpenHAB.

## Support

For issues or questions:
- Check the Troubleshooting section above
- Review the logs with `--verbose` flag
- Verify configuration in `.env` file
- See [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
