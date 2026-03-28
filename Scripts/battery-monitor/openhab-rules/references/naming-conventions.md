# Naming Conventions

Clear, consistent naming makes OpenHAB configs maintainable and debuggable.

---

## Item Naming

### Physical Device Items (Location-Based)

**Pattern**: `Location_Property` or `Location_Device_Property`

```
✅ GOOD - Location-based physical items
Bathroom_Temperature            "Bad Temperatur"
Bathroom_Humidity               "Bad Luftfeuchte"
Bathroom_Sensor_Battery         "Bad Batterie"
ParentsBedroom_Temperature      "Eltern Schlafzimmer Temperatur"
ParentsBedroom_DewPoint_Alert   "Eltern Schlafzimmer Taupunkt Alarm"
OfficeSmall_Temperature         "Büro Herwig Temperatur"
OfficeSmall_Sensor_Battery      "Büro Herwig Batterie"
```

**Benefits:**
- Groups related sensors by location
- Autocomplete shows all bathroom items together
- Easy to find items in rules
- Semantic model compatibility

**Format**: PascalCase with underscores separating hierarchy levels

### Device-Prefixed Items

**Pattern**: `DeviceType_Instance_Function`

```
✅ GOOD - Device-based items
Ulanzi_01_settings              "Ulanzi Settings"
Ulanzi_01_train                 "Ulanzi Zug"
Ulanzi_01_muell                 "Ulanzi Müllbenachrichtigung"
Gosund_02_Power_consumption     "Gosund Power Consumption"
Weatherstation_Temperature_1    "Wetterstation Aussentemperatur"
```

**Use when:**
- Multiple instances of same device type (`_01`, `_02`)
- Device has multiple functions/channels
- Location less relevant than device type

### Virtual/Calculated Items

**Pattern**: camelCase (preferred) or lowercase

```
✅ GOOD - Consistent virtual items
lastWash                        "Letztes mal gewaschen"
currentPrice                    "Current Price"
totalPrice                      "Strompreis"

⚠️ INCONSISTENT - Mixed styles (avoid)
lastWash                        // camelCase
currentnet                      // lowercase
totalprice                      // lowercase
NextCollectionDate              // PascalCase
```

**Recommendation**: Use **camelCase** for virtual items to distinguish from physical items.

Physical items (with underscores):
- `Bathroom_Temperature` → sensor reading
- `ParentsBedroom_DewPoint` → calculated from sensor

Virtual items (camelCase):
- `lastWash` → stored timestamp
- `currentPrice` → calculated value
- `totalCost` → aggregated value

### Collection/Array Items

**Pattern**: BaseName + zero-padded number (for ordering) or descriptive suffix

```
✅ GOOD - Numbered collections
NextCollectionDate              "Next Collection Date"
NextCollectionDate1             "Next Collection Date 1"
NextCollectionDate2             "Next Collection Date 2"

Item0_Collection                "Collection Item 0"
Item1_Collection                "Collection Item 1"
Item2_Collection                "Collection Item 2"

today00                         "Electricity Today 00-01"
today01                         "Electricity Today 01-02"
today23                         "Electricity Today 23-00"

❌ AVOID - Mixed numbering
NextCollectionDate              // No number
NextCollectionDate1             // Starts at 1
NextCollectionDate2

✅ BETTER - Consistent numbering
NextCollectionDate0             // Starts at 0
NextCollectionDate1
NextCollectionDate2
```

**When using zero-padding**:
- Use `today00`, `today01` not `today0`, `today1` (keeps alphabetical order)
- Helps with loops and dynamic item name construction

### Group Names

**Pattern**: `g` + descriptive name in PascalCase with underscores

```
✅ GOOD - Group naming
gBathroom                       "Bathroom"
gBLE_Sensor_Bathroom            "BLE Sensor Bad"
gBLE_Sensor_ParentsBedroom      "BLE Sensor Eltern Schlafzimmer"
gBattery                        "Battery Items"
gStrasshof                      "Strasshof Location"
```

**Prefix convention:**
- `g` = Group
- Immediately followed by descriptive name
- Uses same PascalCase_Underscore pattern as items

---

## Rule Naming

### Recommended: Descriptive with underscores

**Pattern**: `domain_subdomain_action` (lowercase with underscores)

```
✅ GOOD - Clear, readable rule names
bathroom_airing
bathroom_airing_done
bathroom_airing_button
bathroom_airing_motor_off
ulanzi_train_check_on
ulanzi_train_check_off
ulanzi_airing
```

**Benefits:**
- Easy to read in logs
- Groups related rules alphabetically
- Clear hierarchy (domain → subdomain → action)

### Alternative: camelCase

**Pattern**: `domainSubdomainAction` (camelCase)

```
✅ GOOD - camelCase alternative
dewpointBad
dewpointBadAlert
dewpointBedroomAlert
dewpointOfficeSmall
```

**Benefits:**
- Compact
- Common in programming
- Works well for shorter names

### Alternative: PascalCase

**Pattern**: `DomainSubdomainAction` (PascalCase)

```
✅ GOOD - PascalCase alternative
WashingTime
WashHangTime
WashResetLast
WashingBedsheets
UpdateMatrixMessage
```

**Benefits:**
- Matches item naming style
- Clear word boundaries

### Avoid: Mixed conventions in same file

```
❌ INCONSISTENT - Different styles in same domain
rule "dewpointBadAlert"         // camelCase
rule "ulanzi_airing"            // lowercase_underscore
rule "WashingTime"              // PascalCase
rule "Ambient Light"            // With spaces
```

**Pick ONE style per domain** and stick with it.

### Rule Names with Spaces

```
⚠️ USE SPARINGLY - Spaces in rule names
rule "Ambient Light"
rule "Lights off at Midnight"
rule "Aquarium on"
rule "Bewegung Gartenhaus Passage"
```

**When acceptable:**
- Simple, short names (2-3 words)
- Natural language descriptions
- Non-technical users editing rules

**When to avoid:**
- Complex automations (use underscores/camelCase)
- Technical/system rules
- Rules referenced programmatically

---

## File Naming

### Item Files

**Pattern**: Lowercase or PascalCase, group by domain/device type

```
✅ GOOD - Consistent lowercase
washing.items
trains.items
astro.items
shelly.items

✅ GOOD - Consistent PascalCase
GarbageCalendar.items
Gosund.items
Smartmeter.items
Weatherstation.items
Ulanzi.items

⚠️ MIXED - Inconsistent (current state)
washing.items               // lowercase
GarbageCalender.items       // PascalCase
BLE_Sensors.items          // PascalCase with underscore
reolink_cameras.items      // lowercase with underscore
```

**Recommendation**:
- **Lowercase** for common/generic domains (`washing.items`, `lights.items`)
- **PascalCase** for specific device types/brands (`Ulanzi.items`, `Gosund.items`)
- Be consistent within your config

### Rule Files

**Pattern**: Lowercase, match domain, use underscores for multi-word

```
✅ GOOD - Descriptive, lowercase rule files
washing.rules
trains.rules
lights.rules
shelly.rules
dewpoint.rules
bathroomAiring.rules            // camelCase acceptable
senddewpointalert.rules         // no underscore separators
ulanzimessages.rules
```

**Match items to rules:**
```
washing.items       ←→ washing.rules
trains.items        ←→ trains.rules
Ulanzi.items        ←→ ulanzimessages.rules (considers Ulanzi messages)
BLE_Sensors.items   ←→ dewpoint.rules (uses BLE sensor data)
```

File names don't need perfect alignment, but related functionality should be obvious.

---

## Variable Naming (in Rules)

### File-level Variables

**Pattern**: camelCase for timers, lowercase for primitives, descriptive names

```xtend
// ✅ GOOD - Clear variable names
var Timer bathingTimer = null
var Timer airingTimer = null
var String blindPriority = "idle"
var int blindPrioLevel = 0
```

### Local Variables

**Pattern**: Short, descriptive camelCase

```xtend
// ✅ GOOD - Local variables
val temp = (Bathroom_Temperature.state as QuantityType<Number>).doubleValue
val outtemp = (Weatherstation_Temperature_1.state as QuantityType<Number>).doubleValue
val message = "Temperature: " + String.format("%.1f", temp)
val telegramAction = getActions("telegram", "telegram:telegramBot:Telegram_Bot")

// ✅ GOOD - Descriptive for complex values
val collectionDate = (NextCollectionDate.state as DateTimeType).getZonedDateTime(ZoneId.systemDefault())
val timeUntilCollection = Duration.between(currenttime, collectionDate)
```

**Avoid:**
```xtend
// ❌ UNCLEAR - Single letters, abbreviations
val t = item.state
val msg = "test"
val ta = getActions("telegram", "bot")
```

---

## Log Names

**Pattern**: Match rule file name, short, no spaces

```xtend
// ✅ GOOD - Log name matches domain/file
logInfo("washing", "Machine started")
logInfo("dewpoint", "Alert triggered")
logInfo("ulanzi", "Message sent")
logWarn("bathroom", "Sensor offline")

// ❌ AVOID - Long, generic names
logInfo("BathroomDewpointAlertRule", "Alert sent")
logInfo("rule", "Something happened")
```

**Benefits:**
- Filterable in logs: `grep "washing" openhab.log`
- Groups related log entries
- Easy to identify source

---

## Consistency Checklist

When adding new items/rules/files:

**Items:**
- [ ] Physical items: `Location_Property` pattern
- [ ] Device items: `Device_Instance_Function` pattern
- [ ] Virtual items: camelCase consistently
- [ ] Groups: `g` prefix
- [ ] Collections: consistent numbering (zero-padded if needed)

**Rules:**
- [ ] Pick ONE naming style per domain (underscore/camelCase/PascalCase)
- [ ] Name matches functionality clearly
- [ ] Avoid spaces unless simple/natural language

**Files:**
- [ ] Pick ONE style (lowercase vs PascalCase)
- [ ] Match related items file if exists
- [ ] Use `.items` / `.rules` extensions

**Variables & Logs:**
- [ ] camelCase for readability
- [ ] Short log names matching domain
- [ ] Descriptive, not abbreviated

---

## Migration Strategy

**Don't rename everything at once** — it breaks references and requires massive testing.

**Instead:**
1. **Document current state** (you have mixed styles — that's OK for now)
2. **Pick target conventions** for new items/rules
3. **Apply to new additions** going forward
4. **Gradually refactor** old items when touching related code

**Priority order:**
1. Fix inconsistencies within same domain (e.g., all washing rules → same style)
2. Standardize new additions
3. Eventually refactor major domains as needed

---

## Quick Reference

| Type | Pattern | Example |
|------|---------|---------|
| Physical item | `Location_Property` | `Bathroom_Temperature` |
| Device item | `Device_Instance_Function` | `Ulanzi_01_train` |
| Virtual item | camelCase | `lastWash`, `currentPrice` |
| Group | `g` + PascalCase | `gBathroom`, `gBLE_Sensor_Bathroom` |
| Rule | lowercase_with_underscores | `bathroom_airing_done` |
| Rule (alt) | camelCase | `dewpointBadAlert` |
| File | lowercase or PascalCase | `washing.items`, `Ulanzi.items` |
| Variable | camelCase | `bathingTimer`, `telegramAction` |
| Log name | Short, no spaces | `"washing"`, `"dewpoint"` |
