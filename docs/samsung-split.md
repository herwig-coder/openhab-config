# Samsung-Splits (NASA-Bus via ESPHome) — Verhalten und Regel-Checkliste

Stand 2026-10-03. Betrifft ODU 2 (Außengerät Carport) mit **Büro Herwig** (NASA `20.00.01`, AR07TXFC) und **Keller-Hobbyraum** (NASA `20.00.00`, AR12TXFC).
ODU 1 (Wohnzimmer + Wintergarten, ESP `samsung-odu1`) folgt später nach demselben Muster.

Dateien: `things/MQTT_Samsung.things`, `items/Samsung_Split.items`, `rules/samsung_split.rules`.
Projekt-Doku mit Hardware, Inbetriebnahme und allen Messungen: `home-it-docs` → `docs/projects/samsung-split-nasa.md`.

## Kette

```
openHAB Item ──command──► MQTT (10.1.0.10) ──► ESP samsung-odu2 (10.1.0.31) ──► NASA-Bus F1/F2 ──► Innengerät
openHAB Item ◄──state──── MQTT ◄────────────── ESP ◄──────────────────────────── Status-Broadcast des Geräts
```

- ESPHome publiziert **Klartext** (kein JSON): `samsung-odu2/climate/<id>/<attr>/state|command`, Sensoren unter `samsung-odu2/sensor/<id>/state`, Verfügbarkeit `samsung-odu2/status` (retained LWT `online`/`offline`).
- Der **State kommt vom Gerät**, nicht optimistisch vom ESP: ein Item-State bestätigt, dass das Gerät den Befehl übernommen hat.
- Uptime Kuma überwacht `samsung-odu2/status` (MQTT-Monitor, Keyword `online`) und meldet Ausfälle per Telegram.

## Beobachtetes Verhalten (Tests 2026-10-03)

| Thema | Verhalten | Bedeutung für openHAB |
|---|---|---|
| **Latenz** | Kommando → State-Rückmeldung in 0,5–1,3 s; Gerät piept | Nach einem Command ~3 s auf den State warten, bevor man Erfolg prüft |
| **Fernbedienung** | Jeder Tastendruck kommt als State-Änderung an | Items sind auch bei Bedienung per FB aktuell; Regeln sehen FB-Änderungen als normale `changed`-Events |
| **Status-Broadcast** | Innengeräte senden ihren Vollzustand ca. alle 20 s | Spätestens nach ~20 s ist ein Item wieder korrekt |
| **ESP-Neustart** | Climate-Entitäten publizieren Boot-Defaults **Modus `off`, Sollwert `nan`** bis zum nächsten Broadcast (~20 s). Ein Kommando, das in den Neustart fällt, **geht verloren** | **Falsches „aus" möglich** → siehe Checkliste. Thing geht kurz OFFLINE, wenn der Broker das LWT setzt |
| **Sollwert `nan`** | Sollwert-Channel kann `nan` empfangen (Boot, Lüftermodus-Wechsel) | Erzeugt ggf. eine Parse-Warnung im openHAB-Log; Item behält den alten Wert — harmlos |
| **Sollwert bei ausgeschaltetem Gerät** | Wird ignoriert bzw. nicht zurückgemeldet | Sollwert nur bei eingeschaltetem Gerät setzen oder Modus + Sollwert zusammen senden |
| **Lüftermodus** | Gerät meldet eigenen Sollwert **24 °C** | Kein echter Sollwert — nicht persistent auswerten |
| **WindFree** | Nur in Kühlen/Entfeuchten/Lüften; **im Heizmodus ignoriert** (kein State-Wechsel) | Preset nur in passenden Modi senden; beim Ausschalten fällt Preset auf `none` |
| **Swing** | `off`/`vertical`/`horizontal`/`both` funktionieren | — |
| **Raumtemperatur** | Springt beim Einschalten (z. B. 23,3 → 21,3 °C), weil der Lüfter ansaugt; im Standby träger | Für Regelentscheidungen besser einen Raumsensor nehmen (BLE/KNX) oder Werte erst nach einigen Minuten Laufzeit verwenden |
| **Leistung** `Split_Odu2_Power` | Wirkleistungs-Mittel der **letzten Minute**, läuft ~1 min nach; erste Minute nach Start nur teilweise (z. B. 134 W statt ~375 W) | Nicht für schnelle Reaktionen nutzen; für „läuft der Kompressor?" `Split_Odu2_Current > 0` nehmen |
| **Strom** `Split_Odu2_Current` | Momentanwert, 0,00 A bei stehendem Kompressor | Bester Indikator „Außengerät arbeitet" |
| **Energie** `Split_Odu2_Energy` | Zähler des Außengeräts (roh Wh → kWh). Stand 2026-10-03: 29,97 kWh — für die Laufzeit niedrig, Plausibilität noch offen | Nur **je Außengerät**, nicht je Raum. Vor Abrechnungen über einige Tage gegen Smartmeter/Leistung prüfen |
| **Fehlercode** `Split_Odu2_ErrorCode` | 0 = OK; ≠ 0 löst `samsung_split.rules` → Telegram aus | Ein Code gilt fürs Außengerät samt beiden Innengeräten |

## Checkliste für Regeln, die Klima-Items lesen oder steuern

- [ ] **NULL/UNDEF-Guard** auf jedem gelesenen Item (Standard).
- [ ] **ESP-Neustart abfangen:** Entscheidungen auf Basis von `Split_*_Mode`/`Setpoint` nur, wenn `Split_Odu2_Esp_Online == ON` **und** `Split_Odu2_Esp_Uptime > 60 s`. Sonst ist ein `off` möglicherweise nur der Boot-Default.
  ```xtend
  if (Split_Odu2_Esp_Online.state != ON) return;
  if (Split_Odu2_Esp_Uptime.state == NULL || Split_Odu2_Esp_Uptime.state == UNDEF) return;
  if ((Split_Odu2_Esp_Uptime.state as Number).intValue < 60) return;   // item unit is s
  ```
- [ ] **`changed`-Trigger auf Modus:** Ein Wechsel `<modus> → off → <modus>` innerhalb ~20 s ohne eigenes Kommando ist ein ESP-Neustart, kein Benutzereingriff — nicht als „manuell ausgeschaltet" werten.
- [ ] **Erfolg prüfen statt annehmen:** nach `sendCommand` per Timer (~5 s) den State vergleichen; bei Abweichung einmal wiederholen, danach loggen/Telegram. Ursache sind verlorene Kommandos bei ESP-Neustart.
- [ ] **Keine Command-Retains** — Channels sind `retained=false`; Regeln nie über `publishMQTT(..., retained=true)` an `…/command` senden.
- [ ] **FB-Bedienung respektieren:** Regeln, die steuern, brauchen eine Vorrang-/Override-Logik (Benutzer stellt per FB um → Automatik pausiert), sonst kämpfen Regel und Mensch.
- [ ] **WindFree** nur senden, wenn Modus `cool`/`dry`/`fan_only`; im Heizmodus wird es ignoriert.
- [ ] **Sollwert** nur bei laufendem Gerät oder zusammen mit dem Modus senden.
- [ ] **Kompressor-Status** über `Split_Odu2_Current > 0`, nicht über `Split_Odu2_Power` (Minutenmittel, verzögert).
- [ ] **Kein Schnell-Takten:** Inverter-Kompressor nicht in kurzen Abständen ein/aus schalten (Mindestlaufzeit/-pause in der Regel vorsehen, z. B. 10 min).
- [ ] **Beide Innengeräte teilen ein Außengerät:** Leistung/Energie/Fehlercode gelten für beide Räume gemeinsam; der Heizbetrieb des einen beeinflusst die verfügbare Leistung des anderen.
- [ ] **Logging** mit Logger-Name = Regeldatei.

## Geplante Regeln

- **Sperrregel Hobbyraum-Split ↔ Warmwasser-Wärmepumpe** (home-it-docs `docs/haustechnik/regelungskonzept.md`): Hobbyraum-Split darf nicht heizen, während die BWWP dem Keller Wärme entzieht. Braucht die Checkliste oben vollständig (Neustart-Guard, FB-Override, Mindestlaufzeit).

## Optional

- events.log-Filter (log4j2, außerhalb git, siehe `docs/energy-rollout.md`) um `Split_Odu2_(Power|Energy|Current|OutdoorTemp)` erweitern, falls die Minutenwerte stören.
- Weitere Presets (Sleep, Quiet, Fast, Eco, LongReach) sind in ESPHome deaktiviert — erst am Gerät testen, dann in ESPHome-YAML, Things (`allowedStates`) und Items (`commandDescription`) ergänzen.
