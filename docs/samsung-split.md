# Samsung-Splits (NASA-Bus via ESPHome) — Verhalten und Regel-Checkliste

Stand 2026-10-03. Betrifft ODU 2 (Außengerät Carport) mit **Büro Herwig** (NASA `20.00.01`, AR07TXFC) und **Keller-Hobbyraum** (NASA `20.00.00`, AR12TXFC).
**ODU 1** (Außengerät Garten hinten) mit **Wohnzimmer** (AR07TXFC) und **Wintergarten** (AR12TXFC), ESP `samsung-odu1` (10.1.0.30): Things/Items **vorbereitet 2026-10-03** (Things bleiben OFFLINE, Items NULL, bis der ESP am Bus ist). Die Zuordnung NASA-Adresse → Raum liegt ausschließlich in der ESPHome-YAML; openHAB hängt nur an den Topic-Namen (`wohnzimmer_split`, `wintergarten_split`, `odu1_*`).

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
| **MQTT-Last / Publish-Verhalten** | Seit lokalem Komponenten-Patch (2026-10-11, `publish_if_changed`) wird der Climate-Zustand **nur bei Änderung** publiziert; im Ruhezustand kaum Traffic. Nach Reconnect republiziert ESPHome alle States | Nicht annehmen, dass States periodisch kommen — nur bei Änderung bzw. Reconnect |
| **Nachlauf / Auto-Reinigung** | Ausschalten per **Fernbedienung** startet die Trocknung des Wärmetauschers (10–30 min, Display 1–99 %), weil die FB die Auto-Clean-Einstellung mitschickt. **NASA-Aus von openHAB nicht.** Ein `AutoClean` = ON bei ausgeschaltetem Gerät startet die Trocknung (getestet 2026-10-24, Büro). Der Schalter-State zeigt die Einstellung/Anforderung, nicht den Fortschritt | Regeln `Samsung Auto-Reinigung: …`: openHAB-`off` eines **laufenden** Geräts merkt das Gerät vor; sobald das Gerät selbst `off` meldet, wird `Split_*_AutoClean` ON gesendet (Vormerkung verfällt nach 30 s → FB-Aus/ESP-Neustart lösen nie aus). AutoClean **vor** dem Aus wirkt nicht (Test Wohnzimmer). Die FB löst die Reinigung nur bedingt aus (nach kurzem Heizen evtl. nicht). Mode-Items haben dafür `autoupdate="false"` |
| **Latenz** | Kommando → State-Rückmeldung in 0,5–1,3 s; Gerät piept | Nach einem Command ~3 s auf den State warten, bevor man Erfolg prüft |
| **Fernbedienung** | Jeder Tastendruck kommt als State-Änderung an | Items sind auch bei Bedienung per FB aktuell; Regeln sehen FB-Änderungen als normale `changed`-Events |
| **Status-Broadcast** | Innengeräte senden ihren Vollzustand ca. alle 20 s | Spätestens nach ~20 s ist ein Item wieder korrekt |
| **ESP-Neustart** | Climate-Entitäten publizieren Boot-Defaults **Modus `off`, Sollwert `nan`** bis zum nächsten Broadcast (~20 s). Ein Kommando, das in den Neustart fällt, **geht verloren** | **Falsches „aus" möglich** → siehe Checkliste. Thing geht kurz OFFLINE, wenn der Broker das LWT setzt |
| **Sollwert `nan`** | Sollwert-Channel kann `nan` empfangen (Boot, Lüftermodus-Wechsel) | Erzeugt ggf. eine Parse-Warnung im openHAB-Log; Item behält den alten Wert — harmlos |
| **Sollwert bei ausgeschaltetem Gerät oder im Lüftermodus** | Wird **ignoriert** (nicht gespeichert, bestätigt 2026-10-11) — beim nächsten Einschalten gilt der zuletzt im jeweiligen Modus gesetzte Sollwert | **Erst Modus setzen, dann Sollwert** (zwei Kommandos, nach dem Modus ~2 s warten); nicht bei `off`/`fan_only` |
| **Lüftermodus** | Gerät meldet eigenen Sollwert **24 °C** | Kein echter Sollwert — nicht persistent auswerten |
| **WindFree** | Nur in Kühlen/Entfeuchten/Lüften; **im Heizmodus ignoriert** (kein State-Wechsel) | Preset nur in passenden Modi senden; beim Ausschalten fällt Preset auf `none` |
| **Swing** | `off`/`vertical`/`horizontal`/`both` funktionieren. **Am Bus zwei getrennte Werte** (0x4011 auf/ab, 0x407E links/rechts), die ESPHome-Climate-Entity fasst sie zu **einem** Enum zusammen und schreibt immer **beide** Bits (2026-10-26, Code `protocol_nasa.cpp`). Seit Firmware `ba65b6c` (beide ESPs, 2026-10-26) zusätzlich **je Achse ein Schalter**: `Split_*_SwingVertical` / `Split_*_SwingHorizontal` (`…/switch/<gerät>_split_swing_vertikal` bzw. `_swing_horizontal`, ON/OFF, nicht retained, Items mit `autoupdate="false"`; der Schalter-State ist aber das **Echo des ESP** (~0,1 s, `write_state` publiziert vor dem Bus-Schreiben) — die Bestätigung des Geräts ist der Climate-Report `Split_*_Swing` (0,3–1,9 s)) | Für Regeln **nur die Achsen-Schalter** verwenden; `Split_*_Swing` nicht senden (`horizontal` beendet ein laufendes Auf/Ab-Swing, `off` beendet beide) |
| **Lamellen links/rechts** (gemessen 2026-10-26, Büro) | Jedes Einschalten fährt L/R in die **Mitte**, das Gerät **merkt sich die Swing-Richtung** über Aus/Ein; am Anschlag kehrt sie um. Ein Durchlauf ≈ **15,5 s**. Swing OFF **friert die Lamelle ein**. In der **Vorwärmphase** (Heizen bis Lüfter läuft, gemessen 2:00–2:37 min, warmes Gerät) nimmt die FB kein Swing an; ob ein NASA-Befehl dort wirkt, ist ungetestet. Lüfterstart am Bus noch nicht erkennbar | Türausrichtung Büro (`rules/ergant_heat.rules`, Sequenz D): Heizen bestätigt → **3 min** warten → `SwingHorizontal` ON → **23,5 s nach dem Geräte-Report** (`Split_BueroHerwig_Swing` → `horizontal`/`both`) OFF → Türanschlag. Stabilisiert sich selbst; nach FB-Swing kann ein Zyklus an der Wand enden (akzeptiert). Auf/Ab bleibt auf Gerätestandard (nie gesendet). Details: home-it-docs `docs/projects/samsung-split-nasa.md` „Ergebnis Türausrichtung Büro“ |
| **Raumtemperatur** | Springt beim Einschalten (z. B. 23,3 → 21,3 °C), weil der Lüfter ansaugt; im Standby träger | Für Regelentscheidungen besser einen Raumsensor nehmen (BLE/KNX) oder Werte erst nach einigen Minuten Laufzeit verwenden |
| **Leistung** `Split_Odu2_Power` | Wirkleistungs-Mittel der **letzten Minute**, läuft ~1 min nach; erste Minute nach Start nur teilweise (z. B. 134 W statt ~375 W) | Nicht für schnelle Reaktionen nutzen; für „läuft der Kompressor?" `Split_Odu2_Current > 0` nehmen |
| **Strom** `Split_Odu2_Current` | Momentanwert, 0,00 A bei stehendem Kompressor | Bester Indikator „Außengerät arbeitet" |
| **Energie** `Split_Odu2_Energy` / `Split_Odu1_Energy` | Kumulativer Zähler des Außengeräts seit Inbetriebnahme (roh Wh → kWh). Stand 2026-10-11 ~30 kWh je Außengerät — plausibel, Anlage läuft erst wenige Tage | Nur **je Außengerät**, nicht je Raum |
| **Fehlercode** `Split_Odu2_ErrorCode` / `Split_Odu1_ErrorCode` | 0 = OK; ≠ 0 löst `samsung_split.rules` (Gruppe `gSamsungErrorCode`) → Telegram aus | Ein Code gilt fürs Außengerät samt beiden Innengeräten |

> **Verfügbarkeit (Stand 2026-10-23):** `samsung-odu2` (Büro/Hobbyraum) stabil. `samsung-odu1` (Wohnzimmer/Wintergarten) hat wenige Aussetzer pro Tag (~3 × > 70 s, gelegentlich ein Neustart) — bewusst akzeptiert. Regeln auf Wohnzimmer/Wintergarten müssen damit rechnen: Kommando kann verloren gehen, Thing kurz OFFLINE → Erfolg prüfen und ggf. wiederholen (siehe Checkliste).

## Checkliste für Regeln, die Klima-Items lesen oder steuern

- [ ] **NULL/UNDEF-Guard** auf jedem gelesenen Item (Standard).
- [ ] **ESP-Neustart abfangen:** Entscheidungen auf Basis von `Split_*_Mode`/`Setpoint` nur, wenn der **zuständige** ESP online ist **und** Uptime > 60 s — `Split_Odu2_Esp_*` für Büro/Hobbyraum, `Split_Odu1_Esp_*` für Wohnzimmer/Wintergarten. Sonst ist ein `off` möglicherweise nur der Boot-Default.
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
