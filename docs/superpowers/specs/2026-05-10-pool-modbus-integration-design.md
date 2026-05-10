# Pool Modbus Integration — Design

**Date:** 2026-05-10
**Status:** Approved (initial scope, learn-on-the-go)
**Author:** Brainstorm session, herwig.kaltenhauser@gmx.at

## Goal

Integrate two pool devices into OpenHAB via Modbus, using a Waveshare 2-channel
Modbus-to-Ethernet adapter:

1. **SugarValley Oxilife** — salt chlorinator
2. **Poolsana InverPower Ultra** — heat pump

Scope: full monitoring **and** control (read setpoints/state, write setpoints/modes).
Existing KNX `Pool_Salinator` switch stays in place; consolidation is deferred until
the Modbus path has proven stable.

## Approach

Phased rollout (Option A) — risky write commands only after register addresses are
verified against the live devices with `modpoll`. Reduces the chance of writing to
a wrong register because the Poolsana register map is community-sourced rather than
official.

| Phase | Scope | Done when |
|---|---|---|
| 1 — Commissioning | Waveshare configured (IP, Modbus TCP gateway mode), RS485 wired to both devices, `modpoll` reads at least one known register on each device with plausible value | One known register per device returns a plausible value |
| 2 — Read-only | Install Modbus binding, create `things/Modbus_Pool.things` and `items/pool_modbus.items` with **read-only** items, values visible in OH5 | All planned read items show plausible values for ≥ 24 h |
| 3 — Read-write | Add write channels and write-capable items, test each setpoint individually | UI setpoint change reaches device and echo-read confirms it |
| 4 — Rules + UI | `rules/pool_modbus.rules` for safety (filter-coupling), Telegram alerts, watchdog. Optional: Awattar coupling, OH5 dashboard widget | Filter OFF forces heat pump and salt unit OFF; a test alarm reaches Telegram |

## Architecture

### Hardware & Network

```
                        ┌─────────────────────────────────┐
   OpenHAB              │ Waveshare 2-Ch                  │
   10.1.100.101         │ Modbus Gateway                  │
        │               │                                 │
        │ TCP :502 ─────┤ Ch1 IP 10.1.0.18 ─ RS485 ─ Oxilife
        │               │                                 │
        └─ TCP :502 ────┤ Ch2 IP 10.1.0.21 ─ RS485 ─ Heatpump
                        └─────────────────────────────────┘
```

- **Adapter exposes two IPs**, one per RS485 channel (each channel has its own
  network interface). Both listen on the standard Modbus TCP port `502`.
- VLAN 200 "HomeAutomation" — `10.1.0.0/16`, gateway `10.1.0.1` (pfSense). Static
  IPs are taken from the lower `10.1.0.x` range (DHCP scope is `10.1.100.100`–
  `10.1.255.254`).
- IPs alongside existing static assignments (KNX `10.1.0.16`, MQTT `10.1.0.10`,
  watermeter `10.1.0.19`, Ulanzi `10.1.0.20`):
  - **Channel 1:** `10.1.0.18` → SugarValley Oxilife
  - **Channel 2:** `10.1.0.21` → Poolsana InverPower Ultra
- Both confirmed free in the pfSense static map at design time. Plan also adds
  a pfSense static DHCP mapping per channel for documentation.
- **Mode:** Modbus TCP server / TCP-to-RTU gateway (not transparent serial)
- **Channel 1 RTU:** typical `19200 8N1`, slave id `1`
- **Channel 2 RTU:** typical `9600 8N1`, slave id `1` (final values verified in
  Phase 1)

**RS485 wiring:** twisted pair for A/B + common GND, 120 Ω termination at both
ends per channel if cable runs more than a few meters.

### OpenHAB Modbus Binding Stack

Standard four-layer hierarchy:

```
modbus:tcp (Bridge)               TCP connection per device
  └── modbus:poller (Bridge)      periodic block read
        └── modbus:data (Thing)   single value, scaling, channel
```

Per device: one TCP bridge, multiple pollers grouped by function code and
contiguous address range, data things below them.

**Polling cadence:**
- Live readings (temperatures, status): refresh `10000` ms
- Setpoint echo (rarely changes): refresh `30000` ms
- `timeBetweenTransactionsMillis=100` to avoid overloading slow RTU slaves

### File Layout

New files:

```
things/
  Modbus_Pool.things              # both bridges (Oxilife + Heatpump). Tracked in git
                                   # — no secrets

items/
  pool_modbus.items               # all Modbus items for both devices

rules/
  pool_modbus.rules               # populated in Phase 4

transform/                         # create if missing
  div10.js
  div100.js
  mul10.js
```

`items/knx.items` and `rules/poolcontrol.rules` stay untouched. Existing
`Pool_Salinator` (KNX switch) is preserved alongside the new Modbus items.

### Naming Convention

| Domain | Prefix | Examples |
|---|---|---|
| Salt unit | `Pool_Salt_` | `Pool_Salt_pH`, `Pool_Salt_ORP`, `Pool_Salt_Salinity`, `Pool_Salt_Setpoint_pH` |
| Heat pump | `Pool_HP_` | `Pool_HP_WaterTempIn`, `Pool_HP_Setpoint`, `Pool_HP_Mode` |

### Semantic Model

Two new equipment groups under existing `gPoolEngineering`
(`items/semantic_model.items:44`):

- `gPool_SaltSystem` "Salzanlage Oxilife" — Equipment
- `gPool_HeatPump` "Wärmepumpe Poolsana" — Equipment

Items get correct semantic tags (`Measurement+Temperature`, `Setpoint+Temperature`,
`Status`, `Alarm`, etc.) so OH5 renders default equipment cards out of the box.

## Data Points

Final addresses are populated during Phase 1 from documentation
(SugarValley official Modbus map; Poolsana from community sources) and verified
with `modpoll` against the live devices. The lists below describe the **target
items**. Items whose registers turn out to be unreadable or differently meaning
are dropped (YAGNI — no item without a working register).

### SugarValley Oxilife — read

| Item | Description | Unit |
|---|---|---|
| `Pool_Salt_pH` | current pH | — (scaled /100) |
| `Pool_Salt_ORP` | redox potential | mV |
| `Pool_Salt_Salinity` | salt concentration | g/L |
| `Pool_Salt_WaterTemp` | water temperature (cell sensor) | °C |
| `Pool_Salt_Production` | current chlorine production | % |
| `Pool_Salt_FlowAlarm` | no-flow alarm | Switch |
| `Pool_Salt_LowSaltAlarm` | low-salt alarm | Switch |
| `Pool_Salt_CellPolarity` | cell polarity | — |

### SugarValley Oxilife — write

| Item | Description |
|---|---|
| `Pool_Salt_Setpoint_pH` | pH setpoint |
| `Pool_Salt_Setpoint_ORP` | ORP setpoint |
| `Pool_Salt_Setpoint_Production` | manual production % |
| `Pool_Salt_Mode` | Auto / Boost / Manual / Off |

### Poolsana InverPower Ultra — read

| Item | Description | Unit |
|---|---|---|
| `Pool_HP_WaterTempIn` | water inlet | °C |
| `Pool_HP_WaterTempOut` | water outlet | °C |
| `Pool_HP_AmbientTemp` | ambient air | °C |
| `Pool_HP_CompressorState` | compressor running | Switch |
| `Pool_HP_FanSpeed` | fan speed | rpm or % |
| `Pool_HP_Power` | current power draw | W |
| `Pool_HP_ErrorCode` | error number (0 = OK) | Number |
| `Pool_HP_Status` | Idle / Heating / Defrost / Error | String |

### Poolsana InverPower Ultra — write

| Item | Description |
|---|---|
| `Pool_HP_Setpoint` | target water temperature |
| `Pool_HP_Mode` | Heat / Cool / Auto / Off |
| `Pool_HP_OnOff` | on / off |

## Rules (Phase 4)

In `rules/pool_modbus.rules`:

1. **Heat pump dry-run protection** — if `Pool_Filtering` is OFF, force
   `Pool_HP_OnOff` OFF; restore previous state when filter resumes.
2. **Salt unit dry-run protection** — analogous: `Pool_Filtering` OFF →
   `Pool_Salt_Mode` to Off (or production 0).
3. **Awattar coupling (optional)** — if current electricity price is below a
   threshold and pool target temperature not reached → enable heat pump.
   Concrete threshold + logic defined in Phase 4 against existing `Awattar.items`.
4. **Telegram alerts** — `Pool_Salt_FlowAlarm`, `Pool_Salt_LowSaltAlarm`,
   `Pool_HP_ErrorCode != 0` → message via existing Telegram bot.
5. **Connection watchdog** — Modbus TCP bridge OFFLINE → Telegram + log.

## UI

- Default equipment cards from the semantic model are sufficient through
  Phase 3.
- A custom OH5 dashboard widget is **optional** in Phase 4. If built, it follows
  the lessons captured in `feedback_oh5_widgets.md` (YAML quoting, card height
  stretching, canvas offset bug, expression limits, `.state` vs `.displayState`).

## Tools

- **Phase 1 validation:** `modpoll` (Windows binary) for register-by-register
  reads, or a short `pymodbus` script. No writes until Phase 3.
- **OpenHAB binding:** install Modbus binding via UI add-ons or
  `bundle:install` on the Karaf console.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Wrong register address on write damages device or sends bad setpoint | Phase 1 verifies every register read-side first; Phase 3 tests one setpoint at a time with echo-read confirmation |
| Poolsana register map is community-sourced and may be wrong | Treat all Poolsana addresses as unverified until confirmed by `modpoll` against the live device |
| RS485 wiring issues (no termination, ground loops) | Use 120 Ω termination at both ends; common GND; check signal with oscilloscope only if persistent comm errors |
| Modbus binding stalls one device when the other times out | Two separate TCP bridges (one per channel/port) isolate failures |
| Filter pump off while heat pump runs | Dry-run protection rule (Phase 4) |

## Out of Scope

- Replacing or removing the existing KNX `Pool_Salinator` switch (deferred
  decision — items run in parallel for now).
- Dosing pumps, UV sterilizer beyond existing on/off control.
- Energy metering / COP calculation (can be added later if registers expose it).
- Mobile-specific UI work.
