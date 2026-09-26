# Runbook: Bad-Lüftung v2 (Controller)

Stand: 2026-09-26 (Untergrenze Innentemperatur) · openHAB 5.1.0 · Rule: `rules/bathroomAiringController.rules`

| Schritt | Inhalt | Status |
|---------|--------|--------|
| 1 | Schattenbetrieb: v2 loggt nur, v1 (`bathroomAiring.rules`) fährt den Motor | [x] ~~erledigt~~ 2026-09-17 |
| 2 | Auswertung ~3 Tage: v2-Modi (Influx) vs. echte Motorfahrten | [x] ~~erledigt~~ 2026-09-26 — 9 Tage ausgewertet, siehe unten |
| 3 | Umschalten: v1-Entscheidungsregeln + `dewpointBadAlert` entfernen, `Bathroom_Airing_Shadow` = OFF | [ ] offen |
| 4 | Aufräumen: `Bathroom_DewPoint_Previous`, `Bathroom_Someone_Showering`, `Bathroom_Airing_Suspended/Active/Started` | [ ] offen |

---

## Problem (v1)

- Taupunkt-Alarm (innen − außen ≥ 3 °C) war im Sommer praktisch dauernd an: Aug 83 %, Sep 65 % der Zeit;
  Luftfeuchte ≥ 75 % aber nur 2–9 % der Zeit. Pro Ein/Aus ein Telegram → 3–5 Nachrichten/Tag.
- Lüften kurz: 15.07.–16.09. im Schnitt **1,7 h/Tag offen**, obwohl es an Sommertagen 5–6 h mild, trocken und ruhig war.
- Flattern: Regeln reagierten auf jede Taupunkt-Einzelmessung (Sensor springt ±0,26 °C pro 1 % rF).
  12.09.: 20 Motorfahrten in 2 h, schlechtester Tag 31. Fix `fc665a7` hat nur das Symptom gedämpft.
- Tägliches Reset um 05:00 → Fenster ging an ~50 % der Tage um 05:00 auf.

## Logik v2

Eine Entscheidung alle 5 min (`cron 30 */5`), genau ein Modus in `Bathroom_Airing_Mode`:

| Modus | Öffnen wenn | Offen halten solange | Schließen wenn |
|-------|-------------|----------------------|----------------|
| **FAIR** | außen 16–26 °C (15-min-Mittel Wetterstation), 60 min kein Sturm, Böen < 55 km/h, Taupunkt außen < innen, 06–22 Uhr, nicht wärmer als innen +0,5 °C (über 24 °C), **Bad ≥ 21,5 °C** | außen 14–28 °C, kein Sturm, Taupunkt außen ≤ innen +1 °C, nicht wärmer als innen +2 °C (über 24 °C), **Bad ≥ 21 °C** | Bedingung weg **und** ≥ 60 min seit letzter Fahrt; um 22:00 sofort |
| **SHOWER** | rF steigt ≥ 8 %-Punkte in 15 min (Erkennung) → geöffnet erst wenn **Duschen vorbei**: rF ≥ 3 Punkte unter dem Spitzenwert, kein Licht in den letzten 45 min eingeschaltet, kein Sturm, außen ≥ 5 °C — **auch nachts**; nach 90 min ohne Ende verworfen | — | rF ≤ Wert vor dem Duschen +3, oder Taupunkt innen ≤ außen +1 °C, oder max. 45 min (außen < 12 °C) / 90 min, oder Bad unter 19 °C (harte Grenze). Bei FAIR-Wetter Übergabe an FAIR statt Schließen |
| **MANUAL_OPEN / MANUAL_CLOSED** | KNX-Taster `Bathroom_Window_Open` ON/OFF | 120 min Automatik-Pause | danach Neubewertung |
| **OFF** | Master-Schalter `Bathroom_Airing_Automation` aus | — | nach Einschalten 3 min warten, dann Schließfahrt als Resync |

Immer, in jedem offenen Modus:
- **Sturm** schließt sofort: Regen ≥ 4 mm (OWM) oder Böen ≥ 60 km/h oder OWM-Gewitter-Code 2xx.
  Normaler Regen schließt **nicht** (kleines Fenster, Regen kommt nicht rein).
- **Veraltete Sensoren** schließen FAIR/SHOWER: Wetterstation > 30 min, Bad-Sensor > 90 min, OWM > 180 min ohne Update (`lastStateUpdate`).
- **Griff verriegelt/gekippt** (`Bathroom_Alarm_Locked/Tilted`) → nicht öffnen (wie Motor-Layer).

**Feuchte-Alarm** (ersetzt Taupunkt-Alarm fürs Bad): rF ≥ 80 % durchgehend 2 h → `Bathroom_DewPoint_Alert` ON
(KNX-Anzeige `Bathroom_Humidity_Alert`, Ulanzi) + **ein** Telegram. Aus bei rF ≤ 70 %, ohne Telegram.

Motor-Layer bleibt unverändert: `bathroom_airing_action` + `bathroom_airing_motor_off` in `bathroomAiring.rules`
(Requests → Shelly Plus 2PM, Abschaltung bei ≤ 1,1 W).

## Validierung mit Historie (Influx 16.03.–17.09.2026)

Simulation der v2-Logik auf 5-min-Raster mit gemessenen Werten vs. tatsächliche Motorfahrten:

| 15.07.–16.09. | v1 (real) | v2 (Simulation) |
|---|---|---|
| Fenster offen (h/Tag) | 1,7 | **6,0** |
| Motorfahrten/Tag | 4,8 | **3,4** |
| Schlechtester Tag (Fahrten) | 31 | **8** |
| Öffnungen um 05:00 | ~50 % der Tage | keine |
| Duschen mit Lüften binnen 30 min | 136 / 159 | 130 / 159 |
| Sturm-Schließungen | — | ~2 / Monat |
| Feuchte-Alarm-Telegrams (6 Monate) | mehrere pro Tag | 26 gesamt |

Frühling v2: April 1,0 → 4,0 h/Tag, Mai 1,8 → 6,1 h/Tag.

**Nicht während des Duschens öffnen** (159 erkannte Duschen, 5-min-Ticks wie die Rule):

| Öffnen-Auslöser | gelüftet | geöffnet vor rF-Spitze (= Wasser läuft noch) | Verzögerung Median / 90 % |
|---|---|---|---|
| fix 10 min nach Erkennung (erster Entwurf) | 159 | **30** | 10 / 10 min |
| rF ≥ 2 unter Spitze | 155 | 8 | 10 / 28 min |
| **rF ≥ 3 unter Spitze + Licht-Sperre 45 min** (umgesetzt) | 153 | **5** | 15 / 45 min |

Die 5 Restfälle sind Doppel-Duschen: erste Person fertig, rF fällt, Fenster öffnet regulär, zweite Person
duscht 15–40 min später bei schon offenem Fenster (keine Motorfahrt während des Duschens).
Licht war nur bei 14 % der Duschen an (tagsüber) → nur Zusatz-Sperre, nicht Hauptsignal.
FAIR öffnet nie bei laufender Dusche (erkannt, rF steigt oder Licht kürzlich eingeschaltet).
Ist das Fenster wegen FAIR schon offen, wenn geduscht wird, bleibt es offen.

**Grenzen der Simulation**
- Innenfeuchte ist die gemessene (mit v1-Lüftung). Länger offen → Bad trockener → Bedingung „Taupunkt außen < innen" öfter falsch → reale Offenzeit eher etwas geringer.
- OWM-Regen/Böen nur stündlich; Wetterstation-Regensensor liefert nichts (3 Werte in 6 Monaten), Windsensor zeigt fast immer 0.
- Keine Winterdaten → Kälte-Parameter (≥ 5 °C, 45 min) sind Schätzwerte.
- Sensor-Ausfälle in der Historie: Bad-Sensor 06.–18.08. ohne Daten, Wetterstation bis 4,8 Tage Lücken.

## Auswertung Schattenbetrieb (17.–26.09.2026, 9,4 Tage)

v2 lief nur als Log/virtuelles Fenster, v1 hat gefahren. Vergleich aus Influx (`Bathroom_Airing_Mode` vs. Motor-Relais):

| | v1 (real gefahren) | v2 (Schatten) |
|---|---|---|
| Fenster offen | 2,0 h/Tag | **8,2 h/Tag** |
| Motorfahrten | 5,1/Tag (48) | **3,6/Tag (34)** |
| Nachts offen (22–06) | — | 2,4 h gesamt (Dusche + manuell) |
| Feuchte-Alarm | 18× ON in 9 Tagen (≈ 36 Telegrams) | **0×** (rF nie 2 h ≥ 80 %, Spitze 93 %) |

Duschen: 12 erkannt, 10 als SHOWER behandelt (2 fielen in die manuelle Pause — korrekt).
Bei 6 Öffnungen aus CLOSED war die Dusche laut rF-Verlauf beendet; in einem Fall (18.09. 17:25)
begann ~5 min nach dem Öffnen eine **weitere** Dusche (rF 66 → 93 %) — Fenster war dann offen, der Motor fuhr aber nicht.

**Erkenntnisse**
1. **Böen-Grenze 40 km/h war zu streng.** 21.–23.09. durchgehend Böen 41–47 km/h → v2 hielt 1,5 Tage zu
   (0,8 bzw. 0 h offen), obwohl 16–20 °C und trocken. Grenze auf **Öffnen < 55, Sturm ≥ 60 km/h** angehoben (2026-09-26).
2. **Auskühlung ist nicht abgedeckt.** 21 reale Lüftungen ≥ 25 min im Zeitraum: Median **−0,45 °C/h**
   (Extremwert −1,9 °C/h) bei ~10 °C Differenz innen/außen. Alle gemessenen Episoden ≤ 95 min; v2 würde an
   milden Tagen 8–15 h offen halten → mehrere °C Abkühlung und im Herbst/Winter Heizverlust.
   → **erledigt 2026-09-26: Untergrenze Innentemperatur** — FAIR schließt unter 21 °C, öffnet erst ab 21,5 °C;
   SHOWER hat eine harte Grenze bei 19 °C. Modell aus den gemessenen Raten (Abkühlung k = 0,048/h,
   Aufheizung geschlossen nur 0,05 °C/h — Heizung im September aus, Bad kühlt also kaum nach):

   | | FAIR offen | modellierte Bad-Temperatur |
   |---|---|---|
   | ohne Grenze | 8,5 h/Tag | Minimum 19,4 °C, Median 20,8 °C |
   | **Grenze 21 / 21,5 °C** | 7,2 h/Tag | Minimum 21,0 °C, Median 21,6 °C |
   | Grenze 22 / 22,5 °C | 6,2 h/Tag | Minimum 22,0 °C |

   Kostet ~1,3 h/Tag Lüftung. Aufheiz-Rate ist der schwächste Teil des Modells (nur 10 Segmente, Heizung aus)
   — im Winter mit Heizung erholt sich das Bad schneller, dann aber auf Kosten der Heizenergie.
3. Der Rest lief wie geplant: keine Flatter-Zyklen, Sturm-/Ruhezeiten-/Manuell-Logik wie entworfen,
   Alarm deutlich ruhiger.

## Hardware-Fakten

- **Master-Schalter** `Bathroom_Airing_Automation` (KNX) schaltet die **Stromversorgung** beider Shellys (Motor + Kontakte).
  Aus → keine Steuerung, Fenster bleibt wo es ist. Ein → Shellys brauchen einige Zeit bis zur ersten Verbindung.
- Shelly Plus 2PM (Motor): `10.1.3.6`, Shelly Plus i4 DC (Kontakte): `10.1.3.5` — beide per HTTP aus dem Work-VLAN lesbar (`/rpc/Shelly.GetStatus`).
- Die Kontakte melden die **Griffstellung** (verriegelt/gekippt/offen), nicht die Motor-Kippstellung.
  Seit 22.06. keine Änderung, weil nur noch motorisch gelüftet wird. 17.09. geprüft: Shelly-Inputs = openHAB-Items.

## Schritt 1 — Schattenbetrieb

```bash
# Windows
git push
# Server
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

`Bathroom_Airing_Shadow` ist nach dem Anlegen NULL → gilt als Schattenbetrieb. Explizit setzen: Item in der Main UI auf ON.

Prüfen:
- `openhab.log`: keine Fehler beim Laden von `bathroomAiringController.rules`; alle 5 min ggf. `SHADOW would OPEN/CLOSE …`
- `Bathroom_Airing_Mode` / `Bathroom_Airing_Reason` bekommen Werte (REST oder UI)
- Detail-Log bei Bedarf: `log:set DEBUG org.openhab.core.model.script.bathroom_airing_ctl`

## Schritt 3 — Umschalten

1. In `bathroomAiring.rules` entfernen: `someone_showering`, `bathroom_airing`, `bathroom_airing_watchdog`,
   `bathroom_airing_reset_suspend`, `bathroom_airing_init`, `bathroom_airing_button`. Behalten: `bathroom_airing_action`, `bathroom_airing_motor_off`.
2. In `senddewpointalert.rules` die Rule `dewpointBadAlert` entfernen (Schlafzimmer-Regeln bleiben).
3. `Bathroom_DewPoint_Alert` auf OFF setzen, `Bathroom_Airing_Shadow` auf OFF.

## Rollback

`Bathroom_Airing_Shadow` → ON (v2 sofort nur noch Log). Nach Schritt 3 zusätzlich den Umschalt-Commit reverten:
`git revert <commit> && git push`, am Server `sudo git pull`.
