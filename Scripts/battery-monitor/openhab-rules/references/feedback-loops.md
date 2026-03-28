# Feedback Loop Prevention

## Why Loops Happen in Mixed-Bus Systems (KNX + Shelly)

In OpenHAB, when a physical device (e.g., a Shelly relay) is linked to both:
- A **KNX group address** (for button input), AND
- An **OpenHAB item** (for state feedback)

...a rule triggered by the KNX button press may send a command to the Shelly item,
which then sends a state update back, which triggers the same rule again — firing twice.

The root causes are almost always one of:
1. The rule triggers on BOTH the command item AND the feedback/state item
2. `sendCommand` is used on a feedback item (should be `postUpdate`)
3. No guard to detect "I caused this state change"

---

## Pattern 1: Separate Command and Feedback Items

The cleanest solution is to **never let the feedback item trigger the same rule** as the command item.

```xtend
// Items file design (best practice)
// KNX button → command item (triggers rule)
Switch KNX_Button_LivingLight  { channel="knx:..."}

// Shelly actual state → feedback item (does NOT trigger the rule)
Switch Shelly_LivingLight_State { channel="shelly:..."}

// Virtual item Claude controls — the "truth" for the room
Switch LivingRoom_Light
```

```xtend
// Rule: KNX button → control Shelly, update virtual item
rule "Living Room Light - KNX Button"
when
    Item KNX_Button_LivingLight received command
then
    val OnOffType cmd = receivedCommand as OnOffType
    sendCommand(Shelly_LivingLight, cmd)       // to device
    postUpdate(LivingRoom_Light, cmd)          // update virtual item — no command sent to bus
end

// Rule: Shelly feedback → sync virtual item only (NOT sendCommand)
rule "Living Room Light - Shelly Feedback Sync"
when
    Item Shelly_LivingLight_State changed
then
    postUpdate(LivingRoom_Light, Shelly_LivingLight_State.state)
    // No sendCommand here — avoids loop
end
```

---

## Pattern 2: Guard with `triggeringItem`

When you cannot separate items, use `triggeringItem` to detect what caused the rule to fire.

```xtend
rule "Light Control - Guard Pattern"
when
    Item KNX_Button changed or
    Item Shelly_Light_State changed
then
    // Only act on button presses, ignore Shelly feedback
    if (triggeringItem.name == "Shelly_Light_State") return;

    sendCommand(Shelly_Light, KNX_Button.state as OnOffType)
end
```

---

## Pattern 3: Debounce with a Flag Variable

When a rule must respond to both items, use a file-level flag to suppress re-entry.

```xtend
var boolean lightRuleRunning = false

rule "Light with debounce"
when
    Item KNX_Button received command ON
then
    if (lightRuleRunning) return;
    lightRuleRunning = true

    sendCommand(Shelly_Light, ON)

    // Release flag after short delay
    createTimer(now.plusMillis(500)) [ |
        lightRuleRunning = false
    ]
end
```

---

## Pattern 4: `received command` vs `changed` — Choose Carefully

| Trigger | Fires when... | Risk |
|---------|--------------|------|
| `received command` | A command is explicitly sent to the item | Lower — physical user action |
| `changed` | State changes for ANY reason (command, update, binding sync) | Higher — binding feedback can re-trigger |
| `received update` | Any update received, even same value | Highest — fires even if state didn't change |

**Rule of thumb:** For button/command rules, prefer `received command`. Reserve `changed` for
rules that genuinely need to respond to state transitions from any source.

---

## KNX-Specific: One-Press Guarantee

KNX buttons sometimes send both a PRESS (ON) and RELEASE (OFF) signal. To ensure
only one action fires:

```xtend
rule "KNX Button - press only, ignore release"
when
    Item KNX_Button_Blind received command
then
    if (receivedCommand != UP && receivedCommand != DOWN) return;  // ignore STOP/release
    // handle UP / DOWN
end
```
