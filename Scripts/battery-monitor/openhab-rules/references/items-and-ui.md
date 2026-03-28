# Items, Semantic Model & Main UI

## Semantic Model Structure

Full three-layer model — every new item must fit here:

```
Location:  Home > Floor > Room          (tag: Location)
Equipment: Room > Device                (tag: Equipment — Blind, Light, HVAC...)
Point:     Equipment > Control/Status   (tag: Point — Control, Status, Measurement)
```

Always confirm group placement with the user before writing item definitions.

---

## Item Definition Template

```xtend
// Location group
Group LivingRoom "Living Room" <oh:room> ["LivingRoom"]

// Equipment group
Group LivingRoom_Blind "Living Room Blind" <oh:blinds> ["Blinds"] (LivingRoom)

// Points
Rollershutter Blind_LivingRoom_Position "Position [%d %%]"  <oh:blinds>   ["Control"] (LivingRoom_Blind)
Number        Blind_LivingRoom_Priority "Priority [%s]"     <oh:settings> ["Status"]  (LivingRoom_Blind)
```

---

## Naming Convention

```
<Equipment>_<Location>_<Function>

Blind_LivingRoom_Position
Light_Kitchen_Brightness
Temp_Bedroom_Current
Mode_House_Away          ← virtual/flag items prefix with Mode_ or Flag_
```

PascalCase, no spaces, no special characters.

---

## Icon Family — use `oh:` always

| Device/Purpose | Icon |
|---------------|------|
| Blind/Shutter | `oh:blinds` |
| Light | `oh:light` |
| Temperature | `oh:temperature` |
| Switch | `oh:switch` |
| HVAC | `oh:climate` |
| Wind | `oh:wind` |
| Rain | `oh:rain` |
| Settings/Config | `oh:settings` |
| Security | `oh:lock` |
| Motion | `oh:motion` |
| Energy | `oh:energy` |
| Room | `oh:room` |
| Floor | `oh:floor` |
| House | `oh:house` |

Suggest the best match, let user confirm.

---

## oh-location-card Compatibility

Main home page = oh-location-card drill-down: Home → Floor → Room → Equipment → Points.
Every item needs: label, icon, correct semantic group. Equipment groups need a category tag.

---

## Widget Decision Guide

Only suggest when it **clearly adds visualization value**:

| Item type | Widget? | Type |
|-----------|---------|------|
| Rollershutter position | ✅ | `oh-slider-card` (0-100%) |
| Dimmer/brightness | ✅ | `oh-slider-card` |
| Temperature | ✅ | `oh-label-card` with unit |
| User-facing switch | ✅ | `oh-toggle-card` |
| Priority/mode string | ❌ | Background — skip |
| Internal flags/timers | ❌ | Background — skip |

### oh-slider-card (blind position)
```yaml
component: oh-slider-card
config:
  title: Living Room Blind
  item: Blind_LivingRoom_Position
  min: 0
  max: 100
  step: 5
  icon: oh:blinds
```

### oh-label-card (temperature)
```yaml
component: oh-label-card
config:
  title: Temperature
  item: Temp_LivingRoom_Current
  icon: oh:temperature
```

### oh-toggle-card (switch)
```yaml
component: oh-toggle-card
config:
  title: Living Room Light
  item: Light_LivingRoom_Switch
  icon: oh:light
```

---

## New Item Checklist

Always ask before creating items:
1. **Group** — which location + equipment group?
2. **Icon** — suggest from oh: family, user confirms
3. **Widget** — only if user-facing and visual
4. **Persistence** — needs to survive restart? (priority flags, mode items → mapdb group)
