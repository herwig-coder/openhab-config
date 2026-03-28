# Common OpenHAB DSL Patterns

Frequently-used patterns extracted from production rules. Reference these when writing new rules.

---

## Cron Expressions

Schedule rules using `Time cron "expression"` trigger.

### Syntax: `"seconds minutes hours dayOfMonth month dayOfWeek year"`

| Field | Values | Special |
|-------|--------|---------|
| seconds | 0-59 | |
| minutes | 0-59 | `*/15` = every 15 min |
| hours | 0-23 | |
| dayOfMonth | 1-31 | `?` = no specific value |
| month | 1-12 or JAN-DEC | |
| dayOfWeek | 1-7 or SUN-SAT | `MON-FRI` = weekdays |
| year | (optional) | `*` = every year |

### Common Patterns

```xtend
// Every day at 7:20 AM on weekdays
Time cron "0 20 7 ? * MON-FRI *"

// Every 10 minutes
Time cron "0 /10 * * * ?"

// Every 15 minutes during specific hours (6-10 AM weekdays)
Time cron "0 */15 6-10 ? * MON-FRI"

// Twice daily at specific times
Time cron "0 0 7,13 * * *"

// Every hour on the hour
Time cron "0 * * ? * *"

// Daily at midnight
Time cron "0 00 00 * * *"

// 2nd and 4th Friday of every month at 8:20 AM
Time cron "0 20 8 ? 1/1 FRI#2 * " or
Time cron "0 20 8 ? 1/1 FRI#4 * "

// Every hour and 1 second (offset to avoid conflicts)
Time cron "1 0 * ? * * *"
```

### Multiple Triggers

```xtend
rule "Combined Triggers"
when
    Item MyItem changed or
    Time cron "0 20 7 ? * MON-FRI *"
then
    // Runs on item change OR on schedule
end
```

---

## DateTime & Duration Handling

Work with timestamps and calculate time differences.

### Basic DateTime Pattern

```xtend
rule "Check Last Action Time"
when
    Time cron "0 20 7 * * ?"
then
    // NULL guard
    if (lastWash.state == NULL || lastWash.state == UNDEF) return;

    if (lastWash.state instanceof DateTimeType) {
        // Get datetime from item
        val ZonedDateTime last = (lastWash.state as DateTimeType).getInstant.atZone(ZoneId.systemDefault())
        val ZonedDateTime now = ZonedDateTime.now()

        // Calculate duration
        val long days = java.time.Duration.between(last, now).toDays()

        if (days >= 2) {
            logInfo("Check", "Last action was {} days ago", days)
            // Take action
        }
    }
end
```

### Duration Units

```xtend
val long seconds = java.time.Duration.between(last, now).seconds
val long minutes = java.time.Duration.between(last, now).toMinutes()
val long hours = java.time.Duration.between(last, now).toHours()
val long days = java.time.Duration.between(last, now).toDays()
```

### Time Window Pattern

```xtend
// Check if event happened within specific window
if ((minutes >= 10) && (minutes < 20)) {
    // Between 10-20 minutes ago
}
```

### Update DateTime Item

```xtend
// Update item to current time
lastWash.postUpdate(now.toLocalDateTime.toString())
```

### Date Comparison

```xtend
val currenttime = now
val collectiondate = (NextCollectionDate.state as DateTimeType).getZonedDateTime(ZoneId.systemDefault())

if (currenttime.toLocalDate == collectiondate.toLocalDate) {
    // Same day
    message = "Heute: "
} else {
    // Different day
    message = "Morgen: "
}
```

---

## QuantityType & Unit Conversions

Work with measurements (temperature, power, etc.) and convert units.

### Temperature Conversion

```xtend
rule "Process Temperature"
when
    Item Bathroom_DewPoint changed
then
    // NULL guards - CRITICAL
    if (Bathroom_DewPoint.state == NULL || Bathroom_DewPoint.state == UNDEF) {
        logWarn("Rule", "Bathroom_DewPoint is NULL/UNDEF")
        return;
    }

    if (Bathroom_DewPoint.state instanceof QuantityType) {
        val temp = (Bathroom_DewPoint.state as QuantityType<Number>).toUnit("°C").doubleValue

        if (temp > 18.3) {
            logInfo("Rule", "Temperature: {} °C", temp)
        }
    }
end
```

### Power Monitoring

```xtend
rule "Monitor Power Consumption"
when
    Item Gosund_02_Power_consumption changed
then
    // NULL guard
    if (Gosund_02_Power_consumption.state == NULL || Gosund_02_Power_consumption.state == UNDEF) return;

    val power = (Gosund_02_Power_consumption.state as QuantityType<Number>).toUnit("kW").doubleValue

    if (power > 0.01) {
        // Device is running
        lastWash.postUpdate(now.toLocalDateTime.toString())
        logInfo("Power", "Device started, power: {} kW", power)
    }
end
```

### Common Units

| Type | Units | Example |
|------|-------|---------|
| Temperature | `"°C"`, `"°F"` | `toUnit("°C")` |
| Power | `"W"`, `"kW"` | `toUnit("kW")` |
| Voltage | `"V"` | `toUnit("V")` |
| Current | `"A"` | `toUnit("A")` |
| Energy | `"Wh"`, `"kWh"` | `toUnit("kWh")` |

### Price Calculations with QuantityType

```xtend
// NULL guard first
if (currentnet.state == NULL || currentnet.state == UNDEF) {
    logWarn("Price", "currentnet is NULL/UNDEF")
    return;
}

val netprice = (currentnet.state as QuantityType<Number>).doubleValue
val grossprice = (netprice * 1.03 + 1.5 + 8.2) * 1.2
totalprice.postUpdate(grossprice)
```

---

## State-Based Deduplication

Prevent notification spam by tracking alert state.

### Pattern: Alert ON/OFF with Deduplication

```xtend
rule "Dewpoint Alert"
when
    Item Bathroom_DewPoint changed
then
    // NULL guards
    if (Bathroom_DewPoint.state == NULL || Bathroom_DewPoint.state == UNDEF) return;

    val temp = (Bathroom_DewPoint.state as QuantityType<Number>).toUnit("°C").doubleValue

    if (temp > 18.3) {
        // Alert condition met
        val telegramAction = getActions("telegram", "telegram:telegramBot:Telegram_Bot")
        val message = "ALERT! Time to air. Dewpoint at: " + String.format("%.1f", temp) + " °C"

        // Only send if not already alerted
        if (Bathroom_DewPoint_Alert.state != ON) {
            telegramAction.sendTelegram(message)
            logInfo("Alert", "Alert sent: {}", message)
            Bathroom_DewPoint_Alert.postUpdate(ON)
        } else {
            logInfo("Alert", "Alert already active, skipping")
        }
    } else {
        // Alert condition cleared
        if (Bathroom_DewPoint_Alert.state == ON) {
            val telegramAction = getActions("telegram", "telegram:telegramBot:Telegram_Bot")
            val message = "Bathroom: aired enough. Dewpoint at: " + String.format("%.1f", temp) + " °C"

            telegramAction.sendTelegram(message)
            logInfo("Alert", "Alert cleared: {}", message)
            Bathroom_DewPoint_Alert.postUpdate(OFF)
        }
    }
end
```

### Required Items

```
Switch Bathroom_DewPoint_Alert  "Bathroom Dewpoint Alert State"
```

### Benefits
- Prevents duplicate notifications
- State persists across rule evaluations
- Clear alert lifecycle (ON → OFF)

---

## Power Monitoring Pattern

Detect when appliances start/stop based on power consumption.

### Complete Pattern

```xtend
rule "Detect Washing Machine Start"
when
    Item Gosund_02_Power_consumption changed
then
    // NULL guard
    if (Gosund_02_Power_consumption.state == NULL || Gosund_02_Power_consumption.state == UNDEF) return;

    val power = (Gosund_02_Power_consumption.state as QuantityType<Number>).toUnit("kW").doubleValue
    logInfo("Power", "Power consumption: {} kW", power)

    if (power > 0.01) {
        // Machine started, record timestamp
        lastWash.postUpdate(now.toLocalDateTime.toString())
        logInfo("Power", "Washing machine started")
    }
end

rule "Check Machine Runtime"
when
    Time cron "0 /10 * * * ?"  // Every 10 minutes
then
    // NULL guard
    if (lastWash.state == NULL || lastWash.state == UNDEF) return;

    if (lastWash.state instanceof DateTimeType) {
        val ZonedDateTime last = (lastWash.state as DateTimeType).getInstant.atZone(ZoneId.systemDefault())
        val ZonedDateTime now = ZonedDateTime.now()
        val long minutes = java.time.Duration.between(last, now).toMinutes()

        if ((minutes >= 10) && (minutes < 20)) {
            // Machine has been running 10-20 minutes
            val telegramAction = getActions("telegram", "telegram:telegramBot:TelegramWashbot_Bot")
            telegramAction.sendTelegram("The wash is ready to hang.")
        }
    }
end
```

### Use Cases
- Washing machine completion detection
- Dishwasher cycle monitoring
- Dryer runtime tracking
- Any appliance with power metering

---

## String Formatting

Format numbers and dates for display in messages.

### Number Formatting

```xtend
// Format decimal with 1 digit after decimal point
val message = "Temperature: " + String.format("%.1f", temp) + " °C"

// Format with 2 digits
val message = "Price: " + String.format("%.2f", price) + " ct/kWh"

// Result: "Temperature: 18.3 °C"
// Result: "Price: 24.50 ct/kWh"
```

### Date Formatting (German Locale)

```xtend
// Format: "Do 12.03" (Thu 12.03)
val message = String.format(java.util.Locale.GERMAN, "%ta %1$td.%1$tm", collectiondate.toLocalDate()) + ": "
```

### Time Formatting

```xtend
// Format time with leading zeros: "07:20"
val message = String.format("Zug %02d:%02d on time.", departuretime.getHour(), departuretime.getMinute())

// Include variable in formatted string
val message = String.format("Zug %02d:%02d is %d min late.", hour, minute, delayMinutes)
```

### Format Specifiers

| Specifier | Meaning | Example |
|-----------|---------|---------|
| `%d` | Integer | `42` |
| `%02d` | Integer, 2 digits, zero-padded | `07` |
| `%.1f` | Float, 1 decimal place | `18.3` |
| `%.2f` | Float, 2 decimal places | `24.50` |
| `%ta` | Short weekday name (locale) | `Do` (Thu) |
| `%1$td` | Day of month | `12` |
| `%1$tm` | Month number | `03` |

---

## instanceof + NULL Guards

Understand the relationship between NULL guards and type checks.

### Pattern: NULL Guards First, Then Type Check

```xtend
rule "Safe Type Checking"
when
    Item MyItem changed
then
    // STEP 1: NULL guard - prevents crashes
    if (MyItem.state == NULL || MyItem.state == UNDEF) {
        logWarn("Rule", "MyItem is NULL/UNDEF, skipping")
        return;
    }

    // STEP 2: Type check - ensures correct type before casting
    if (MyItem.state instanceof QuantityType) {
        // Safe to cast now
        val temp = (MyItem.state as QuantityType<Number>).toUnit("°C").doubleValue

        // Use the value
        logInfo("Rule", "Temperature: {} °C", temp)
    } else {
        logWarn("Rule", "MyItem is not a QuantityType")
    }
end
```

### Why Both?

| Check | Purpose | What It Prevents |
|-------|---------|------------------|
| NULL guard | Ensures state exists | Crash when accessing NULL state |
| instanceof | Ensures correct type | Crash when casting wrong type |

### Common Mistake

```xtend
// ❌ WRONG: instanceof alone doesn't prevent NULL crash
if (MyItem.state instanceof QuantityType) {
    val temp = (MyItem.state as QuantityType<Number>).doubleValue  // Can still crash if NULL
}

// ✅ CORRECT: NULL guard first
if (MyItem.state == NULL || MyItem.state == UNDEF) return;
if (MyItem.state instanceof QuantityType) {
    val temp = (MyItem.state as QuantityType<Number>).doubleValue  // Safe
}
```

### When to Use Each

**Always use NULL guards** before:
- Casting: `(item.state as QuantityType<Number>)`
- Calling methods: `item.state.toString()`
- Comparing: `item.state == "value"`

**Use instanceof** when:
- Item can have multiple types (Number, String, etc.)
- You need to handle different types differently
- You want extra type safety before casting

---

## Rule File Organization

Best practices for organizing rules into files.

### Organization by Domain

```
rules/
├── ulanzimessages.rules          # Ulanzi/Awtrix display rules
├── senddewpointalert.rules       # Dewpoint monitoring & alerts
├── washing.rules                  # Washing machine automation
├── trains.rules                   # Train schedule monitoring
├── bathroomAiring.rules          # Bathroom ventilation
├── lights.rules                   # Lighting automation
└── shelly.rules                   # Shelly device rules
```

### Benefits of Separation

| Benefit | Example |
|---------|---------|
| **Easier debugging** | All Telegram alerts in one file → easy to review notification logic |
| **Independent deployment** | Update train rules without touching lighting |
| **Clear ownership** | Each file has focused responsibility |
| **Better version control** | Smaller, focused diffs in commits |

### Naming Convention

```
<domain>_<optional-subdomain>.rules

Examples:
- ulanzi_messages.rules          # Domain: ulanzi, subdomain: messages
- senddewpointalert.rules        # Domain: dewpoint alerts
- washing.rules                   # Domain: washing machine
```

### When to Split Files

**Split when:**
- File exceeds ~300 lines
- Multiple unrelated automation domains in one file
- Different deployment schedules (test vs. production)
- Different maintenance responsibilities

**Keep together when:**
- Rules share common items
- Rules are tightly coupled (depend on each other)
- Total lines < 200 and logically related

### File Header Pattern

```xtend
////////////////////////////////////////////////////////
/// Bathroom Dewpoint Alert
////////////////////////////////////////////////////////
rule "dewpointBadAlert"
when
    Item Bathroom_DewPoint changed
then
    // Rule logic
end

////////////////////////////////////////////////////////
/// Parents Bedroom Dewpoint Alert
////////////////////////////////////////////////////////
rule "dewpointBedroomAlert"
when
    Item ParentsBedroom_DewPoint changed
then
    // Rule logic
end
```

Clear section headers make navigation easier in long files.

---

## Quick Reference

### Before Writing Any Rule

1. ✅ Add NULL guards for all item states you'll use
2. ✅ Use instanceof if item can have multiple types
3. ✅ Log warnings when skipping due to NULL
4. ✅ Use appropriate string formatting for messages
5. ✅ Consider state-based deduplication for alerts
6. ✅ Organize related rules in same file

### Common Gotchas

| Issue | Solution |
|-------|----------|
| Rule crashes on sensor offline | Add NULL guards before accessing state |
| Duplicate notifications | Use state-based deduplication pattern |
| Wrong unit in calculations | Use `.toUnit("desired_unit")` |
| Cron not triggering | Check seconds field (often `0`) |
| DateTime parsing fails | Use `.getInstant.atZone(ZoneId.systemDefault())` |
| Incorrect time math | Use `Duration.between(start, end).toMinutes()` |
