---
name: openhab-rules
description: >
  Use this skill whenever the user asks to write, fix, review, or improve anything related to
  OpenHAB 4.x automation — including Rules DSL (Xtend) scripts, Python extension scripts called
  from rules, item definitions, widget suggestions, deployment to Linux, or output via Telegram
  or Awtrix/Ulanzi. Triggers include: any mention of openHAB rules, .rules files, Xtend scripts,
  Python scripts for openHAB, item automations, KNX, Shelly, blind/shutter control, cron rules,
  HTTP actions, deploying scripts via SCP, openHAB items/groups/semantic model, Main UI widgets,
  oh-location-card, Telegram bot notifications, MQTT Awtrix pixel clock, or any home automation
  logic targeting openHAB 4.x. Always use this skill even for "simple" requests — there are many
  subtle pitfalls across all these areas.
---

# OpenHAB 4.x Automation Skill

This skill covers the full development workflow:
1. **Rules DSL (Xtend)** — automations running inside OpenHAB
2. **Python 3 standalone scripts** — independent scripts at `/opt/script-name/` with virtual environments, using REST API to update OpenHAB items
3. **Items & semantic model** — correct item definition, groups, icons, widgets
4. **Output channels** — Telegram via OpenHAB action service (centralized config) and Awtrix/Ulanzi pixel clock via MQTT
5. **Deployment** — Virtual environment setup with isolated dependencies, triggered by rules or cron

## Architecture Pattern

**Python scripts update items → OpenHAB rules send notifications**

```
┌─────────────────┐
│  Python Script  │ Updates items via REST API
│  /opt/script/   │────────────────────────┐
└─────────────────┘                        │
                                           ▼
                                  ┌────────────────┐
                                  │ OpenHAB Items  │
                                  │ MyScript_Status│
                                  └────────────────┘
                                           │ Item changed
                                           ▼
                                  ┌────────────────┐
                                  │ OpenHAB Rule   │ Sends Telegram
                                  │ (notification) │ via action service
                                  └────────────────┘
```

**Benefits**: Centralized notification config, scripts remain standalone, clean separation of concerns.

---

## Reference Files

Load these as needed — do not load all upfront:

| File | Load when... |
|------|-------------|
| `references/deployment.md` | **SETUP**: Configuring deployment pipeline, rollback procedures, or Git-based deployment from Windows to Linux |
| `references/security-guidelines.md` | **CRITICAL**: Using executeCommandLine, HTTP calls with user input, or storing credentials — read FIRST |
| `references/naming-conventions.md` | Creating new items, rules, or files — check naming patterns for consistency |
| `references/common-patterns.md` | Need examples of cron expressions, DateTime handling, QuantityType conversions, string formatting, or other frequently-used DSL patterns |
| `references/feedback-loops.md` | Rule involves KNX, Shelly, or any mixed-bus item that both triggers and is commanded |
| `references/state-management.md` | Multiple automations can control the same device (blinds, lights, HVAC) |
| `references/external-data.md` | Rule needs HTTP calls or shell commands to fetch data from external services |
| `references/extension-scripts.md` | A Python script needs to be written, deployed, or called from a rule |
| `references/items-and-ui.md` | New items, groups, icons, or Main UI widgets are needed |
| `references/output-channels.md` | Telegram notification or Awtrix display output is appropriate |

---

## Mandatory Interactions — Always Ask Before Writing

### 1. Time-based rules (cron)
When the user says "check at X time" or "run at X o'clock":
> **"Should this use the current day of execution dynamically, or a fixed date?"**
→ Default to **dynamic (current day)** unless told otherwise.

### 2. New items required
Before creating any item always ask:
- **"Which group should this item belong to?"** (semantic Location, Equipment, or Point group)
- **"Should I apply an icon? If yes, I'll suggest one from the `oh:` icon family."**
- **"Does a widget add clear value here?"** — propose only if it helps the user monitor or control something actively. Skip for background flags/state variables.

### 3. Python extension scripts
Before writing any extension script:
- Confirm script name and single-sentence purpose
- Ask: **"Are existing items sufficient, or do new items need to be created?"**
- Always deliver: **script + calling rule snippet + deployment instructions** as a complete set

### 4. Output channel suggestions
When a rule does something worth notifying about, proactively suggest:
- **Errors / safety alerts** → Telegram home alerts bot
- **Glanceable status changes** → Awtrix pixel clock
- **Awtrix config not yet defined** → note "Awtrix MQTT topic/app name TBD" and ask user when ready
- **New Telegram bot scope** → flag: *"This might warrant a dedicated bot — shall we define one?"*

---

## Non-Negotiable DSL Rules

### 1. NULL / UNDEF guard — always, no exceptions
```xtend
// WRONG
var Number pos = MyBlind_Position.state as Number

// CORRECT
if (MyBlind_Position.state == NULL || MyBlind_Position.state == UNDEF) return;
var Number pos = MyBlind_Position.state as Number
```

### 2. `val` vs `var` — closures always use `val`
```xtend
// WRONG — mutable var in closure causes runtime errors
var String mode = "sunrise"
createTimer(now.plusSeconds(5)) [ | logInfo("rule", mode) ]

// CORRECT
val String mode = "sunrise"
createTimer(now.plusSeconds(5)) [ | logInfo("rule", mode) ]
```

### 3. `sendCommand` vs `postUpdate`

**Syntax**: `Item.sendCommand(value)` or `Item.postUpdate(value)`

| Use | When |
|-----|------|
| `MyItem.sendCommand(value)` | Actuator — device must DO something (sends to linked device/binding) |
| `MyItem.postUpdate(value)` | Virtual/flag item — update state only, no bus command |

```xtend
// ✅ CORRECT - Actuator (triggers physical action)
MyBlind.sendCommand(50)
Kitchen_Light.sendCommand(ON)

// ✅ CORRECT - Virtual item (state only)
myFlag.postUpdate(ON)
calculatedValue.postUpdate(42)
```

Mixing these is the #1 cause of KNX/Shelly feedback loops.

### 4. Timer — reschedule instead of recreate

**Best practice**: Use `reschedule()` instead of cancel + recreate.

```xtend
var Timer myTimer = null   // file-level declaration

// In rule body - BEST: Use reschedule
if (myTimer === null) {
    myTimer = createTimer(now.plusSeconds(30)) [ |
        // action
        myTimer = null
    ]
} else {
    myTimer.reschedule(now.plusSeconds(30))
}

// Alternative: Cancel and recreate (less efficient)
if (myTimer !== null) {
    myTimer.cancel()
    myTimer = null
}
myTimer = createTimer(now.plusSeconds(30)) [ |
    // action
    myTimer = null
]
```

**Null checks**: Use `===` for equality, `!==` for inequality with null.

### 5. Type casting

**Best practice**: Cast to `Number` (not DecimalType) to avoid "Ambiguous Method Call" errors.

```xtend
// Number items WITHOUT units
val Number value = MyItem.state as Number
val int intValue = value.intValue
val double doubleValue = value.doubleValue

// Number items WITH units (Temperature, Power, etc.)
val temp = (TempItem.state as QuantityType<Number>).toUnit("°C").doubleValue
val power = (PowerItem.state as QuantityType<Number>).toUnit("kW").doubleValue

// String and boolean conversions
val String mode = MyItem.state.toString
val boolean on = MyItem.state == ON
```

**When to use QuantityType**:
- Temperature: `Number:Temperature` items
- Power/Energy: `Number:Power`, `Number:Energy` items
- Any item with unit dimensions

---

## Rule File Structure

```xtend
// HTTP and Exec actions are auto-imported in OpenHAB 4.x
// Only import when using Java classes directly:
// import java.time.ZonedDateTime
// import java.time.Duration

// File-level state (timers, priority flags)
var Timer  myTimer        = null
var String blindPriority  = "idle"
var int    blindPrioLevel = 0

// ─── Rule ─────────────────────────────────────────────────────────────────
rule "Short Descriptive Name"
when
    Item MyItem changed
then
    if (MyItem.state == NULL || MyItem.state == UNDEF) return;
    // logic
end
```

## Trigger Quick Reference
```xtend
Item MyItem changed
Item MyItem changed from OFF to ON
Item MyItem received command ON
Item MyItem received update
Time cron "0 0 7 * * ?"        // 7:00 AM daily
Time cron "0 0/15 * * * ?"     // every 15 minutes
System started
```

## DSL Logging

**Safe logging** (state can be NULL):
```xtend
// ✅ CORRECT - No .toString needed, handles NULL safely
logInfo("FileName",  "Blind position: {}", MyBlind.state)
logWarn("FileName",  "Unexpected state: {}", MyItem.state)

// ✅ CORRECT - Static messages
logError("FileName", "Critical failure in blind rule")

// ❌ WRONG - Can crash if state is NULL
logInfo("FileName", "Position: {}", MyBlind.state.toString)
```

Log name = rule file name (short, no spaces). Keeps `openhab.log` filterable.

---

## Pre-Delivery Checklist

### Every Rules DSL file
- [ ] NULL/UNDEF guard on every item read
- [ ] `val` in all timer/lambda closures
- [ ] Timers cancelled before recreating
- [ ] `sendCommand` for actuators, `postUpdate` for virtual items
- [ ] Feedback loop guard present where needed (→ see feedback-loops.md)
- [ ] Priority variable updated on automation override (→ see state-management.md)
- [ ] Logging at all key decision points
- [ ] Time-based: confirmed dynamic date with user

### Every Python standalone script
- [ ] Virtual environment setup (`/opt/script-name/venv/`)
- [ ] requirements.txt included with dependencies
- [ ] .env file for configuration (not hardcoded values)
- [ ] Updates OpenHAB items via REST API (not direct Telegram sending)
- [ ] Exits with code 0 (success) / non-zero (failure)
- [ ] Delivered with: calling rule snippet + notification rule + deployment instructions
- [ ] New items confirmed (group + icon + widget decision)
- [ ] Notification rule uses OpenHAB action service (centralized bot config)

### Every new item
- [ ] Semantic group confirmed with user
- [ ] Icon from `oh:` family assigned
- [ ] Widget proposed only if clear visualization value
- [ ] Compatible with oh-location-card drill-down layout

### Output channels
- [ ] Errors/safety events → Telegram home alerts bot considered
- [ ] Glanceable status → Awtrix considered
- [ ] New bot scope → flagged to user if needed
