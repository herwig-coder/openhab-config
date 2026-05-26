# BWM Override via ITR508 Logic Gates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a controllable gating layer between the four corridor/WC BWMs and the N567 Aktor by using the ITR508-16A's four standalone Logic Gates. Solves the BWM-cyclic-Senden-overrides-wall-button regression plus the unreliable Ambient-Sperre on Siemens UP 258 BWMs.

**Architecture:** ITR508 logic gates (AND, 2 inputs each: raw BWM motion GA + Enable flag) produce gated motion GAs. N567 reads gated GAs instead of raw. OpenHAB controls the Enable flags via three new switch items, with rules for manual-override (5 min) and Ambient-mode coupling.

**Tech Stack:** ETS 6 (user runs), ITR508 logic gates, N567 input re-linking, OpenHAB 4 KNX binding, Xtend rules DSL.

**Spec:** [docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md](../specs/2026-05-26-bwm-override-via-itr508-design.md)
**Builds on:** [docs/superpowers/plans/2026-05-22-knx-motion-redesign.md](2026-05-22-knx-motion-redesign.md) (must be complete first — it is, since 2026-05-22)

**Conventions:**
- **[ETS]** — User runs in ETS. Not agent-doable. Plan describes the change so user can verify it.
- **[CFG]** — File edit in `openhab-config/` repo (agent-able via subagent).
- **[VERIFY]** — Observation step (logs, OH5 UI, KNX Group Monitor).

---

## Phase 1 — ETS preparation (USER)

### Task 1 — Export current `UnserHaus.knxproj` as rollback baseline [ETS]

- [ ] **Step 1: ETS → Datei → Exportieren → Projekt-Backup**

Speichere unter `openhab-config/docs/knx/UnserHaus-pre-bwm-override-2026-MM-DD.knxproj`. Gitignored, dient als Rollback wenn die ITR508-Programmierung schiefgeht.

- [ ] **Step 2: Bestätigen dass der ITR508 (1.1.10) erreichbar ist**

ETS → Topologie → 1.1.10 → Rechtsklick → "Read individual address". Sollte erfolgreich sein. Falls Timeout oder Fehler: Aktor offline (Sicherung im Keller-Verteiler prüfen) oder Linie-Koppler-Filter blockiert das Telegramm.

### Task 2 — Neue Group Addresses anlegen [ETS]

Im KNX-Bereich `1/0/x` (Vorräume Gänge):

- [ ] **Step 1: Sieben neue GAs erstellen**

| GA | Name | DPT |
|---|---|---|
| `1/0/13` | `Vorraum BWM Enable` | 1.001 (Switch) |
| `1/0/14` | `Kl. Vorraum BWM Enable` | 1.001 |
| `1/0/15` | `WC BWM Enable` | 1.001 |
| `1/0/19` | `Vorraum BWM-VRGR gegated` | 1.001 |
| `1/0/20` | `Vorraum BWM-Eingang gegated` | 1.001 |
| `1/0/22` | `Kl. Vorraum BWM gegated` | 1.001 |
| `1/0/23` | `WC BWM gegated` | 1.001 |

`1/0/21` bewusst frei lassen (Reserve für künftige "Master Enable" GA).

- [ ] **Step 2: GAs noch nicht verlinken** — kommen in Task 3 und 4 dran.

---

## Phase 2 — ITR508 Logic Gates (USER, ETS)

### Task 3 — ITR508 Logic Gates konfigurieren [ETS]

ETS → Aktor `1.1.10` (ITR Keller Aktor 8x16A) → Parameter-Tab.

- [ ] **Step 1: Logic Gate Count = 4**

Im "Allgemein"-Block (oder vergleichbar) Parameter `Logic Gate Count` auf **4 Logic Gates** setzen. Damit erscheinen die vier Gate-Konfigurations-Bereiche.

- [ ] **Step 2: Gate 1 — Vorraum VR GR**

| Parameter | Wert |
|---|---|
| Logic Type | AND |
| Number of Inputs | 2 Inputs |
| Send On | Change of Output |
| Logic Value After Bus Return | TRUE (= 1, BWMs aktiv per Default) |
| Logic Value After ETS Programming | TRUE |

Group Object-Verlinkungen (im Tab "Kommunikationsobjekte" nach der Param-Konfig):
- **Gate 1 Input 1** ← `1/0/9` (Vorraum Bewegung BWM)
- **Gate 1 Input 2** ← `1/0/13` (Vorraum BWM Enable)
- **Gate 1 Output** → `1/0/19` (Vorraum BWM-VRGR gegated)

- [ ] **Step 3: Gate 2 — Vorraum Eingangs-BWM**

Selbe Parameter wie Gate 1. Verlinkungen:
- **Gate 2 Input 1** ← `1/0/5` (Vorraum Hauptlicht Eingang BWM — Schalt-Output des Eingangs-BWMs)
- **Gate 2 Input 2** ← `1/0/13` (Vorraum BWM Enable — gleicher Enable wie Gate 1)
- **Gate 2 Output** → `1/0/20` (Vorraum BWM-Eingang gegated)

- [ ] **Step 4: Gate 3 — Kleiner Vorraum**

- **Gate 3 Input 1** ← `1/0/10` (Kl. Vorraum Bewegung BWM)
- **Gate 3 Input 2** ← `1/0/14` (Kl. Vorraum BWM Enable)
- **Gate 3 Output** → `1/0/22` (Kl. Vorraum BWM gegated)

- [ ] **Step 5: Gate 4 — WC**

- **Gate 4 Input 1** ← `1/0/11` (WC Bewegung BWM)
- **Gate 4 Input 2** ← `1/0/15` (WC BWM Enable)
- **Gate 4 Output** → `1/0/23` (WC BWM gegated)

- [ ] **Step 6: ITR508 programmieren (Applikation)**

ETS → Aktor `1.1.10` → "Applikation programmieren". Dauer ~1-2 Min (Aktor war 9 Jahre nicht reprogrammiert).

⚠ **Vorsicht:** Bei Problemen während des Downloads (Bus-Timeout, Schreibfehler) sofort das Backup aus Task 1 zurückspielen. Der Aktor steuert das Keller-Bad, Dampfbad und Lüftung — wenn er bricht, geht das Keller-Lichtsetup nicht mehr.

### Task 4 — Smoke-Test Gates ohne N567-Änderung [ETS][VERIFY]

Bevor wir den N567 umkonfigurieren, testen wir dass die Gates funktionieren.

- [ ] **Step 1: ETS Group Monitor öffnen**

- [ ] **Step 2: Test Gate 1 (Vorraum VR GR)**

In Group Monitor manuell senden:
1. `1/0/13 = 1` (Enable ON) — Gate-Output sollte folgendem Input folgen
2. `1/0/9 = 1` (BWM Motion ON) → erwarten: `1/0/19 = 1` (gate output ON) auf dem Bus zu sehen
3. `1/0/13 = 0` (Enable OFF) → erwarten: `1/0/19 = 0` (gate output OFF — durch AND-Bedingung)
4. `1/0/9 = 0` und `1/0/13 = 1` → erwarten: `1/0/19 = 0` (immer noch — BWM-Input ist 0)
5. `1/0/9 = 1` und `1/0/13 = 1` → erwarten: `1/0/19 = 1`

- [ ] **Step 3: Test Gate 2, 3, 4 analog**

Tests sind kurz — wenn Gate 1 funktioniert, sind die anderen mit hoher Wahrscheinlichkeit auch OK (identische Konfig, anderer Input-GA).

**Gate:** Alle vier Gates verifiziert bevor die N567-Umkonfiguration kommt.

---

## Phase 3 — N567 Aktor input re-linking (USER, ETS)

### Task 5 — N567 Kanal C — Schalten + Verknüpfung umverdrahten [ETS]

ETS → Aktor `1.1.2` (N567/22) → Kommunikationsobjekte-Tab.

- [ ] **Step 1: Schalten Kanal C (Nr. 11) — `1/0/19` hinzufügen, `1/0/9` entfernen**

Aktuelle Belegung: `1/0/0`, `0/0/2`, `0/0/4`, `1/0/9`

Reihenfolge der Operationen (wichtig — niemals Hauptadresse `1/0/0` verlieren):
1. `1/0/19` **hinzufügen** als zusätzlicher Listener
2. `1/0/9` **entfernen** aus der Liste

Endzustand: `1/0/0`, `0/0/2`, `0/0/4`, `1/0/19`. Hauptadresse bleibt `1/0/0`.

- [ ] **Step 2: Verknüpfung Kanal C (Nr. 12) — `1/0/20` ersetzt `1/0/5`**

Aktuelle Belegung: `1/0/5` (alleinige GA). Verknüpfungs-Funktion: ODER (bleibt).

1. `1/0/20` **hinzufügen**
2. `1/0/5` **entfernen**

Endzustand: `1/0/20`. ODER-Modus bleibt.

### Task 6 — N567 Kanal a (Kleiner Vorraum) und Kanal D (WC) [ETS]

- [ ] **Step 1: Schalten Kanal a (Nr. 35) — `1/0/22` hinzufügen, `1/0/10` entfernen**

Aktuelle Belegung: `1/0/2`, `0/0/2`, `0/0/4`, `1/0/10`. Endzustand: `1/0/2`, `0/0/2`, `0/0/4`, `1/0/22`.

- [ ] **Step 2: Schalten Kanal D (Nr. 15) — `1/0/23` hinzufügen, `1/0/11` entfernen**

Aktuelle Belegung: `1/4/0`, `0/0/2`, `0/0/4`, `1/0/11`. Endzustand: `1/4/0`, `0/0/2`, `0/0/4`, `1/0/23`.

### Task 7 — N567 programmieren [ETS]

- [ ] **Step 1: Applikation programmieren**

ETS → `1.1.2` → "Applikation programmieren". Bei Erfolg: alle drei Vorraum-Kanäle und WC empfangen jetzt von den gegateten GAs.

### Task 8 — End-to-end Walk-Test [ETS][VERIFY]

Mit der Enable-Logik noch nicht in OpenHAB → manuelles Setzen der Enable-Flags via Group Monitor:

- [ ] **Step 1: Standard-Betrieb (Enable = ON)**

`1/0/13 = 1`, `1/0/14 = 1`, `1/0/15 = 1` senden. Walk-Test in jeder Zone:
- Vorraum: bewegen → Hauptlicht muss anspringen, Zeitschalter 3 Min läuft
- Kl. Vorraum: bewegen → Licht an, 2 Min Timer
- WC: bewegen → Licht an, 5 Min Timer

Wenn das nicht passt: N567-Verlinkung in Task 5/6 prüfen.

- [ ] **Step 2: Override-Simulation (Enable = OFF)**

Während du im Vorraum vor dem BWM stehst (Licht ist an): `1/0/13 = 0` senden.

Erwartung: Licht geht aus, bleibt aus auch wenn du weiter im Cone bist. Zyklisches Senden vom BWM (1/0/9 = ON alle 10s) kommt zwar weiterhin auf dem Bus an, der Gate-Output `1/0/19` bleibt aber bei 0 → N567 Schalten-State bleibt 0 → Licht aus.

Wandtaster für Hauptlicht drücken (sollte direkt auf `1/0/0` schreiben): Licht kann manuell wieder eingeschaltet werden, weil Wandtaster nicht durch Gate läuft. Bei Wand-OFF → Licht aus.

- [ ] **Step 3: Re-enable**

`1/0/13 = 1` senden. Falls noch Bewegung detektiert wird, springt das Licht beim nächsten zyklisches Senden (max. 10 s später) wieder an.

**Gate:** Die ETS-Phase ist erfolgreich, wenn alle drei Zonen sowohl mit Enable=ON wie auch mit Enable=OFF korrekt reagieren.

---

## Phase 4 — OpenHAB Integration (AGENT/CFG)

### Task 9 — KNX-Channels für die Enable-Flags ergänzen [CFG]

**Files:**
- Modify: `things/KNX_tunnel.things`

- [ ] **Step 1: Drei neue Channels einfügen** (nach den bestehenden Motion-Channels von 2026-05-22):

```xtend
        // BWM Enable flags (1/0/13–15) — OH-gesteuert, gating der BWM-Telegrame
        // via ITR508 Logic Gates 1–4. Default ON (BWMs aktiv). Siehe
        // docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md
        Type switch        : Vorraum_BWM_Enable                 "Enable"        [ga="1.001:1/0/13" ]
        Type switch        : KlVorraum_BWM_Enable               "Enable"        [ga="1.001:1/0/14" ]
        Type switch        : WC_BWM_Enable                      "Enable"        [ga="1.001:1/0/15" ]
```

- [ ] **Step 2: Commit**

```bash
git add things/KNX_tunnel.things
git commit -m "knx: bwm enable channels for itr508 gating override"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
ssh herwig@10.1.100.101 'sudo tail -30 /var/log/openhab/openhab.log | grep -iE "knx|error"'
```

Expected: keine Parse-Fehler.

### Task 10 — Items für die Enable-Flags [CFG]

**Files:**
- Create: `items/bwm_override.items`

- [ ] **Step 1: Datei mit drei Switch-Items erstellen**

```xtend
// BWM Enable Flags — steuern die ITR508 Logic Gates die zwischen BWMs und
// N567 Aktor sitzen. Default ON (BWMs aktiv und triggern Lichter).
// Werden auf OFF gesetzt bei Wandtaster-Override (5 min) oder Ambient-Modus.
// Siehe docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md

Switch  Strasshof_Vorraum_BWM_Enable    "Vorraum BWM aktiv [%s]"        <if:mdi:motion-sensor>  (gMainCorridor, gKNX_CorridorLight)  ["Switch"]    {channel="knx:device:bridge:knx_main:Vorraum_BWM_Enable"}
Switch  Strasshof_KlVorraum_BWM_Enable  "Kl. Vorraum BWM aktiv [%s]"    <if:mdi:motion-sensor>  (gSmallCorridor)                       ["Switch"]    {channel="knx:device:bridge:knx_main:KlVorraum_BWM_Enable"}
Switch  Strasshof_WC_BWM_Enable         "WC BWM aktiv [%s]"             <if:mdi:motion-sensor>  (gWC)                                  ["Switch"]    {channel="knx:device:bridge:knx_main:WC_BWM_Enable"}
```

- [ ] **Step 2: Commit + deploy**

```bash
git add items/bwm_override.items
git commit -m "add: bwm enable items for vorraum + kl vorraum + wc"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

OH5 UI → Settings → Items → search "BWM aktiv" — drei neue Items sichtbar.

### Task 11 — Rules für Override-Logik [CFG]

**Files:**
- Create: `rules/bwm_override.rules`

- [ ] **Step 1: Datei mit vier Rules erstellen**

```xtend
// BWM-Override-Rules — steuern die ITR508-Gates die zwischen BWMs und Aktor sitzen.
// Siehe docs/superpowers/specs/2026-05-26-bwm-override-via-itr508-design.md

var Timer corridorOverrideTimer = null
var Timer klVorraumOverrideTimer = null
var Timer wcOverrideTimer = null

// --- R1: System start → BWMs immer auf ON setzen -----------------------
rule "BWM Enable: defaults on system start"
when
    System started
then
    logInfo("BWM-Override", "System started — BWMs enabled (default state)")
    Strasshof_Vorraum_BWM_Enable.sendCommand(ON)
    Strasshof_KlVorraum_BWM_Enable.sendCommand(ON)
    Strasshof_WC_BWM_Enable.sendCommand(ON)
end

// --- R2: Hauptvorraum Wandtaster-Override -------------------------------
// Heuristik: Licht geht OFF während gCorridor_Motion aktiv → externe Quelle
// (Wandtaster, Szene). BWM Enable für 5 min auf OFF.
rule "Manual OFF in Hauptvorraum → disable BWM for 5 min"
when
    Item Corridor_Light changed to OFF
then
    if (gCorridor_Motion.state != ON) {
        // Normaler Zeitschalter-Ablauf, nicht manuell — kein Override
        return;
    }
    if (Strasshof_AwayMode.state == ON) {
        // Im AwayMode wollen wir BWMs aktiv halten für Telegram-Alarm
        return;
    }
    logInfo("BWM-Override", "Manual OFF im Hauptvorraum erkannt — BWM disabled für 5 min")
    Strasshof_Vorraum_BWM_Enable.sendCommand(OFF)
    if (corridorOverrideTimer !== null) corridorOverrideTimer.cancel()
    corridorOverrideTimer = createTimer(now.plusMinutes(5)) [|
        Strasshof_Vorraum_BWM_Enable.sendCommand(ON)
        logInfo("BWM-Override", "Hauptvorraum override expired — BWM re-enabled")
        corridorOverrideTimer = null
    ]
end

// --- R3: Kleiner Vorraum Wandtaster-Override ---------------------------
rule "Manual OFF in Kl. Vorraum → disable BWM for 5 min"
when
    Item SmallCorridor_Light changed to OFF
then
    if (SmallCorridor_Motion.state != ON) return;
    if (Strasshof_AwayMode.state == ON) return;
    logInfo("BWM-Override", "Manual OFF im Kl. Vorraum erkannt — BWM disabled für 5 min")
    Strasshof_KlVorraum_BWM_Enable.sendCommand(OFF)
    if (klVorraumOverrideTimer !== null) klVorraumOverrideTimer.cancel()
    klVorraumOverrideTimer = createTimer(now.plusMinutes(5)) [|
        Strasshof_KlVorraum_BWM_Enable.sendCommand(ON)
        logInfo("BWM-Override", "Kl. Vorraum override expired — BWM re-enabled")
        klVorraumOverrideTimer = null
    ]
end

// --- R4: WC Wandtaster-Override ----------------------------------------
rule "Manual OFF in WC → disable BWM for 5 min"
when
    Item WC_Light changed to OFF
then
    if (WC_Motion.state != ON) return;
    if (Strasshof_AwayMode.state == ON) return;
    logInfo("BWM-Override", "Manual OFF im WC erkannt — BWM disabled für 5 min")
    Strasshof_WC_BWM_Enable.sendCommand(OFF)
    if (wcOverrideTimer !== null) wcOverrideTimer.cancel()
    wcOverrideTimer = createTimer(now.plusMinutes(5)) [|
        Strasshof_WC_BWM_Enable.sendCommand(ON)
        logInfo("BWM-Override", "WC override expired — BWM re-enabled")
        wcOverrideTimer = null
    ]
end

// --- R5: Ambient-Modus → BWMs deaktivieren -----------------------------
rule "Ambient mode active → disable all BWMs"
when
    Item Strasshof_AmbientLight_On changed to ON
then
    if (Strasshof_AwayMode.state == ON) {
        // AwayMode hat Priorität — BWMs bleiben aktiv für Alarm-Logik
        logInfo("BWM-Override", "Ambient activated, aber AwayMode aktiv — BWMs bleiben ON")
        return;
    }
    logInfo("BWM-Override", "Ambient mode aktiviert — alle BWMs disabled")
    Strasshof_Vorraum_BWM_Enable.sendCommand(OFF)
    Strasshof_KlVorraum_BWM_Enable.sendCommand(OFF)
    Strasshof_WC_BWM_Enable.sendCommand(OFF)
end

// --- R6: Ambient-Modus aus → BWMs wieder aktivieren --------------------
rule "Ambient mode off → re-enable all BWMs"
when
    Item Strasshof_AmbientLight_On changed to OFF
then
    logInfo("BWM-Override", "Ambient mode deaktiviert — alle BWMs re-enabled")
    Strasshof_Vorraum_BWM_Enable.sendCommand(ON)
    Strasshof_KlVorraum_BWM_Enable.sendCommand(ON)
    Strasshof_WC_BWM_Enable.sendCommand(ON)
end

// --- R7: AwayMode aktiviert → BWMs aktivieren (überschreibt Ambient) ---
rule "AwayMode active → ensure BWMs enabled"
when
    Item Strasshof_AwayMode changed to ON
then
    logInfo("BWM-Override", "AwayMode aktiviert — alle BWMs ON (überschreibt Ambient falls aktiv)")
    Strasshof_Vorraum_BWM_Enable.sendCommand(ON)
    Strasshof_KlVorraum_BWM_Enable.sendCommand(ON)
    Strasshof_WC_BWM_Enable.sendCommand(ON)
end
```

- [ ] **Step 2: Item `SmallCorridor_Light` und `WC_Light` verifizieren**

```bash
grep -nE "^Switch +SmallCorridor_Light|^Switch +WC_Light" items/
```

Wenn `WC_Light` nicht existiert: ist evtl. noch nicht in items/knx.items. Vor R4-Deploy ergänzen — alternativ R4 entfernen (Kl. Vorraum + Hauptvorraum reichen falls WC manuelles Off rar ist).

- [ ] **Step 3: Commit + deploy**

```bash
git add rules/bwm_override.rules
git commit -m "add: bwm override rules (manual-off + ambient + awaymode)"
git push
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
ssh herwig@10.1.100.101 'sudo tail -60 /var/log/openhab/openhab.log | grep -iE "BWM-Override|error"'
```

Expected log lines after first load:
```
[INFO] BWM-Override - System started — BWMs enabled (default state)
```

### Task 12 — End-to-End Walk-Test [VERIFY]

Drei Test-Szenarien:

- [ ] **Step 1: Manual-Override Test**

1. AwayMode = OFF
2. Ambient = OFF (z.B. Tag, oder manuell Strasshof_AmbientLight_On = OFF)
3. In Hauptvorraum-BWM-Cone gehen → Licht muss angehen
4. Wandtaster Hauptvorraum OFF drücken
5. Stehen bleiben — Licht muss aus bleiben, auch wenn BWM weiter zyklisch sendet
6. Im OH-Log: `Manual OFF im Hauptvorraum erkannt — BWM disabled für 5 min`
7. 5 Min warten + bewegen → BWM wieder aktiv, Licht geht wieder

- [ ] **Step 2: Ambient-Mode Test**

1. AwayMode = OFF
2. Strasshof_AmbientLight_On manuell auf ON setzen (oder Sunset simulieren)
3. Im Log: `Ambient mode aktiviert — alle BWMs disabled`
4. In Vorraum gehen → kein Hauptlicht
5. Strasshof_AmbientLight_On auf OFF → Log: `re-enabled`, BWMs wieder aktiv

- [ ] **Step 3: AwayMode-Priority Test**

1. AwayMode = ON (manuell)
2. Strasshof_AmbientLight_On = ON
3. Im Log: `Ambient activated, aber AwayMode aktiv — BWMs bleiben ON`
4. In Vorraum gehen → Bewegung wird detektiert, Telegram-Alarm geht raus, Licht geht an (weil BWMs nicht gegated)

**Gate:** alle drei Szenarien verhalten sich wie erwartet.

---

## Phase 5 — Documentation finalisation (AGENT/CFG)

### Task 13 — Persönliche Doku aktualisieren [CFG]

**Files:**
- Modify: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\docs\smart-home\knx-motion-logic.md`
- Modify: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\docs\projects\knx-todo.md`
- Modify: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\docs\smart-home\knx-devices.md`
- Modify: `C:\Users\herwi\OneDrive\Dokumente\Privat\Makerstuff\docs\smart-home\knx-ga-map.md`

- [ ] **Step 1: knx-motion-logic.md** — neue Sektion "Phase 3: Manual-Override + Ambient-Coupling via ITR508" hinzufügen, beschreibt das Gating-Layer.

- [ ] **Step 2: knx-todo.md** — den BWM-Limitierung-Punkt umformulieren: "Gelöst durch ITR508-Gating-Architektur (2026-MM-DD)". BWM-Modell-Tausch bleibt auf der Liste als Wunsch.

- [ ] **Step 3: knx-devices.md** — bei `1.1.10` (ITR508) ergänzen dass 4 Logic Gates nun für BWM-Gating in Verwendung sind.

- [ ] **Step 4: knx-ga-map.md** — die sieben neuen GAs (`1/0/13–15`, `1/0/19–20`, `1/0/22–23`) in der `1/0/x`-Sektion ergänzen.

- [ ] **Step 5: CHANGELOG** — Eintrag für den Tag des Umsetzungs-Tages.

### Task 14 — openhab-config CHANGELOG [VERIFY]

- [ ] **Step 1: Commits-Liste prüfen**

```bash
git log --oneline | head -5
```

Sollte die Tasks 9–11-Commits zeigen.

---

## Self-Review

- [x] **Spec coverage:** alle In-Scope-Punkte abgedeckt (7 GAs, 4 Gates, 4 N567-Inputs, 3 OH-Items, 7 Rules)
- [x] **No placeholders:** alle GAs konkret, alle Items mit Channel-Reference, alle Rules komplett-Code
- [x] **Type consistency:** Item-Namen `Strasshof_*_BWM_Enable` durchgängig, Channel-Namen ohne Strasshof-Prefix konsistent zu bestehenden Channels
- [x] **Phases independent:** Phase 1+2 (ETS) testbar bevor Phase 3 (N567 relink) bevor Phase 4 (OH). Rollback möglich nach jeder Phase.
- [x] **Edge cases addressed:** AwayMode-vs-Ambient-Priority, OH-Offline-Verhalten, Default-After-Bus-Return, Override-Timer-Reset bei Doppel-Press
