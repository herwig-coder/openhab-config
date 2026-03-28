# Priority-Based State Management

## The Problem: Competing Automations

When multiple rules can control the same device (e.g., blinds controlled by
sunrise, privacy mode, manual buttons, wind alarm), they fight each other because
none of them knows WHY the device is currently in its state.

**Example failure chain:**
1. Sunrise rule → lowers blind to 50% → sets priority "sunrise"
2. User enables privacy → lowers blind to 90%
3. User disables privacy → rule lifts blind to 0% ✓
4. But "sunrise" intent is still active → sunrise rule fires again next event ✗

**Solution: A priority variable that tracks who last set the state, and rules
that check priority before acting.**

---

## Core Pattern: Priority Variable + Guard

### Step 1: Define a file-level priority variable

```xtend
// Priority levels (higher number = higher authority):
// 0 = idle
// 1 = automation (sunrise, schedule)
// 2 = comfort/scene (privacy, away mode)
// 3 = manual (user pressed button)
// 4 = safety (wind, rain, alarm)

var String  blindPriority    = "idle"
var int     blindPriorityLevel = 0
```

### Step 2: Each rule checks and sets priority

```xtend
rule "Blind - Sunrise Half Position"
when
    Time cron "0 30 6 * * ?"
then
    // Only act if nothing more important is active
    if (blindPriorityLevel > 1) {
        logInfo("Blinds", "Sunrise skipped — higher priority active: {}", blindPriority)
        return;
    }

    blindPriority      = "sunrise"
    blindPriorityLevel = 1
    sendCommand(MyBlind_Position, 50)
    logInfo("Blinds", "Sunrise: blind set to 50%, priority = sunrise")
end

rule "Blind - Privacy ON"
when
    Item Privacy_Mode received command ON
then
    blindPriority      = "privacy"
    blindPriorityLevel = 2
    sendCommand(MyBlind_Position, 90)
    logInfo("Blinds", "Privacy ON: blind set to 90%")
end

rule "Blind - Privacy OFF"
when
    Item Privacy_Mode received command OFF
then
    // Release priority — go back to whatever automation was active, or idle
    if (blindPriority == "privacy") {
        blindPriority      = "idle"
        blindPriorityLevel = 0
        sendCommand(MyBlind_Position, 0)   // fully open — user released privacy
        logInfo("Blinds", "Privacy OFF: blind opened, priority reset to idle")
    }
end

rule "Blind - Manual Button"
when
    Item KNX_Blind_Button received command
then
    // Manual always wins — highest normal priority
    blindPriority      = "manual"
    blindPriorityLevel = 3
    sendCommand(MyBlind_Position, receivedCommand)
    logInfo("Blinds", "Manual override: blind set to {}", receivedCommand.toString)
end

rule "Blind - Wind Safety"
when
    Item Wind_Alarm changed to ON
then
    // Safety overrides everything
    blindPriority      = "wind"
    blindPriorityLevel = 4
    sendCommand(MyBlind_Position, 0)   // fully retract for safety
    logWarn("Blinds", "WIND ALARM: blind retracted, priority = wind")
end

rule "Blind - Wind Safety Clear"
when
    Item Wind_Alarm changed to OFF
then
    if (blindPriority == "wind") {
        blindPriority      = "idle"
        blindPriorityLevel = 0
        logInfo("Blinds", "Wind alarm cleared, priority reset")
    }
end
```

---

## Pattern: Priority Item (Persistent Across Restarts)

File-level variables reset when OpenHAB restarts. For blinds that must remember
their mode across reboots, use a **String item** with persistence instead.

```xtend
// In items file:
String Blind_LivingRoom_Priority  "Blind Priority [%s]"  (Persisted)
```

```xtend
// In rules — read from item, not variable
rule "Blind - Sunrise"
when
    Time cron "0 30 6 * * ?"
then
    val String currentPriority = Blind_LivingRoom_Priority.state.toString

    if (currentPriority == "manual" || currentPriority == "wind") {
        logInfo("Blinds", "Sunrise skipped, priority: {}", currentPriority)
        return;
    }

    postUpdate(Blind_LivingRoom_Priority, "sunrise")
    sendCommand(MyBlind_Position, 50)
end
```

---

## Priority Resolution Table

Use this table when designing rules. Fill it in for your home:

| Priority | Name     | Level | Who sets it    | Who can override |
|----------|----------|-------|----------------|------------------|
| Lowest   | idle     | 0     | reset rules    | anyone           |
|          | sunrise  | 1     | cron rule      | comfort, manual, safety |
|          | privacy  | 2     | scene rule     | manual, safety   |
|          | manual   | 3     | button press   | safety only      |
| Highest  | wind/safety | 4  | sensor alarm   | nobody           |

---

## Common Mistakes to Avoid

```xtend
// WRONG: Privacy OFF blindly opens blind without checking who set it
rule "Privacy OFF - wrong"
when
    Item Privacy_Mode received command OFF
then
    sendCommand(MyBlind_Position, 0)  // What if wind alarm is active? Now blind is open in a storm!
end

// CORRECT: Always check priority before acting
rule "Privacy OFF - correct"
when
    Item Privacy_Mode received command OFF
then
    if (blindPriority != "privacy") return;  // don't override something more important
    blindPriority = "idle"
    blindPriorityLevel = 0
    sendCommand(MyBlind_Position, 0)
end
```
