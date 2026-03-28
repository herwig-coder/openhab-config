# Changelog - OpenHAB Train Tracker

## [2.0.0] - 2026-03-07

### Major Architecture Changes

**Complete system redesign** from direct OpenHAB integration to clean JSON-based architecture.

#### Core Changes

**Python Script (train_tracker.py):**
- ✅ **Removed:** All OpenHAB HTTP client code and direct item updates
- ✅ **Removed:** Unused `get_next_departure_with_stops()` method (152 lines)
- ✅ **Changed:** Output JSON to stdout instead of updating OpenHAB
- ✅ **Changed:** Send logs to stderr (not stdout) for clean JSON output
- ✅ **Added:** Arrival time tracking in all responses
- ✅ **Added:** `--max-changes` parameter for configurable transfer limits
- ✅ **Added:** Direct HAFAS TripSearch API implementation (bypasses pyhafas parsing)
- ✅ **Added:** Support for both timestamp formats (14-char and 6-char HAFAS times)
- ✅ **Added:** Proper delay handling for both timedelta and integer types
- ✅ **Fixed:** Station matching now uses exact IDs (no more "Bleiburg" confusion)
- ✅ **Fixed:** Connection search uses TripSearch API (like Scotty webapp)

**OpenHAB Integration:**
- ✅ **Moved:** All OpenHAB integration logic to rules (trains.rules)
- ✅ **Added:** JSON parsing with JSONPATH transformations in rules
- ✅ **Added:** MAX_CHANGES configuration variable in rules
- ✅ **Added:** TrainArrival_Time item and updates
- ✅ **Added:** Comprehensive NULL/UNDEF state handling in all rules
- ✅ **Updated:** All 10 rules to use executeCommandLine + JSONPATH
- ✅ **Updated:** Script execution includes --max-changes parameter

### New Features

1. **Arrival Time Tracking**
   - Added `arrival_time` to JSON output
   - Added `TrainArrival_Time` OpenHAB item
   - Updated all rules to parse and set arrival time
   - Updated sitemap to display arrival time

2. **Configurable Transfer Limits**
   - Added `MAX_TRAIN_CHANGES` environment variable
   - Added `--max-changes` command-line argument
   - Added MAX_CHANGES configuration in OpenHAB rules
   - Enables finding connections with 0-N transfers

3. **Clean JSON Architecture**
   - Python outputs structured JSON to stdout
   - OpenHAB rules parse JSON and update items
   - No credentials needed in Python script
   - Easier testing and debugging

4. **Direct HAFAS TripSearch**
   - Bypasses pyhafas journey parsing issues
   - Direct API access to maxChg parameter
   - Exact station matching by ID
   - More reliable than previous approach

### Documentation Updates

**README.md:**
- ✅ Updated "How It Works" to reflect HAFAS TripSearch architecture
- ✅ Removed all references to OpenHAB tokens/credentials
- ✅ Updated configuration section (removed token, added MAX_TRAIN_CHANGES)
- ✅ Added TrainArrival_Time to items list
- ✅ Updated command-line arguments (removed dry-run, added max-changes)
- ✅ Updated test examples with JSON output
- ✅ Updated OpenHAB integration section (rules-based approach)
- ✅ Updated troubleshooting (removed token issues, added max-changes help)
- ✅ Updated API Information section (HAFAS TripSearch details)

**openhab/README.md:**
- ✅ Added TrainArrival_Time to items configuration
- ✅ Added MAX_CHANGES to configuration variables
- ✅ Updated rules description (JSON parsing, JSONPATH)
- ✅ Updated multiple routes example with JSON parsing
- ✅ Updated troubleshooting (removed token, added JSON parsing)

**QUICK_START.md:**
- ✅ Complete rewrite for JSON-based architecture
- ✅ Removed OpenHAB token requirements
- ✅ Updated configuration examples
- ✅ Added JSON output examples
- ✅ Updated test section with actual JSON responses
- ✅ Added arrival time to examples
- ✅ Updated scheduling section (OpenHAB rules vs standalone)
- ✅ Updated troubleshooting for new architecture

**New Documentation:**
- ✅ **ARCHITECTURE.md** - Complete system architecture documentation
- ✅ **CHANGELOG.md** - This file

**Other Files:**
- ✅ Updated `.vscode/launch.json` (removed dry-run, added test-station config)
- ✅ Updated `.env.example` with MAX_TRAIN_CHANGES parameter

### Code Cleanup

**Removed:**
- 152 lines of unused `get_next_departure_with_stops()` method
- All OpenHAB HTTP client code (60+ lines)
- All direct item update logic (40+ lines)
- Dry-run functionality (no longer needed)
- Test-departure flag (no longer needed)

**Result:** ~250 lines of code removed, cleaner and more maintainable

### Bug Fixes

1. **Station Matching**
   - Fixed: "Bleiburg" matching multiple wrong stations
   - Solution: Direct TripSearch API with exact station IDs

2. **Connection Search**
   - Fixed: Found trains going in wrong direction
   - Solution: TripSearch API with proper origin/destination

3. **Transfer Counting**
   - Fixed: No way to filter by number of transfers
   - Solution: maxChg parameter in TripSearch API

4. **Timestamp Parsing**
   - Fixed: "time data '170200' does not match format" error
   - Solution: Support both 14-char and 6-char HAFAS timestamps

5. **Delay Type Handling**
   - Fixed: "unsupported type for timedelta" error
   - Solution: Handle both timedelta and integer delay values

6. **NULL State Errors**
   - Fixed: "Could not cast NULL to java.lang.Number" in OpenHAB
   - Solution: NULL checks before casting in all rules

### Migration Guide

**For existing users:**

1. **Update .env file:**
   ```diff
   - OPENHAB_URL=http://localhost:8080
   - OPENHAB_TOKEN=oh.mytoken...
   - OPENHAB_DELAY_ITEM=TrainDelay_Minutes
   - OPENHAB_STATUS_ITEM=TrainStatus_Text
   - OPENHAB_DEPARTURE_ITEM=TrainDeparture_Time
   + MAX_TRAIN_CHANGES=0
   ```

2. **Update OpenHAB items:**
   ```
   + DateTime TrainArrival_Time "Arrival Time [%1$tH:%1$tM]" <calendar>
   ```

3. **Replace trains.rules:**
   - Copy new trains.rules from openhab/ folder
   - Update SCRIPT_PATH and TRACKER_SCRIPT variables
   - Update ORIGIN_STATION, DESTINATION_STATION, SCHEDULED_TIME
   - Add MAX_CHANGES="0" configuration

4. **Test:**
   ```bash
   # Test standalone (should output JSON)
   python train_tracker.py --verbose

   # Check OpenHAB logs
   tail -f /var/log/openhab/openhab.log | grep TrainTracker
   ```

### Breaking Changes

⚠️ **These changes are not backwards compatible with v1.x:**

1. Script no longer updates OpenHAB directly
2. Removed command-line arguments: `--url`, `--token`, `--delay-item`, `--status-item`, `--departure-item`, `--dry-run`, `--test-departure`
3. Script now outputs JSON instead of formatted text reports
4. OpenHAB rules must be updated to use executeCommandLine + JSONPATH
5. .env file format changed (removed OpenHAB config, added MAX_TRAIN_CHANGES)

### Performance Improvements

- ✅ Faster API calls (direct HAFAS TripSearch vs multiple departures queries)
- ✅ Reduced network traffic (single API call instead of multiple)
- ✅ Better error handling (graceful degradation in rules)

### Known Issues

None at this time.

### Dependencies

**No changes:**
- pyhafas>=0.4.0
- requests>=2.31.0

**Still using:**
- Python 3.8+
- OpenHAB 3.x or 4.x (for integration only)

### Testing

All tests passing:
- ✅ Station lookup test
- ✅ JSON output test
- ✅ HAFAS TripSearch API test
- ✅ OpenHAB rules execution test
- ✅ NULL state handling test
- ✅ Arrival time tracking test
- ✅ Max changes parameter test

### Credits

**API Source:**
- ÖBB HAFAS API (fahrplan.oebb.at/bin/mgate.exe)
- pyhafas library by n0emis

**Architecture:**
- Clean separation of concerns
- JSON-based integration pattern
- Inspired by Unix philosophy (do one thing well)

---

## [1.0.0] - 2026-03-06

### Initial Release

- Basic train delay tracking
- Direct OpenHAB integration
- Station lookup via pyhafas
- Departure tracking with pyhafas journeys()
- Environment-based configuration
- Windows and Linux support

---

**Legend:**
- ✅ Completed
- ⚠️ Breaking change
- 🐛 Bug fix
- ✨ New feature
- 📝 Documentation
- 🔧 Maintenance
