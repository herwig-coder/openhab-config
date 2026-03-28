# OpenHAB Train Tracker - System Architecture

## Overview

This project tracks Austrian train delays using the ÖBB HAFAS API and integrates with OpenHAB for home automation. The architecture follows a clean separation of concerns: the Python script fetches and formats data, while OpenHAB handles all integration, state management, and automation.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ÖBB HAFAS API                                 │
│              https://fahrplan.oebb.at/bin/mgate.exe              │
│          (Same API used by official ÖBB Scotty app)             │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS POST
                              │ (TripSearch method)
                              │
┌─────────────────────────────────────────────────────────────────┐
│              Python Script (train_tracker.py)                    │
│                                                                   │
│  1. Lookup station IDs (Wien Hbf → 1190100)                     │
│  2. Query connections with transfer filtering                   │
│  3. Calculate delay (planned vs actual time)                    │
│  4. Format JSON output to stdout                                │
│  5. Log details to stderr                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ JSON output
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                OpenHAB Rules (trains.rules)                      │
│                                                                   │
│  1. Execute script via executeCommandLine()                     │
│  2. Parse JSON with JSONPATH transformations                    │
│  3. Update OpenHAB items                                        │
│  4. Trigger alerts/automations based on status                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Item updates
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              OpenHAB Items (trains.items)                        │
│                                                                   │
│  • TrainDelay_Minutes (Number)                                  │
│  • TrainStatus_Text (String)                                    │
│  • TrainDeparture_Time (DateTime)                               │
│  • TrainArrival_Time (DateTime)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Display
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            OpenHAB Sitemap (trains.sitemap)                      │
│                                                                   │
│  • Color-coded status display                                   │
│  • Conditional visibility                                       │
│  • Multiple view options                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. JSON-Based Output (Not Direct OpenHAB Updates)

**Why:** Clean separation of concerns, easier testing, no credentials in Python

**Benefits:**
- Script can be tested standalone without OpenHAB
- No OpenHAB credentials needed in Python code
- OpenHAB rules provide better error handling and retry logic
- Easier to debug (JSON is human-readable)
- Script can be used with other systems (not just OpenHAB)

**Implementation:**
```python
# Python outputs JSON to stdout
print(json.dumps({
    "status": "DELAYED",
    "delay_minutes": 12,
    "departure_time": "2026-03-07T08:27:00",
    "arrival_time": "2026-03-07T11:23:00"
}))

# OpenHAB parses JSON
val status = transform("JSONPATH", "$.status", results)
TrainStatus_Text.postUpdate(status)
```

### 2. Direct HAFAS TripSearch API (Not pyhafas journeys())

**Why:** Better control, exact station matching, transfer filtering

**Benefits:**
- Bypasses pyhafas parsing issues (ctxRecon errors)
- Direct access to maxChg parameter (max train changes)
- Exact station matching (no "Bleiburg" confusion)
- More reliable and predictable
- Same API method as official ÖBB Scotty app

**Implementation:**
```python
request_body = {
    "svcReqL": [{
        "meth": "TripSearch",
        "req": {
            "depLocL": [{"type": "S", "extId": origin_id}],
            "arrLocL": [{"type": "S", "extId": destination_id}],
            "outTime": time_str,
            "maxChg": max_changes  # 0=direct, 1=one transfer
        }
    }]
}
```

### 3. Arrival Time Tracking

**Why:** Delays can occur during the trip, not just at departure

**Benefits:**
- More complete delay information
- Users can track if they'll be late to destination
- Better for longer journeys where delays accumulate

**Data Flow:**
```
HAFAS API → departure_time + arrival_time
         → Python JSON output
         → OpenHAB item TrainArrival_Time
         → Sitemap display
```

### 4. Configurable Transfer Count

**Why:** Not all routes have direct connections

**Benefits:**
- Flexible route planning
- Can find connections even when no direct train available
- User controls trade-off between convenience and travel time

**Configuration:**
```bash
# .env file
MAX_TRAIN_CHANGES=0  # Direct only
MAX_TRAIN_CHANGES=1  # Allow one transfer
MAX_TRAIN_CHANGES=2  # Allow two transfers
```

## Data Flow

### 1. Script Execution

```
OpenHAB Rule Trigger (cron: every 15 min, 6-10 AM, Mon-Fri)
         ↓
executeCommandLine(python, train_tracker.py, --origin, --destination, --time, --max-changes)
         ↓
Python script starts with command-line args
```

### 2. API Calls

```
1. Station Lookup (via pyhafas)
   locations("Wien Hbf") → station_id "1190100"

2. Connection Search (direct HAFAS API)
   POST /bin/mgate.exe
   TripSearch method with maxChg parameter
   → List of connections

3. Parse Response
   Extract: departure time, arrival time, delay, cancellation
```

### 3. JSON Output

```python
{
  "success": true,
  "status": "DELAYED",           # ON_TIME, DELAYED, CANCELLED, NOT_FOUND, ERROR
  "delay_minutes": 12,           # Integer
  "planned_time": "08:15",       # HH:MM
  "actual_time": "08:27",        # HH:MM
  "departure_time": "2026-03-07T08:27:00",  # ISO 8601
  "arrival_time": "2026-03-07T11:23:00"     # ISO 8601
}
```

### 4. OpenHAB Processing

```java
// Rule parses JSON
val results = executeCommandLine(...)
val status = transform("JSONPATH", "$.status", results)
val delay = transform("JSONPATH", "$.delay_minutes", results)
val departure = transform("JSONPATH", "$.departure_time", results)
val arrival = transform("JSONPATH", "$.arrival_time", results)

// Update items
TrainStatus_Text.postUpdate(status)
TrainDelay_Minutes.postUpdate(Integer::parseInt(delay))
TrainDeparture_Time.postUpdate(departure)
TrainArrival_Time.postUpdate(arrival)
```

### 5. Automation

```java
// Other rules trigger on item changes
rule "Train Delay Alert"
when
    Item TrainStatus_Text changed to "DELAYED"
then
    val delay = TrainDelay_Minutes.state as Number
    if (delay > 5) {
        sendNotification("Train delayed by " + delay + " minutes!")
    }
end
```

## Component Details

### Python Script (train_tracker.py)

**Responsibilities:**
- Load configuration from .env or command-line args
- Lookup station IDs via HAFAS API
- Query connections via HAFAS TripSearch
- Calculate delay status
- Format and output JSON

**Dependencies:**
- `pyhafas` - For station lookup
- `requests` - For direct HAFAS API calls
- `oebb_profile.py` - Custom HAFAS profile with ÖBB credentials

**Configuration:**
- `ORIGIN_STATION` - Origin station name
- `DESTINATION_STATION` - Destination station name
- `SCHEDULED_TIME` - Scheduled departure time (HH:MM)
- `MAX_TRAIN_CHANGES` - Maximum transfers allowed (0-9)

**Output:** JSON to stdout, logs to stderr

### OpenHAB Items (trains.items)

**Core Items:**
```
Number TrainDelay_Minutes      # 0-999 minutes
String TrainStatus_Text        # ON_TIME, DELAYED, CANCELLED, NOT_FOUND, ERROR
DateTime TrainDeparture_Time   # Actual departure (ISO 8601)
DateTime TrainArrival_Time     # Arrival at destination (ISO 8601)
```

**Optional Items:**
```
DateTime TrainLastUpdate       # Last script execution time
String TrainOrigin             # Origin station name (for display)
String TrainDestination        # Destination station name (for display)
String TrainScheduledTime      # Scheduled time (for display)
```

### OpenHAB Rules (trains.rules)

**10 Pre-Configured Rules:**

1. **Update Train Status** - Periodic execution (every 15 min)
2. **Train Delay Alert** - Alert if delay > 5 minutes
3. **Train Cancelled Alert** - Urgent alert for cancellations
4. **Train Status Changed** - Log all status changes
5. **Morning Train Check** - Run at 6:30 AM with summary
6. **High Delay Warning** - Alert if delay > 30 minutes
7. **Disable Weekend Tracking** - Startup message
8. **Manual Trigger** - Optional manual check switch
9. **Departure Reminder** - Reminder 45 min before departure
10. **Error Detection** - Handle script errors

**Configuration Variables:**
```java
val String SCRIPT_PATH = "/path/to/venv/bin/python"
val String TRACKER_SCRIPT = "/path/to/train_tracker.py"
val String ORIGIN_STATION = "Wien Hbf"
val String DESTINATION_STATION = "Salzburg Hbf"
val String SCHEDULED_TIME = "08:15"
val String MAX_CHANGES = "0"
```

### OpenHAB Sitemap (trains.sitemap)

**Three Variants:**

1. **trains** - Complete view with all details
2. **trains_compact** - Minimal view for dashboards
3. **trains_detailed** - With charts and statistics

**Features:**
- Color-coded status (green/orange/red)
- Conditional visibility (delay shown only when delayed)
- Icons for visual appeal
- Formatted timestamps

## Error Handling

### Python Script

```python
try:
    # API call
    connection = get_direct_connections(...)
except RequestException:
    return {"status": "ERROR", "delay_minutes": 0}
```

**Error States:**
- `ERROR` - API down, network issue, parsing error
- `NOT_FOUND` - No matching train/connection
- `CANCELLED` - Train exists but is cancelled

### OpenHAB Rules

```java
// NULL handling to prevent casting errors
if (TrainDelay_Minutes.state === NULL || TrainDelay_Minutes.state === UNDEF) {
    logWarn("TrainTracker", "Delay value not available yet")
    return
}
val delay = TrainDelay_Minutes.state as Number
```

**Protection:**
- Check for NULL/UNDEF before casting
- Try-catch around JSON parsing
- Timeout on executeCommandLine (30 seconds)
- Graceful degradation (continue if one item update fails)

## Configuration Files

### .env (User Configuration)

```ini
ORIGIN_STATION=Wien Hbf
DESTINATION_STATION=Salzburg Hbf
SCHEDULED_TIME=08:15
MAX_TRAIN_CHANGES=0
```

### oebb_profile.py (HAFAS Configuration)

```python
baseUrl = "https://fahrplan.oebb.at/bin/mgate.exe"
salt = '5DBkaU5t'
addChecksum = True
requestBody = {
    'lang': 'deu',
    'client': {'id': 'OEBB', 'v': '6140000', 'type': 'AND'},
    'auth': {'type': 'AID', 'aid': 'OWDL4fE4ixNiPBBm'}
}
```

## Testing Strategy

### 1. Station Lookup Test

```bash
python train_tracker.py --test-station "Wien Hbf"
# Outputs: {"success": true, "station_id": "1190100"}
```

### 2. Standalone Test

```bash
python train_tracker.py --verbose
# Outputs JSON to stdout, logs to stderr
```

### 3. OpenHAB Integration Test

```bash
# Check OpenHAB logs
tail -f /var/log/openhab/openhab.log | grep TrainTracker

# Manually trigger rule via Karaf console
openhab> openhab:send CheckTrainNow ON
```

### 4. End-to-End Test

1. Run script manually → verify JSON
2. Check OpenHAB logs → verify rule execution
3. Check item states → verify values updated
4. Check sitemap → verify display

## Deployment

### Initial Setup

1. Clone repository
2. Run setup script (creates venv, installs dependencies)
3. Edit `.env` with route configuration
4. Test script standalone

### OpenHAB Integration

1. Copy `trains.items` to `conf/items/`
2. Copy `trains.rules` to `conf/rules/` and update paths
3. Copy `trains.sitemap` to `conf/sitemaps/` (optional)
4. Restart OpenHAB
5. Check logs for successful execution

### Verification

```bash
# Check OpenHAB logs
tail -f /var/log/openhab/openhab.log | grep TrainTracker

# Check item states
openhab> openhab:status TrainStatus_Text
openhab> openhab:status TrainDelay_Minutes
```

## Maintenance

### Updating Configuration

**Change route:**
Edit `ORIGIN_STATION`, `DESTINATION_STATION`, `SCHEDULED_TIME` in `trains.rules`

**Change schedule:**
Edit cron expression in Rule 1: `Time cron "0 */15 6-10 ? * MON-FRI"`

**Add notifications:**
Uncomment `sendNotification()` or `sendTelegram()` lines in rules

### API Changes

If HAFAS API changes:
1. Check [API_SOURCES.md](API_SOURCES.md) for version info
2. Update `oebb_profile.py` if needed
3. Update API version in requestBody

### Troubleshooting

**Script fails:**
- Check logs with `--verbose`
- Test station lookup with `--test-station`
- Verify internet connection

**OpenHAB items not updating:**
- Check rule execution in logs
- Verify script paths in rules
- Test JSONPATH transformations
- Check for NULL state errors

## Future Enhancements

### Potential Additions

1. **Multiple Routes** - Track morning and evening commutes separately
2. **Historical Data** - Persistence and charts via InfluxDB
3. **Smart Notifications** - Only alert on significant delays
4. **Alternative Routes** - Suggest alternatives when train is cancelled
5. **Weather Integration** - Combine with weather for departure planning

### Extensibility

The JSON-based architecture makes it easy to:
- Use output with other home automation systems
- Parse data in custom scripts
- Store in databases for analytics
- Display in mobile apps or web dashboards

## Summary

This architecture provides:

✅ **Clean separation** - Python fetches, OpenHAB integrates
✅ **No credentials** - No OpenHAB tokens in Python
✅ **Easy testing** - Script outputs JSON, can be tested standalone
✅ **Reliable** - Direct HAFAS API, same as official app
✅ **Flexible** - Configurable transfers, multiple routes
✅ **Complete** - Tracks both departure and arrival times
✅ **Automated** - OpenHAB schedules and manages execution
✅ **Extensible** - JSON output works with any system

The result is a robust, maintainable train tracking system that seamlessly integrates with OpenHAB for home automation.
