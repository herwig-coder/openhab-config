# KNX Motion Logic Redesign — Design

**Date:** 2026-05-22
**Status:** Approved. Three new GAs already created in ETS (1/0/9, 1/0/10, 1/0/11).
**Authoritative reference for KNX-side design:** `<personal-docs>/smart-home/knx-motion-logic.md`
(located at `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\docs\smart-home\knx-motion-logic.md`).

This spec covers only the **openhab-config-side** changes. KNX hardware/ETS design,
parameter tables, and migration order live in the personal docs.

## Goal

Replace the current "each BWM owns its own light timer and writes the light GA
directly" pattern with "BWMs send ON-pulses on dedicated motion GAs, N567 actuator
holds a single retriggerable staircase timer per zone". Fixes the off-on flapping
caused by two competing BWM timers in the main corridor.

The redesign keeps all main lighting logic in KNX. OpenHAB only needs to:
1. Expose the three new motion GAs as items (for the AwayMode telegram alarm,
   visualization, future analytics)
2. Rewire the existing AwayMode telegram rule from `Corridor_Light` (light-state
   proxy) to the new `Corridor_Motion` item (true motion signal)
3. Clean up the now-obsolete `Corridor_lights_lock_Motion_Entry` channel (which
   was historically a misuse of GA `1/0/5`)

## In Scope (this spec)

- New KNX channels in `things/KNX_tunnel.things` for `1/0/9`, `1/0/10`, `1/0/11`
- New items in `items/awaymode.items` (or a new `items/motion.items`):
  `Corridor_Motion`, `SmallCorridor_Motion`, `WC_Motion`
- Update `rules/awaymode.rules` R3: trigger on `Corridor_Motion` not on `Corridor_Light`
- Deprecate `Corridor_lights_lock_Motion_Entry` channel (still bound to `1/0/5` —
  after ETS migration that GA carries nothing meaningful)
- Commissioning notes / verification steps in OpenHAB (events.log + UI sanity)

## Out of Scope (covered in personal docs)

- ETS parameter tables for the 4 BWMs and the N567 actuator channels
- Migration order in ETS (which device to download first, why)
- Hardware-level stolpersteine
- Aktor-Inventar / .knxproj extraction

## OpenHAB-Side Architecture

### New channels in `things/KNX_tunnel.things`

Add inside the existing `Thing device knx_main` block, near the existing corridor
lock channels (~line 79–82):

```xtend
// Bewegungs-Trigger der Vorraum- und WC-BWMs (neu 2026-05-22, siehe
// docs/superpowers/specs/2026-05-22-knx-motion-redesign-design.md und
// persönliche Doku smart-home/knx-motion-logic.md)
Type switch        : Corridor_Motion                    "Motion"        [ga="1.001:1/0/9" ]
Type switch        : SmallCorridor_Motion               "Motion"        [ga="1.001:1/0/10" ]
Type switch        : WC_Motion                          "Motion"        [ga="1.001:1/0/11" ]
```

### New items (`items/motion.items`)

```xtend
Switch Corridor_Motion       "Vorraum Bewegung [%s]"          <if:mdi:motion-sensor>  (gMainCorridor)   ["Status","Presence"]  {channel="knx:device:bridge:knx_main:Corridor_Motion"}
Switch SmallCorridor_Motion  "Kleiner Vorraum Bewegung [%s]"  <if:mdi:motion-sensor>  (gSmallCorridor)  ["Status","Presence"]  {channel="knx:device:bridge:knx_main:SmallCorridor_Motion"}
Switch WC_Motion             "WC Bewegung [%s]"               <if:mdi:motion-sensor>  (gWC)             ["Status","Presence"]  {channel="knx:device:bridge:knx_main:WC_Motion"}
```

`gWC` exists in semantic model (verify before commit). The items can stay in their
own file `items/motion.items` rather than being added to `awaymode.items`, since
their primary purpose is broader than just away-mode (future: presence-aware
heating, illumination logic, etc.).

### AwayMode rule rewiring

In `rules/awaymode.rules`, change the R3 trigger:

```xtend
// Before:
when
    Item Corridor_Light changed to ON

// After:
when
    Item Corridor_Motion changed to ON
```

The body of the rule is unchanged. Message text could be adjusted to mention
"Bewegungsmelder" explicitly since the signal is now unambiguous.

R1 and R2 (lock override) stay completely as-is — they react to `Strasshof_AwayMode`
changes and to lock-attempt items, none of which are affected.

### Deprecation

After the ETS migration, `1/0/5` "Vorraum Hauptlicht Eingang BWM" carries no
traffic anymore (the Eingangs-BWM now sends only to `1/0/9`). Remove the now-misleading
channel from `things/KNX_tunnel.things`:

```xtend
// REMOVE:
Type switch        : Corridor_lights_lock_Motion_Entry  "Light"         [ga="1.001:1/0/5" ]
```

No item references this channel in the current configuration (verified during
brainstorm).

## Migration Sequencing (OpenHAB perspective)

The KNX migration steps (ETS configuration, BWM downloads, actuator parametrization)
are owned by the user and documented in the personal docs. The OpenHAB-side changes
can be applied in either order:

- **Before KNX migration:** new channels return UNDEF until BWMs start sending —
  harmless. Items appear in UI but stay NULL.
- **After KNX migration:** new items immediately receive traffic; AwayMode rule
  re-trigger starts working with the cleaner signal.

Recommended: apply OpenHAB changes **after** ETS migration is complete and verified,
so we don't have stale channels around if anything in the KNX side gets rolled back.

## Acceptance Criteria

1. After full migration, `events.log` shows `Corridor_Motion changed from OFF to ON`
   events when someone passes either VR GR or Eingangs-BWM.
2. AwayMode telegram alarm fires on `Corridor_Motion` ON (not on light state change).
3. Hauptlicht Vorraum (1/0/0) goes ON when motion detected, stays ON for actuator's
   night-mode duration (~3 min), then goes OFF cleanly — no flapping on subsequent
   2-3 minute observation windows.
4. `Strasshof_AmbientLight_On` ON (manual or via sunset rule when AwayMode==OFF)
   locks BWMs → no light from motion → behavior unchanged from before redesign.

## Risks

| Risk | Mitigation |
|---|---|
| New motion items receive no traffic after migration | Verify with manual BWM trigger before swapping AwayMode rule; check `events.log` |
| AwayMode rule double-fires (old trigger on `Corridor_Light` + new on `Corridor_Motion`) | Replace, do not duplicate — single trigger per rule |
| Channel deprecation breaks something | Confirm no item linked to old channel before deletion (grep done) |
| KNX migration rollback needed mid-way | OpenHAB changes are backwards-compatible: old GAs still exist; new items just stay NULL until BWMs send |
