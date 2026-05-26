# BWM-Override via ITR508 Logic Gates — Design

**Date:** 2026-05-26
**Status:** Approved (concept). Implementation deferred — execute when time permits.
**Builds on:** [2026-05-22 KNX Motion Logic Redesign](2026-05-22-knx-motion-redesign-design.md). KNX-side migration is live; this spec adds a layer **above** it without rolling anything back.

## Problem

After the 2026-05-22 BWM migration, a regression surfaced: **when a BWM is in active motion phase and the user manually presses a wall button to turn off the light, the BWM's cyclic-Senden (every 10s) re-asserts the Aktor's Schalten input → light comes back on within seconds**. Wall button effectively bypassed.

Additionally: when the Sunset rule activates the Ambient scene (sets `0/0/3 = ON` → BWM Sperre), the Siemens UP 258 i-system BWM appears to not fully suppress an already-running cyclic-Senden cycle — at least under certain conditions reported by the user. The Sperre as designed should stop these telegrams; in practice it doesn't reliably during active motion.

Both issues have the same root cause: **once a BWM is in active phase, its cyclic-Senden overrides any external attempt to keep the light off** (until the BWM's own Nachlaufzeit ends, which can be 153–340 s depending on zone).

## Goal

Insert a controllable **gating layer** between the BWMs and the N567 Aktor. When the gate is closed, BWM telegrams are neutralised at the bus level — the Aktor sees no further motion signals regardless of how often the BWM cycles. Open the gate by default; close it on specific OpenHAB-driven events:

1. **Manual override** — user presses a wall button to turn off the light → disable gate for that zone for 5 minutes
2. **Ambient mode** — sunset rule activates Ambient → disable all corridor BWM gates (except when AwayMode is ON)

The gating is implemented in the existing **ITR508-16A** (Keller-Aktor, 1.1.10), which has four standalone Logic Gates with configurable AND/OR/XOR and up to 4 inputs each — enough for all three zones. No new hardware needed.

## In Scope

- Four new ITR508 logic gates (AND, 2 inputs each)
- Seven new Group Addresses (3 Enable, 4 gated motion)
- Re-link N567 Aktor inputs from raw BWM-GAs to gated GAs (Kanal C/a/D)
- New OpenHAB items + channels for the three Enable flags
- New OpenHAB rules: Manual-OFF detection, Ambient mode coupling, system-start defaults

## Out of Scope

- Replacing the Siemens UP 258 BWMs (long-term wish in [[knx-todo]])
- Changing the existing 2026-05-22 migration (Aktor Zeitschalter mode stays, BWM cyclic-Senden stays — the gating sits *above* this)
- Pool-Filter scheduler, AwayMode rules, lights.rules (untouched)

## Architecture

### Data flow (per zone)

```
BWM (e.g. VR GR 1.1.100)
  └── sends ON cyclically every 10s to:
        1/0/9  "Vorraum Bewegung BWM"
                  │
                  ├── OpenHAB Item Corridor_Motion_VR (for AwayMode-Telegram)
                  │
                  └── ITR508 Gate 1 input A
                                │
ITR508 Gate 1 input B ─── 1/0/13  "Vorraum BWM Enable" (OH-controlled, default ON)
                                │
ITR508 Gate 1 output (AND) ───► 1/0/19  "Vorraum BWM-VRGR gegated"
                                       │
                                       └── N567 Kanal C Schalten input
                                                  │
                                                  OR-Verknüpfung
                                                  with Verknüpfung input
                                                  (Eingangs-BWM via gate 2)
                                                  │
                                                  Zeitschalter (3 min)
                                                  │
                                                  ▼
                                          1/0/0 "Hauptlicht Vorraum"
```

When Enable=ON: gate is transparent (BWM telegram passes through).
When Enable=OFF: gate output stays at 0 regardless of BWM. Aktor sees no motion → light stays off.

### New Group Addresses

| GA | Name | DPT | Function |
|---|---|---|---|
| `1/0/13` | Vorraum BWM Enable | 1.001 | OH→ITR508 enable flag |
| `1/0/14` | Kl. Vorraum BWM Enable | 1.001 | OH→ITR508 enable flag |
| `1/0/15` | WC BWM Enable | 1.001 | OH→ITR508 enable flag |
| `1/0/19` | Vorraum BWM-VRGR gegated | 1.001 | ITR508 Gate 1 → N567 Kanal C Schalten |
| `1/0/20` | Vorraum BWM-Eingang gegated | 1.001 | ITR508 Gate 2 → N567 Kanal C Verknüpfung |
| `1/0/22` | Kl. Vorraum BWM gegated | 1.001 | ITR508 Gate 3 → N567 Kanal a Schalten |
| `1/0/23` | WC BWM gegated | 1.001 | ITR508 Gate 4 → N567 Kanal D Schalten |

Note: `1/0/21` is intentionally left as a gap (could be reserved for a future "all corridor BWMs enable" master flag).

### ITR508 Logic Gate configuration

All four gates: **AND, 2 inputs each, SendOn = Change of Output, Logic Value After Bus Return = ON** (fail-safe — if bus returns and enable flag hasn't been received yet, treat as enabled so BWMs work normally).

| Gate | Inputs | Output | Purpose |
|---|---|---|---|
| 1 | `1/0/9` (VR GR Motion) + `1/0/13` (Enable) | `1/0/19` | VR-GR BWM gated |
| 2 | `1/0/5` (Eingang Motion) + `1/0/13` (Enable) | `1/0/20` | Eingangs-BWM gated (shares Enable with VR GR) |
| 3 | `1/0/10` (Kl. Vorraum Motion) + `1/0/14` (Enable) | `1/0/22` | Kl. Vorraum BWM gated |
| 4 | `1/0/11` (WC Motion) + `1/0/15` (Enable) | `1/0/23` | WC BWM gated |

### N567 Aktor input re-linking

The Schalten and Verknüpfung inputs of Kanal C, a, D currently receive the raw BWM motion GAs. After the change they receive only the gated GAs.

| Kanal | Schalten — before | Schalten — after | Verknüpfung — before | Verknüpfung — after |
|---|---|---|---|---|
| C (Hauptvorraum) | `1/0/0`, `0/0/2`, `0/0/4`, `1/0/9` | `1/0/0`, `0/0/2`, `0/0/4`, **`1/0/19`** | `1/0/5` (OR-Modus) | **`1/0/20`** (OR-Modus) |
| a (Kl. Vorraum) | `1/0/2`, `0/0/2`, `0/0/4`, `1/0/10` | `1/0/2`, `0/0/2`, `0/0/4`, **`1/0/22`** | – | – |
| D (WC) | `1/4/0`, `0/0/2`, `0/0/4`, `1/0/11` | `1/4/0`, `0/0/2`, `0/0/4`, **`1/0/23`** | – | – |

**Wall buttons + scene addresses (`1/0/0`, `0/0/2`, `0/0/4` etc.) stay directly on Schalten** — they are not gated. Only the BWM-motion-GAs move to the gated path.

### OpenHAB-Seite

#### New things channels in `things/KNX_tunnel.things`

```xtend
// BWM Enable flags (1/0/13–15) — OH-gesteuert, gating der BWM-Telegrame via ITR508
// (Logic Gates 1–4). Default ON (BWMs aktiv). Siehe
// docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md
Type switch        : Vorraum_BWM_Enable                 "Enable"        [ga="1.001:1/0/13" ]
Type switch        : KlVorraum_BWM_Enable               "Enable"        [ga="1.001:1/0/14" ]
Type switch        : WC_BWM_Enable                      "Enable"        [ga="1.001:1/0/15" ]
```

The gated motion GAs (`1/0/19`, `1/0/20`, `1/0/22`, `1/0/23`) don't need OpenHAB items — they're internal to the KNX bus flow (ITR508 → N567).

#### New items in `items/bwm_override.items` (neu)

```xtend
// BWM Enable Flags — steuern die ITR508 Logic Gates die zwischen BWMs und
// N567 Aktor sitzen. Default ON (BWMs aktiv und triggern Lichter).
// Werden auf OFF gesetzt bei Wandtaster-Override (5 min) oder Ambient-Modus.
// Siehe docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md

Switch  Strasshof_Vorraum_BWM_Enable    "Vorraum BWM aktiv [%s]"        <if:mdi:motion-sensor>  (gMainCorridor, gKNX_CorridorLight)  ["Switch"]    {channel="knx:device:bridge:knx_main:Vorraum_BWM_Enable"}
Switch  Strasshof_KlVorraum_BWM_Enable  "Kl. Vorraum BWM aktiv [%s]"    <if:mdi:motion-sensor>  (gSmallCorridor)                       ["Switch"]    {channel="knx:device:bridge:knx_main:KlVorraum_BWM_Enable"}
Switch  Strasshof_WC_BWM_Enable         "WC BWM aktiv [%s]"             <if:mdi:motion-sensor>  (gWC)                                  ["Switch"]    {channel="knx:device:bridge:knx_main:WC_BWM_Enable"}
```

#### New rules in `rules/bwm_override.rules` (neu)

Vier Rules:

1. **System-Start defaults** — beim Startup alle Enables auf ON setzen
2. **Manual-OFF detection** — Licht geht OFF während Motion aktiv → Override 5 Min, zonen-spezifisch
3. **Ambient mode → disable** — Sunset-Trigger schaltet Enables off (außer AwayMode aktiv)
4. **Ambient mode off → re-enable** — Sunrise-Trigger schaltet zurück ON

Vollständige Code-Listings im Implementierungs-Plan.

### Detektions-Heuristik: "Manual OFF während Motion"

OpenHAB hat keinen direkten Weg zu wissen, ob ein `Corridor_Light → OFF` von einem Wandtaster, dem Aktor-Zeitschalter-Ablauf oder einer Szene kommt. Heuristik:

**Wenn `Corridor_Light` zu OFF wechselt UND ein zugehöriges Motion-Item (z.B. `gCorridor_Motion` oder `Corridor_Motion_VR`) ist gerade ON → muss extern getriggert sein** (Wandtaster, Szene, OH-Rule), denn:

- Aktor-Zeitschalter-Ablauf käme nicht zustande wenn BWM noch zyklisch retriggert
- Bei aktiver Bewegung sendet BWM alle 10s ON → Zeitschalter-Timer kann nicht ablaufen

Edge cases:
- **Szene 0/0/2 oder 0/0/4 ("Alle Lichter aus")**: würde als "Manual OFF" detektiert. Akzeptabel — bedeutet meist "User will explizit Ruhe", Override für 5 Min ist OK.
- **OpenHAB sendet OFF (z.B. dry-run-Protection oder lights-rules Midnight-Off)**: könnte False Positive auslösen. Mitigations:
  - Midnight-Off (00:00) — Motion ist um Mitternacht selten aktiv → Heuristik trifft selten falsch
  - AwayMode-Override würde sowieso die BWMs unsperren; im Override-Pfad ist's egal
- **Aktor-Zeitschalter läuft ab WÄHREND noch BWM-zyklisch-ON kommt**: technisch ungewöhnlich aber theoretisch möglich falls Zeitschalter-Timer kürzer als BWM-cycle (10s) ist. Mit 3-Min-Aktor-Timer und 10s-BWM-cycle nicht realistisch.

## Behavior matrix

| Zustand | Vorraum_BWM_Enable | BWM-Motion am Bus | Aktor-Input | Licht-Verhalten |
|---|---|---|---|---|
| **Normalbetrieb (Tag)** | ON | ggf. zyklisch ON | ON (via Gate) | BWM steuert Licht normal |
| **Normalbetrieb, User schaltet Wandtaster OFF** | ON → OFF (Override-Rule) | weiter zyklisch ON | OFF (Gate blockt) | Licht bleibt aus für 5 Min, danach automatisch wieder ON via Gate |
| **Ambient-Modus (Sonnenuntergang)** | OFF (Rule) | zyklisch ON wenn jemand vorbei läuft | OFF (Gate blockt) | Hauptlicht bleibt aus; nur Ambient-Lichter an |
| **Ambient + AwayMode** | ON (Rule überstimmt Ambient) | zyklisch ON | ON (Gate offen) | Bewegung triggert Licht UND Telegram-Alarm (gewollt für Anwesenheits-Simulation) |
| **AwayMode aktiv, kein Ambient** | ON | zyklisch ON | ON (Gate offen) | Wie Normalbetrieb plus Telegram-Alarm bei Bewegung |
| **OpenHAB offline (Stromausfall etc.)** | letzter Wert / Default ON | unverändert | wie Enable | Wenn Enable zuletzt auf ON war: BWMs arbeiten normal. Wenn auf OFF zum Zeitpunkt des Crashs: bleibt OFF bis manuell oder Bus-Reset (Default-After-Bus-Return = ON) |

## Acceptance criteria

1. Nach ETS-Programmierung des ITR508 (Gates 1–4) und N567 (Schalten/Verknüpfung relinkt): manuelles Senden von `1/0/13 = OFF` per ETS Group Monitor → Vorraum-Licht geht nicht mehr durch BWM-Trigger an, auch nicht durch zyklisches Senden. Wandtaster funktioniert normal (Schalten ist nicht gegatet).
2. Nach OH-Deploy: in der OH5 UI Switch `Strasshof_Vorraum_BWM_Enable` togglen → entsprechend reagiert das BWM-Gating.
3. Wandtaster-Walk-Test: vor BWM stehen → Licht an. Wandtaster drücken (OFF). Licht bleibt **aus**, auch wenn man weiter im BWM-Cone steht. Nach 5 Min: BWM wieder aktiv, Bewegung triggert Licht.
4. Ambient-Modus-Walk-Test: Sunset triggert Ambient → alle drei Enable-Items gehen auf OFF. Bewegung im Vorraum schaltet kein Hauptlicht mehr. AwayMode aktivieren → Enables gehen wieder ON (in dem Fall durch die AwayMode-Override-Rule).
5. AwayMode-Telegram-Test: `Corridor_Motion_VR` und `gCorridor_Motion` reagieren weiterhin auf BWM-Rohdaten (1/0/9), unabhängig vom Gating. Telegram-Alarm funktioniert wie vorher.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| ITR508 wurde seit 2017-03-26 nicht mehr programmiert (9 Jahre) | Vor Programmierung Projekt-Backup machen (`UnserHaus.knxproj` exportieren). Rollback ist eine ETS-Download-Aktion. Testen einer Programmier-Operation auf einem nicht-kritischen Kanal zuerst, falls Bedenken. |
| ITR508 hat nur 4 Logic Gates max — wir nutzen alle | Falls künftig weitere Zonen dazukommen (BWM in Bad, Küche, Keller etc.) muss eine alternative Logik genutzt werden (Per-Output-Logic des ITR508 selbst, oder zusätzlicher MDT Logikbaustein). Aktuell ausreichend. |
| Heuristik "Manual OFF während Motion" trifft Szenen | False positive bei "Alle Lichter aus"-Szene (5 Min Override) ist akzeptabel — User-Intent ist sowieso "Ruhe". |
| Falsch verlinktes Schalten-Objekt killt Wandtaster | Reihenfolge in ETS: zuerst neue GAs am Schalten/Verknüpfung **hinzufügen**, dann alte BWM-GA daraus **entfernen**. Nicht in einem Schritt überschreiben. Wandtaster-Test nach jeder Aktor-Programmierung. |
| OH-Server offline bei Sunset → kein Disable-Telegram | ITR508 Default-After-Bus-Return = ON → BWMs arbeiten normal. Worst case: Hauptlicht geht bei Bewegung tagsüber an obwohl Ambient eigentlich aktiv wäre. Akzeptabel und selbstheilend sobald OH zurück. |
| Override-Timer überlebt nicht OH-Restart | Acceptable. Bei OH-Restart fällt Enable auf default ON → BWMs aktiv. User merkt nur dass Override-Phase verkürzt war. |

## Open questions / future improvements

- **Per-Wandtaster-OFF Detection statt Heuristik**: derzeit unterscheiden wir Wandtaster-OFF nicht von Szene-OFF. Falls False-Positives nerven, könnte man eine eigene GA für "User drückt Wand-OFF" am Tastsensor 1.1.103 anlegen — separater Channel-Output, nur bei Tastendruck.
- **Konfigurierbare Override-Dauer** über ein OH-Number-Item (statt hardcoded 5 Min).
- **Override-Status anzeigen** in OH5-UI: ein Indicator-Icon wenn das Enable gerade auf OFF gepinnt ist.
- **Wenn künftig modernere BWMs eingebaut werden** (siehe knx-todo): das Gating bleibt nützlich als zentrale Override-Schnittstelle. Bei BWMs die Sperre korrekt umsetzen, könnte die Ambient-Coupling-Rule wegfallen, der Manual-Override bleibt nützlich.
