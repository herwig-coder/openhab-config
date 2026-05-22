# KNX Motion Logic Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate corridor + WC motion-detection from "BWM owns light timer + sends to light GA" to "BWM sends ON-pulses on dedicated motion GAs, N567 actuator holds one retriggerable staircase timer per zone".

**Architecture:** ETS reprogramming (one actuator, four BWMs) — all heavy lifting in KNX. OpenHAB-side: three new channels for `1/0/9–11`, three new items, one rule trigger swap, one channel deprecation. KNX three new GAs are already created in ETS (done 2026-05-22).

**Tech Stack:** ETS 6 (user runs), OpenHAB 4 KNX binding, Xtend rules DSL.

**Spec:** [docs/superpowers/specs/2026-05-22-knx-motion-redesign-design.md](../specs/2026-05-22-knx-motion-redesign-design.md)
**Hardware-detail reference:** `<personal-docs>/smart-home/knx-motion-logic.md`

**Conventions:**
- **[ETS]** — User runs in ETS. Cannot be done by an agent. Plan describes the change so user can verify it was done right.
- **[CFG]** — File edit in `openhab-config/` repo (agent-able).
- **[VERIFY]** — Observation step (logs, UI). Either side can do it; results gate progression.

---

## Phase 1 — N567 Actuator Reprogramming (ETS)

### Task 1 — Identify and prep the actuator channels [ETS]

**Files:** none in openhab-config — pure ETS work.

- [ ] **Step 1: Open `UnserHaus.knxproj` in ETS 6**

Topology view → device `1.1.2` (Siemens N 567/22, 16-fach Schaltaktor). This is the actuator that drives `1/0/0` (Hauptlicht Vorraum), `1/0/2` (Kleiner Vorraum), and `1/4/0` (Licht WC).

- [ ] **Step 2: Channel assignment (confirmed 2026-05-22)**

The N567 12-fach Schaltaktor enthält 12 Kanäle A–H + a–d. Folgende Zuordnung gilt:

| Zone | N567-Kanal | Licht-GA |
|---|---|---|
| Hauptvorraum | **C** | `1/0/0` Hauptlicht Vorraum |
| Kleiner Vorraum | **a** (Lowercase!) | `1/0/2` Kleiner Vorraum Hauptlicht |
| WC | **D** | `1/4/0` Licht WC |

Wichtig: Kanal "a" (klein) ist ein eigener Kanal, nicht zu verwechseln mit Kanal "A" (groß). Die Group-Object-Nummern im ETS unterscheiden sich (höhere Nummern für die Kleinbuchstaben-Kanäle).

- [ ] **Step 3: Note current parameters as rollback baseline**

For each of the three channels, before changing anything: open the parameter view, screenshot or note the current setting of `Nachtbetrieb`, `ON-time during night mode`, and any logic operations. This is your rollback reference.

### Task 2 — Switch each zone channel to Zeitschalter mode [ETS]

The N567 calls its staircase function **"Betriebsart = Zeitschalter"** (not "Nachtbetrieb"). Confirmed against actual UI on the user's Kanal C config screen (2026-05-22).

For each of the three zone channels (C, a, D):

- [ ] **Step 1: Set `Betriebsart` = Zeitschalter**

In the Parameter tab of the channel, find the `Betriebsart` setting. Default is `Normalbetrieb`. Change to `Zeitschalter`. New time-related parameters become visible after this change.

- [ ] **Step 2: Set the Einschaltdauer (ON-time)**

| Zone | Channel | Einschaltdauer |
|---|---|---|
| Hauptvorraum | C | 3 min |
| Kleiner Vorraum | a | 2 min |
| WC | D | 5 min |

- [ ] **Step 3: Set `Verknüpfung` per channel**

Verified against live UI (2026-05-22): N567/22 Zeitschalter mode does **not** expose explicit retrigger/manual-off parameters. Retrigger is default on (any new ON during running timer restarts it). Manual OFF aborts the timer.

| Channel | Verknüpfung-Funktion |
|---|---|
| C (Hauptvorraum) | **ODER-Verknüpfung** — required so the Verknüpfung-Objekt (with `1/0/9`) actually drives the output |
| a (Kl. Vorraum) | keine Verknüpfung (oder ODER — egal, wir nutzen Schalten für `1/0/10`) |
| D (WC) | keine Verknüpfung (egal, wir nutzen Schalten für `1/0/11`) |

⚠ **Wichtig zu wissen:** Der Wechsel `Betriebsart` von Normalbetrieb auf Zeitschalter setzt im N567/22 die `Verknüpfung`-Einstellung auf `keine Verknüpfung` zurück. Nach dem Umschalten auf Zeitschalter explizit wieder auf `ODER-Verknüpfung` setzen für Kanal C.

- [ ] **Step 4: Other channel parameters**

`Relaisbetrieb = Schließer` (Default), `Blinken vor Ausschalten = Nein` (oder Ja — Geschmackssache, optional Vorwarnung 30s vor Aus). `Einschaltverzögerung` und `Ausschaltverzögerung` bleiben `gesperrt`. Startwert nach Netzspannungswiederkehr bleibt `wie vor Spannungsausfall`.

### Task 3 — Link new motion GAs (mixed approach per channel) [ETS]

The N567's Verknüpfung-Funktion is already in use for Kanal C (OR-mode, with `1/0/5` from the Eingangs-BWM). We exploit this and use **different attachment points per channel**:

| Channel | New GA | Attach to | Why |
|---|---|---|---|
| Hauptvorraum (C) | `1/0/9` | **Verknüpfung-Objekt (Nr. 12)** — *replace* `1/0/5` | Existing OR-logic from old design; minimal change, cleanest semantic separation (Schalten = manual/scenes, Verknüpfung = motion) |
| Kl. Vorraum (a) | `1/0/10` | **Schalten-Objekt (Nr. 35)** — *add as additional listener* | No existing Verknüpfung setup; simpler to add to Schalten |
| WC (D) | `1/0/11` | **Schalten-Objekt (Nr. 15)** — *add as additional listener* | dito |

- [ ] **Step 1: Kanal C — Verknüpfung-Objekt (Nr. 12) update**

In the actuator's Group Objects view, find Nr. 12 "Verknüpfung, Kanal C". Currently linked to `1/0/5`. Remove `1/0/5`, drag `1/0/9` onto the object. Verknüpfungsfunktion-Parameter for Kanal C stays at "ODER (OR)". Schalten-Objekt (Nr. 11) stays untouched (`1/0/0`, `0/0/2`, `0/0/4`).

- [ ] **Step 2: Kanal a — Schalten-Objekt (Nr. 35) addition**

Currently linked: `1/0/2`, `0/0/2`, `0/0/4`. Add `1/0/10` as additional listener. Hauptadresse stays `1/0/2`.

- [ ] **Step 3: Kanal D — Schalten-Objekt (Nr. 15) addition**

Currently linked: `1/4/0`, `0/0/2`, `0/0/4`. Add `1/0/11` as additional listener. Hauptadresse stays `1/4/0`.

**Important:** all other linked GAs at all channels (especially `0/0/2`, `0/0/4` scene receivers) must stay — those are listeners for the "Alle aus" scenes that drive multiple channels.

### Task 4 — Download actuator + smoke-test with wall buttons [ETS][VERIFY]

⚠ **Übergangs-Stolperstein erwartet:** In dieser Phase haben die BWMs noch ihre alte Konfiguration. Wenn ein BWM während des Tests Bewegung erkennt, sendet er nach Ablauf seiner eigenen Nachlaufzeit (~60s default) `1/0/0 = OFF` — und das bricht den Zeitschalter-Timer des Aktors ab. Symptom: Licht geht nach ~60s aus statt nach den eingestellten 3 Min.

Saubere Test-Optionen:
- (a) **BWMs vor Test sperren:** `0/0/3 = ON` senden (Ambiente-Szene sperrt alle Vorraum-BWMs). Nach Test mit `0/0/2 = ON` wieder entsperren.
- (b) **Test verschieben** bis BWMs umkonfiguriert sind (Phase 2 vorziehen, dann gesamtsystem testen).



- [ ] **Step 1: ETS → Programmieren → Applikation only (not Adressen, not Alle)**

Reduces download time and avoids resetting unrelated parameters.

- [ ] **Step 2: Manual wall-button test per zone**

Press Hauptvorraum wall button → light comes on → after ~3 min light auto-off (with optional blink before).
Repeat for Kl. Vorraum (2 min) and WC (5 min).

If the timer doesn't auto-off: Nachtbetrieb is not actually enabled — revisit Task 2 (Step 4 fallback most likely needed).

- [ ] **Step 3: Retrigger test**

Switch on via wall button → wait 1 min → switch on again → timer should restart, total time on ≈ 1 min + Nachtbetrieb-Zeit.

**Gate:** Do not proceed to BWM reprogramming until this passes.

---

## Phase 2 — BWM Reprogramming (ETS)

Repeat the BWM procedure four times, **one device at a time**, with a verification step in between each. If something breaks, you only have one device misconfigured to roll back.

**Reihenfolge:** Vom Einfachen zum Komplexen. Erst Single-BWM-Zonen mit Schalten-Add (Kl. Vorraum 2-Min-Timer, WC 5-Min), dann die Hauptvorraum-Zone mit Verknüpfung-OR und zwei BWMs.

### Task 5 — Reconfigure VR KL Bewegungsmelder (1.1.102) [ETS]

Start hier — einfachste Konfig (Schalten-Add, 1 BWM, 2-Min-Timer = schneller Test-Zyklus). Wenn das funktioniert, ist das Pattern für WC + Hauptvorraum validiert.

- [ ] **Step 1: Open device `1.1.102` parameter view**

- [ ] **Step 2: Set the following parameters** (gilt sinngemäß für alle vier BWMs)

**Korrektur (2026-05-22):** Im App-Programm `211D-01` sind `Wert_Beginn` und `Wert_Ende` mit `Access="None"` hardcoded — wir können den BWM nicht stoppen, am Ende der Nachlaufzeit ein OFF zu schicken. Workaround: BWM-Nachlaufzeit länger als Aktor-Einschaltdauer setzen, damit der Aktor zuerst abläuft und der späte BWM-OFF ins Leere greift.

| Parameter | Wert (VR KL) | Begründung |
|---|---|---|
| Bewegungserfassung | unchanged (z.B. "bis Helligkeitswert 5 Lux") | Lichtschwelle hat eigenen Zweck (nur Trigger im Dunkel), nicht in diesem Redesign anfassen |
| Zyklisches Senden bei Erfassung | **freigegeben** | retriggert den Aktor-Zeitschalter während andauernder Bewegung |
| Zyklisches Senden Basis | Zeitbasis 1,0 sek | |
| Zyklisches Senden Faktor | 10 | alle 10s ein Retrigger — reicht für jede Zeitschalter-Einstellung |
| **Nachlaufzeit Basis** | **Zeitbasis 17 sek** | |
| **Nachlaufzeit Faktor** | **9** (= 153 s ≈ 2:33) | länger als Aktor-Einschaltdauer (2 Min) damit BWM-OFF zu spät kommt um Aktor-Timer abzubrechen |
| Totzeit nach Ende der Erfassung | Basis 130 ms × Faktor 0 = 0 (unchanged) | nicht relevant |
| Funktion des Sperrobjekts | "Aus = Betrieb, Ein = Sperrung aktiviert" (unchanged) | Sperre durch 0/0/3 funktioniert weiter |

**Nachlaufzeit-Tabelle für alle BWMs:** (Faustregel = Aktor-Zeit + ~30s Puffer)

| BWM | Aktor-Einschaltdauer | Nachlaufzeit Basis × Faktor | ≈ Sekunden |
|---|---|---|---|
| VR KL (1.1.102) | 2 min | 17 sek × 9 | 153 s |
| WC (1.1.101) | 5 min | 17 sek × 20 | 340 s |
| VR GR (1.1.100) | 3 min | 17 sek × 12 | 204 s |
| Vorraum Eingang (1.1.106) | 3 min | 17 sek × 12 | 204 s |

- [ ] **Step 3: Relink Schalten group object**

Currently: `Schalten` → `1/0/2` (Kleiner Vorraum Hauptlicht).
New: `Schalten` → `1/0/10`.
Remove `1/0/2`, add `1/0/10`. Verify `1/0/10` is the only GA on Schalten.

- [ ] **Step 4: Sperrung group object unchanged** — hört weiter auf `0/0/3`, `0/0/2`, `1/0/8`.

- [ ] **Step 5: Download device (Applikation only)**

- [ ] **Step 6: Walk-test**

Im Kleinen Vorraum vor BWM-Erfassungskegel laufen → in ETS Group Monitor `1/0/10 = ON` beobachten → Kleiner Vorraum Hauptlicht muss angehen → Bewegung beenden, ~2:30 stehen bleiben (außerhalb Erfassung) → Licht muss nach **exakt 2 Min Aktor-Timer** ausgehen, NICHT schon nach 30s (das wäre die alte BWM-Nachlaufzeit).

Diagnose:
- Licht kommt nicht: Schalten-Verlinkung auf `1/0/10` falsch / Kanal-a Zeitschalter nicht aktiv
- Licht geht zu früh aus (~30s): `Wert nach Ende der Erfassung` noch auf "Aus" → BWM sendet doch OFF
- Licht geht gar nicht aus: Aktor Kanal a noch im Normalbetrieb / Einschaltdauer nicht gesetzt

**Gate:** dieser Test muss sauber durchlaufen, bevor du mit Task 6 weitermachst.

### Task 6 — Reconfigure WC Bewegungsmelder (1.1.101) [ETS]

Selbes Pattern wie Task 5, längerer Timer.

- [ ] **Step 1: Open device `1.1.101` parameter view**

- [ ] **Step 2: Set parameters identical to Task 5 Step 2**

- [ ] **Step 3: Relink Schalten group object**

Currently: `Schalten` → `1/4/0` "Licht WC".
New: `Schalten` → `1/0/11`.

- [ ] **Step 4: Download + walk-test**

WC betreten → Licht muss kommen → WC verlassen, 5-6 Min warten → Licht muss nach genau 5 Min ausgehen.

### Task 7 — Reconfigure VR GR Bewegungsmelder (1.1.100) [ETS]

Erster der zwei Hauptvorraum-BWMs. Pattern wechselt: jetzt **Verknüpfung-OR** statt Schalten-Add, weil Kanal C diese Logik schon eingerichtet hat.

- [ ] **Step 1: Open device `1.1.100` parameter view**

- [ ] **Step 2: Set parameters identical to Task 5 Step 2**

- [ ] **Step 3: Relink Schalten group object**

Currently: `Schalten` → `1/0/0` (Hauptlicht Vorraum).
New: `Schalten` → `1/0/9` (Vorraum Bewegung BWM).
Remove `1/0/0`, add `1/0/9`. Verify `1/0/9` is the only GA on Schalten.

- [ ] **Step 4: Sperrung group object unchanged**

- [ ] **Step 5: Download + walk-test**

Vor VR GR-Erfassung laufen → `1/0/9 = ON` im Group Monitor → Hauptlicht Vorraum geht an (über Aktor Kanal C Verknüpfung-OR) → Timer 3 Min läuft → Licht aus.

Wenn das nicht klappt: Verknüpfung Kanal C steht ggf. nicht auf "ODER-Verknüpfung" oder `1/0/9` ist nicht auf Verknüpfung-Objekt (Nr. 12) verlinkt — siehe Phase 1 Task 3.

### Task 8 — Reconfigure Vorraum Eingang Bewegungsmelder (1.1.106) [ETS]

Zweiter Hauptvorraum-BWM. Validiert die OR-Fusion zwischen beiden BWMs.

- [ ] **Step 1: Open device `1.1.106` parameter view**

- [ ] **Step 2: Set parameters identical to Task 5 Step 2**

- [ ] **Step 3: Relink Schalten group object**

Currently: `Schalten` → `1/0/0` + `1/0/5`.
New: `Schalten` → `1/0/9` (entfernt beide alten Verlinkungen).
Damit wird `1/0/5` GA endgültig obsolet — Cleanup in Task 13.

- [ ] **Step 4: Download + walk-test single**

Eingangsbereich BWM-Cone → `1/0/9 = ON` → Hauptlicht an → 3 Min → aus.

- [ ] **Step 5: Combined retrigger test (der echte Härtetest)**

Vor VR GR bewegen → Licht an, Timer läuft. Nach 2 Min zum Eingang gehen, Eingangs-BWM triggern → Aktor empfängt neues ON auf `1/0/9` → Timer **startet neu** (retriggerbar) → Licht bleibt insgesamt 2 + 3 = 5 Min an, NICHT vorzeitig aus, NICHT flackernd.

Das ist die ursprüngliche Anforderung "Bewegung von beliebigem Sensor → Licht an, Nachlauf nach letzter Bewegung von irgendeinem Sensor". Wenn das durchläuft, ist das Re-Design technisch verifiziert.

**Gate:** All four BWMs reprogrammed and individually tested. Now also run the **Sperre-Test** for all of them:
1. Send `0/0/3` = ON (e.g. via OH `Strasshof_AmbientLight_On`)
2. Walk in front of any BWM → no light should come on (BWM locked)
3. Send `0/0/2` = ON (`Strasshof_AllLights_Off`) → BWMs unlocked
4. Walk again → light comes on

---

## Phase 3 — OpenHAB: Expose Motion GAs

### Task 9 — Add KNX channels for the three motion GAs [CFG]

**Files:**
- Modify: `things/KNX_tunnel.things` (after line 82, near existing corridor lock channels)

- [ ] **Step 1: Read current things file around the corridor lock section**

```bash
grep -n "Corridor_lights_lock_Motion" things/KNX_tunnel.things
```

Expected: lines 81–82 with the two existing lock channels.

- [ ] **Step 2: Append the three new motion channels**

After the line containing `Corridor_lights_lock_Motion`, add:

```xtend
        // Bewegungs-Trigger der Vorraum- und WC-BWMs (neu 2026-05-22).
        // BWMs senden hier ON-Pulse; N567-Aktor läuft im Nachtbetrieb und
        // hält den retriggerbaren Timer pro Zone. Siehe
        // docs/superpowers/specs/2026-05-22-knx-motion-redesign-design.md
        Type switch        : Corridor_Motion                    "Motion"        [ga="1.001:1/0/9" ]
        Type switch        : SmallCorridor_Motion               "Motion"        [ga="1.001:1/0/10" ]
        Type switch        : WC_Motion                          "Motion"        [ga="1.001:1/0/11" ]
```

- [ ] **Step 3: Verify file still parses**

Push the change to git and pull on the server. Then tail openhab.log:

```bash
git add things/KNX_tunnel.things
git commit -m "add: knx channels for vorraum + wc motion ga (1/0/9-11)"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
ssh herwig@10.1.100.101 'sudo tail -30 /var/log/openhab/openhab.log | grep -iE "KNX|error|exception"'
```

Expected: no parse errors related to KNX_tunnel.things. Existing channels still loaded.

### Task 10 — Add motion items [CFG]

**Files:**
- Create: `items/motion.items`

- [ ] **Step 1: Verify `gWC` exists in semantic model**

```bash
grep -n "gWC " items/semantic_model.items
```

Expected: line 33 (or wherever) defines `gWC`. If missing, add as part of this task.

- [ ] **Step 2: Create `items/motion.items`**

```xtend
// Bewegungs-Status-Items für Vorraum + WC. Empfangen ON-Pulse von den
// KNX-Bewegungsmeldern (siehe docs/superpowers/specs/2026-05-22-knx-motion-redesign-design.md).
// Verwendung: AwayMode-Telegram-Alarm, künftig auch Präsenz-abhängige Logik.

Switch  Corridor_Motion       "Vorraum Bewegung [%s]"          <if:mdi:motion-sensor>  (gMainCorridor)   ["Status","Presence"]  {channel="knx:device:bridge:knx_main:Corridor_Motion"}
Switch  SmallCorridor_Motion  "Kleiner Vorraum Bewegung [%s]"  <if:mdi:motion-sensor>  (gSmallCorridor)  ["Status","Presence"]  {channel="knx:device:bridge:knx_main:SmallCorridor_Motion"}
Switch  WC_Motion             "WC Bewegung [%s]"               <if:mdi:motion-sensor>  (gWC)             ["Status","Presence"]  {channel="knx:device:bridge:knx_main:WC_Motion"}
```

- [ ] **Step 3: Deploy and verify items show up**

```bash
git add items/motion.items
git commit -m "add: motion items for vorraum + wc (linked to 1/0/9-11)"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

OH5 UI → Items → search "Motion" — should see the three new items, each linked to one channel.

### Task 11 — Verify motion events arrive [VERIFY]

- [ ] **Step 1: Tail events.log**

```bash
ssh herwig@10.1.100.101 'sudo tail -f /var/log/openhab/events.log'
```

- [ ] **Step 2: Walk past each BWM in turn**

Expected event sequence per walk:
```
Item 'Corridor_Motion' received command ON          (or similar — depends on KNX binding semantics)
Item 'Corridor_Motion' predicted to become ON
Item 'Corridor_Motion' changed from OFF to ON
```

And after a minute (cyclic re-send from BWM):
```
Item 'Corridor_Motion' received update ON
```

After motion stops + BWM Nachlaufzeit: no further events (BWM does not send OFF).

- [ ] **Step 3: If no events arrive**

- Confirm `1/0/9` traffic in ETS Group Monitor first (rules out KNX wiring issue)
- If telegrams on bus but not in OH: channel name in items file ≠ name in things file. Grep both.

**Gate:** All three motion items produce `changed to ON` events when their respective BWMs trigger. Don't proceed to AwayMode rewiring before this works.

---

## Phase 4 — OpenHAB: Rewire AwayMode Rule

### Task 12 — Swap AwayMode R3 trigger from Corridor_Light to Corridor_Motion [CFG]

**Files:**
- Modify: `rules/awaymode.rules`

- [ ] **Step 1: Locate R3**

```bash
grep -n "corridor motion alarm" rules/awaymode.rules
```

Expected: somewhere around line 41 ("AwayMode: corridor motion alarm").

- [ ] **Step 2: Edit the rule**

Change the `when` block from:

```xtend
rule "AwayMode: corridor motion alarm"
when
    Item Corridor_Light changed to ON
then
```

to:

```xtend
rule "AwayMode: corridor motion alarm"
when
    Item Corridor_Motion changed to ON
then
```

Also update the message text inside the rule body for clarity:

```xtend
    val message = "🚨 Bewegung erkannt im Vorraum (BWM) während Abwesenheit: " + now
```

(Previously said "Bewegung im Vorraum" generically — now we know it's the BWM channel, not manual switching.)

- [ ] **Step 3: Deploy and test**

```bash
git add rules/awaymode.rules
git commit -m "fix: awaymode rule triggers on Corridor_Motion not Corridor_Light"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

- [ ] **Step 4: End-to-end AwayMode test**

1. Switch `Strasshof_AwayMode` to ON in OH5 UI.
2. Walk past VR GR or Eingangs-BWM.
3. Telegram arrives within seconds with the new message text.
4. Switch off AwayMode.
5. Walk again → no Telegram (rule guards on `state == ON`).

- [ ] **Step 5: Confirm manual switching does NOT trigger Telegram anymore**

With AwayMode ON: press a Vorraum wall button to switch Corridor_Light → no Telegram (because rule no longer reacts to Corridor_Light). This is the **intentional improvement** — the new signal is cleaner.

If you actually want manual switching to also alarm during away mode, that's a follow-up scope decision; mention to operator if observed.

**Gate:** AwayMode end-to-end test passes with the new motion item.

---

## Phase 5 — Cleanup

### Task 13 — Deprecate Corridor_lights_lock_Motion_Entry channel [CFG]

**Files:**
- Modify: `things/KNX_tunnel.things` (remove the obsolete channel line)

After ETS migration, `1/0/5` carries no traffic anymore — Vorraum Eingangs-BWM sends on `1/0/9` instead.

- [ ] **Step 1: Confirm no item references the channel**

```bash
grep -n "Corridor_lights_lock_Motion_Entry" items/
```

Expected: no matches (this channel never had an item bound to it).

- [ ] **Step 2: Remove the channel line**

In `things/KNX_tunnel.things`, delete:

```xtend
        Type switch        : Corridor_lights_lock_Motion_Entry  "Light"         [ga="1.001:1/0/5" ]
```

- [ ] **Step 3: Verify no error after reload**

```bash
git add things/KNX_tunnel.things
git commit -m "remove: obsolete Corridor_lights_lock_Motion_Entry channel (1/0/5 unused post-migration)"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
ssh herwig@10.1.100.101 'sudo tail -30 /var/log/openhab/openhab.log | grep -iE "knx|error"'
```

Expected: no errors mentioning a missing channel. KNX bridge stays ONLINE.

### Task 14 — Verify lights.rules unaffected [VERIFY]

The existing AwayMode-guard added to `rules/lights.rules` (the sunset trigger that skips when AwayMode==ON) is unchanged by this migration. Just confirm it still works:

- [ ] **Step 1: With AwayMode == OFF, advance to a sunset event**

Either wait for actual sunset or manually set `Strasshof_SunPhase` to `SUN_SET` in OH UI. The "Ambient Light" rule should fire and send `Strasshof_AmbientLight_On` = ON, which locks BWMs (no light on motion). Logs confirm.

- [ ] **Step 2: With AwayMode == ON, advance sunset again**

Rule should log `Sunset — übersprungen (AwayMode aktiv, würde BWMs sperren)` and not lock the BWMs. Motion still triggers light + Telegram.

- [ ] **Step 3: No commit needed unless something broke**

If lights.rules needed adjustment, commit:

```bash
git add rules/lights.rules
git commit -m "fix: any lights.rules adjustment for motion redesign"
```

---

## Self-Review (run after writing — done)

- [x] **Spec coverage:**
  - New channels in things — Task 9 ✓
  - New items — Task 10 ✓
  - AwayMode rule rewire — Task 12 ✓
  - Channel deprecation — Task 13 ✓
  - Acceptance criteria mapped to verification gates ✓
- [x] **Placeholder scan:**
  - The "Force Nachtbetrieb dauerhaft EIN" step in Task 2.4 lists two options — that's a real conditional, not a placeholder. Engineer picks based on what the actuator UI exposes.
  - Address `1/4/0` for WC light is marked "confirm address in ETS" — true uncertainty (extracted from raw .knxproj; final verification on the device is appropriate).
- [x] **Type consistency:** Item names `Corridor_Motion`, `SmallCorridor_Motion`, `WC_Motion` used consistently from Task 10 onwards. Channel names `Corridor_Motion`, `SmallCorridor_Motion`, `WC_Motion` match between Task 9 and Task 10. `Strasshof_AwayMode` and `Strasshof_AmbientLight_On` referenced from existing files (already exist).
