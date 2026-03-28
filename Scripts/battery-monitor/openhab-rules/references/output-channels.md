# Output Channels: Telegram & Awtrix

## Core Principle: Centralized Notification Config

**All notifications go through OpenHAB rules using action services.**

```
┌──────────────┐
│ Python Script│──REST API──> OpenHAB Items ──changed──> Notification Rule ──> Telegram
│ OR           │                                          (action service)
│ DSL Rule     │
└──────────────┘
```

**Benefits**:
- Change bot config in one place (OpenHAB Thing)
- Add new notification channels without touching scripts
- Consistent notification logic across all automations

---

## When to Suggest Each Channel

| Situation | Telegram | Awtrix |
|-----------|----------|--------|
| Safety alert (wind, flood, alarm) | ✅ Always | ✅ Flash/alert |
| Script or rule error | ✅ Yes | ❌ |
| Automation completed (blind set, scene activated) | Optional | ✅ Brief notification |
| Daily summary / status report | ✅ Yes | ❌ |
| Glanceable real-time value (power, temp) | ❌ | ✅ Yes |
| User interaction needed (confirmation) | ✅ Yes | ❌ |

Proactively suggest output when the rule does something worth knowing about.
When scope exceeds home alerts bot, flag: *"This might warrant a new bot — shall we define one?"*

---

## Python Scripts: Update Items, Don't Send Directly

**Pattern**: Python scripts update OpenHAB status items → Notification rule watches items → Sends Telegram

### Python script (updates items via REST API)
```python
import requests
import os

def update_openhab_status(status: str, message: str = ""):
    """Update status item in OpenHAB."""
    url = f"{os.getenv('OPENHAB_URL')}/rest/items/MyScript_Status"
    headers = {'Authorization': f"Bearer {os.getenv('OPENHAB_TOKEN')}"}

    requests.post(url, headers=headers, data=status, timeout=5)

    if message:
        requests.post(
            f"{os.getenv('OPENHAB_URL')}/rest/items/MyScript_Message",
            headers=headers,
            data=message,
            timeout=5
        )

# Usage
try:
    update_openhab_status("RUNNING")
    result = do_work()
    update_openhab_status("SUCCESS", f"Processed {result} items")
except Exception as e:
    update_openhab_status("ERROR", str(e))
```

### Notification rule (watches items, sends Telegram)
```xtend
rule "Script Notifications"
when
    Item MyScript_Status changed
then
    val String status = MyScript_Status.state.toString
    val String message = MyScript_Message.state.toString
    val telegramAction = getActions("telegram", "telegram:telegramBot:homeAlerts")

    if (status == "ERROR") {
        telegramAction.sendTelegram("⚠️ Script error: " + message)
    } else if (status == "SUCCESS" && message != NULL) {
        telegramAction.sendTelegram("✅ " + message)
    }
end
```

**Why this pattern?**
- Bot config stays in OpenHAB (one place to change chat ID/token)
- Easy to add email, Awtrix, etc. without touching Python
- Scripts remain standalone (no Telegram dependency)

---

## Telegram — Home Alerts Bot

### Rule action syntax (DSL rules)
```xtend
val telegramAction = getActions("telegram", "telegram:telegramBot:homeAlerts")
telegramAction.sendTelegram("Message text here")
```

### With item value in message
```xtend
val telegramAction = getActions("telegram", "telegram:telegramBot:homeAlerts")
telegramAction.sendTelegram(
    "⚠️ Wind alarm! Blind retracted. Current position: " + MyBlind.state.toString + "%"
)
```

### Severity conventions
| Level | Prefix | Use for |
|-------|--------|---------|
| 🔴 Alert | `⚠️` or `🚨` | Safety, errors, failures |
| 🟡 Warning | `⚡` | Unexpected state, fallback triggered |
| 🟢 Info | `✅` or `ℹ️` | Completed automations, summaries |

### When to add Telegram notification rule
- Any safety event (wind, flood, security) → always create notification rule
- Python script errors → create notification rule watching status item
- Daily summary results → create notification rule for completed status
- Automation state changes → optional, ask user
- **Never** send Telegram directly from Python scripts — always via notification rule

### Adding a new bot
When a rule's notification needs don't fit "home alerts":
→ Flag to user: *"Should we define a new Telegram bot for this? E.g., a 'daily status' bot or 'energy monitor' bot?"*
→ Do not assume — wait for user to define bot name and chat ID before writing the action

### Multiple Telegram Bots Pattern

**Use separate bots to keep notification streams distinct:**

```xtend
// General home alerts
val telegramAction = getActions("telegram", "telegram:telegramBot:Telegram_Bot")
telegramAction.sendTelegram("⚠️ Dewpoint alert: Time to air bathroom")

// Specialized washing machine bot
val washbotAction = getActions("telegram", "telegram:telegramBot:TelegramWashbot_Bot")
washbotAction.sendTelegram("Check for new wash now. Last wash was 3 days ago.")
```

**When to use separate bots:**

| Use Case | Example Bots | Benefit |
|----------|-------------|---------|
| Different priorities | `Telegram_Bot` (safety), `StatusBot` (daily summaries) | Users can mute summaries without missing alerts |
| Different audiences | `HomeAlerts` (family chat), `TechAlerts` (personal) | Target messages to appropriate recipients |
| Domain separation | `Telegram_Bot` (general), `TelegramWashbot_Bot` (chores) | Clear organization of notification types |

**Decision guide:**
- **Same bot**: Related functionality, same priority level, same audience
- **Separate bot**: Different mute preferences, different audiences, distinct domains

**Configuration**: Each bot is a separate Thing in OpenHAB with its own chat ID and token.

### NULL Guards: Item States vs. Action Services

**CRITICAL**: NULL guards are required for **item states**, not for action services.

```xtend
rule "Dewpoint Alert with Telegram"
when
    Item Bathroom_DewPoint changed
then
    // ✅ REQUIRED: NULL guard on item states before using
    if (Bathroom_DewPoint.state == NULL || Bathroom_DewPoint.state == UNDEF) {
        logWarn("Alert", "Bathroom_DewPoint is NULL/UNDEF, skipping")
        return;
    }
    if (Weatherstation_Temperature_1.state == NULL || Weatherstation_Temperature_1.state == UNDEF) {
        logWarn("Alert", "Weatherstation_Temperature_1 is NULL/UNDEF, skipping")
        return;
    }

    // Safe to cast after NULL guards
    val temp = (Bathroom_DewPoint.state as QuantityType<Number>).toUnit("°C").doubleValue
    val outtemp = (Weatherstation_Temperature_1.state as QuantityType<Number>).toUnit("°C").doubleValue

    if ((temp > 18.3) && (outtemp < 10)) {
        // ✅ NO NULL guard needed for action service
        val telegramAction = getActions("telegram", "telegram:telegramBot:Telegram_Bot")
        telegramAction.sendTelegram("ALERT! Time to air. Dewpoint at: " + String.format("%.1f", temp) + " °C")
    }
end
```

**Why?**
- Item states can be NULL/UNDEF (sensor offline, not initialized)
- Action services either exist (configured Thing) or throw error on getActions call
- Casting NULL item states causes crashes; using action service does not

---

## Awtrix / Ulanzi Pixel Clock — MQTT

### Architecture: One Item Per App

**Pattern**: Create dedicated items for each "app" on the display
```
Ulanzi_01_garbage   → Garbage collection reminder
Ulanzi_01_energy    → Energy price display
Ulanzi_01_alerts    → General alerts
```

Each item sends to its own MQTT topic/app, allowing independent control.

### Items Definition
```
String Ulanzi_01_garbage  "Garbage Alert"   <garbage>  (gDisplay)  {channel="mqtt:topic:mqtt_Ulanzi:Ulanzi_01_garbage"}
String Ulanzi_01_energy   "Energy Price"    <energy>   (gDisplay)  {channel="mqtt:topic:mqtt_Ulanzi:Ulanzi_01_energy"}
String Ulanzi_01_alerts   "System Alerts"   <alarm>    (gDisplay)  {channel="mqtt:topic:mqtt_Ulanzi:Ulanzi_01_alerts"}
```

### JSON Payload Format (Standard)
```json
{"text":"message", "color":"#RRGGBB", "icon":"laMetric_id"}
```

### Rule Pattern with NULL Guards

```xtend
rule "Ulanzi Energy Price"
when
    Item EnergyPrice changed
then
    // CRITICAL: NULL guard first
    if (EnergyPrice.state == NULL || EnergyPrice.state == UNDEF) return;

    val price = (EnergyPrice.state as QuantityType<Number>).doubleValue

    // Color logic
    var color = "#FFDE21"  // Yellow default
    if (price > 30) { color = "#FF0000" }  // Red = expensive
    if (price < 24) { color = "#00FF00" }  // Green = cheap

    // Compose JSON payload
    val message = "{\"text\":\"" + String.format("%.2f",price) + " ct\",\"color\":\"" + color + "\",\"icon\":\"53070\"}"

    logInfo("Ulanzi", "Energy price update: {}", message)
    Ulanzi_01_energy.sendCommand(message)
end
```

### Clear App from Display
```xtend
Ulanzi_01_energy.sendCommand("")  // Removes app completely
```

### Conditional Visibility (Time-Based Display)
```xtend
// Enable/disable apps based on time or conditions
Switch Ulanzi_TrainCheck  "Show Train Info"

rule "Enable Train Display"
when Time cron "0 20 7 ? * MON-FRI *"  // Weekday mornings
then Ulanzi_TrainCheck.sendCommand(ON)

rule "Disable Train Display"
when Time cron "0 50 7 ? * MON-FRI *"
then
    Ulanzi_TrainCheck.sendCommand(OFF)
    Ulanzi_01_train.sendCommand("")  // Clear display
end

rule "Update Train Info"
when
    Item TrainStatus changed or
    Item Ulanzi_TrainCheck changed
then
    if (Ulanzi_TrainCheck.state != ON) return;
    if (TrainStatus.state == NULL || TrainStatus.state == UNDEF) return;

    // Only update when check is enabled
    val message = "{\"text\":\"Train on time\",\"color\":\"#00FF00\",\"icon\":\"12738\"}"
    Ulanzi_01_train.sendCommand(message)
end
```

### Color Conventions
| Color | Hex | Use For |
|-------|-----|---------|
| 🔴 Red | `#FF0000` | Alerts, high values, errors |
| 🟡 Yellow | `#FFDE21` | Warnings, medium values |
| 🟢 Green | `#00FF00` | OK status, low values |
| 🔵 Blue | `#0000FF` | Info, neutral status |
| ⚪ White | `#FFFFFF` | Default, time displays |

### LaMetric Icon IDs (Common)
| Icon | ID | Use |
|------|----|----|
| ⚡ Lightning | `53070` | Energy/electricity |
| 🚂 Train | `12738` | Transportation |
| 🗑️ Garbage | `53860` | Waste collection |
| 🪟 Window | `32097` | Airing/ventilation |
| 📊 Graph | `37520` | Statistics/charts |
| 🌡️ Thermometer | `2422` | Temperature |

**Find more icons**: https://developer.lametric.com/icons

### Python Script Integration

Python scripts update status items → Rule formats Ulanzi JSON → Sends to display

```python
# Python script updates simple item
def update_energy_price(price: float):
    requests.post(
        f"{OPENHAB_URL}/rest/items/EnergyPrice",
        headers=headers,
        data=str(price)
    )

# Rule handles Ulanzi formatting and display logic
```

### When to Suggest Ulanzi
- ✅ Real-time measurements (power, temp) → persistent app
- ✅ Time-sensitive info (train, garbage) → conditional visibility
- ✅ Color-coded status → use color conventions
- ✅ Multi-app displays → one item per app
- ❌ Long text → use Telegram instead
- ❌ Interactive controls → not supported
