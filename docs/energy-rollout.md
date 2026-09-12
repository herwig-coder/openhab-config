# Runbook: Energie-Rollout (Victron + Persistence + Logging)

Stand: 2026-09-12 · openHAB 5.1.0 auf `homeservernew` (10.1.100.101)

Drei Teile, in dieser Reihenfolge. Jede Stufe einzeln ausrollen und prüfen, bevor die nächste kommt.

| Teil | Inhalt | Status |
|------|--------|--------|
| A | log4j2-Filter für `events.log` (liegt **außerhalb** von git) | [x] ~~erledigt~~ 2026-09-12 |
| 1 | Persistence UI → Dateien, Energie-Gruppen, Smart-Meter/Awattar-Umbau | [ ] |
| 2 | Victron: Things, Items, Keepalive-Rule | [ ] |

---

## Teil A — log4j2-Filter (erledigt)

**Datei:** `/var/lib/openhab/etc/log4j2.xml` (Debian/apt, `OPENHAB_USERDATA=/var/lib/openhab`).
Nicht im Repo → nach openHAB-Upgrades prüfen, ob der Filter noch drin ist.

Im Appender `EVENT` (`RollingRandomAccessFile name="EVENT"`) nach `<DefaultRolloverStrategy max="7"/>`:

```xml
<!-- Energy: drop high-frequency value changes, keep state/mode/alarm changes and all commands -->
<RegexFilter regex="Item '(?:SmartMeter_|Victron_(?!SystemState'|Alarm'|\w*_Alarm_|MultiPlus_Mode'|MultiPlus_State'|Generator_Mode'|Generator_State'|State_|Battery_ChargeBlocked'|Battery_DischargeBlocked'))[^']*' changed from .*" onMatch="DENY" onMismatch="NEUTRAL"/>
```

- Verwirft: `changed`-Events aller `SmartMeter_*` und `Victron_*` Items
- Behält: Systemstatus, Modus, Zustand, Alarme, BMS-Sperren, **alle Commands**, alles andere
- Live-Log-Viewer / Karaf-Konsole zeigen weiterhin alles (nur `events.log` gefiltert)
- Getestet mit echtem Log4j2 2.24 / Java 21

**Lessons learned:** `monitorInterval` greift unter pax-logging nicht zuverlässig — Änderungen an
`log4j2.xml` brauchen `sudo systemctl restart openhab` (oder `sudo touch /var/lib/openhab/etc/org.ops4j.pax.logging.cfg`).
XML vorher prüfen: `python3 -c "import xml.dom.minidom as m; m.parse('/var/lib/openhab/etc/log4j2.xml'); print('XML OK')"`.
Log4j2-Konfigfehler stehen im Journal, nicht in `openhab.log`: `sudo journalctl -u openhab | grep -i StatusLogger`.

---

## Stufe 1 — Persistence auf Dateien + Energie-Struktur

**Was sich ändert**
- Persistence für `influxdb`, `rrd4j`, `mapdb`, `inmemory` kommt aus `persistence/*.persist` statt aus der UI (JSONDB).
  Die UI-Config enthielt nur die ehemaligen Service-Defaults (vom 5.1-Upgrade angelegt) — 1:1 übernommen.
- Neu: Energie-Gruppen werden gedrosselt statt bei jeder Änderung geschrieben:

  | Gruppe | InfluxDB | rrd4j | MapDB |
  |--------|----------|-------|-------|
  | alles andere (`*`) | everyChange | everyChange + everyMinute | everyChange |
  | `gEnergySystem*` (Dashboard) | Änderung, max. 1×/10 s + everyMinute | everyMinute | everyMinute |
  | `gEnergyDiag*` (Diagnose) | everyMinute | everyMinute | everyMinute |

- Items: `gEnergySystem` / `gEnergyDiag` / `gEnergy` in `semantic_model.items`; Smart Meter und Strompreis unter „Energie“.
  Item-Namen unverändert → `ui/widgets/widget_energy_meter.yaml` funktioniert weiter.

**Wichtig:** UI- und Datei-Config für denselben Service schließen sich aus. Die JSONDB-Datei muss weg,
**während openHAB gestoppt ist** (openHAB hält JSONDB im Speicher — Datei nie im laufenden Betrieb anfassen).
Nur den Stufe-1-Commit pushen — `git pull` holt sonst Stufe 2 gleich mit.

**Ablauf (Server)**
```bash
# 0. Backup
sudo cp -p /var/lib/openhab/jsondb/org.openhab.core.persistence.PersistenceServiceConfiguration.json \
           ~/PersistenceServiceConfiguration.json.bak-2026-09-12

# 1. Stop → UI-Config weg → Dateien holen → Start   (~2 min Downtime, restoreOnStartup stellt Zustände wieder her)
sudo systemctl stop openhab
sudo mv /var/lib/openhab/jsondb/org.openhab.core.persistence.PersistenceServiceConfiguration.json /tmp/
cd /etc/openhab && sudo git pull
ls -la /etc/openhab/persistence/          # erwartet: 4 × .persist
sudo systemctl start openhab
```

**Prüfen**
- [ ] `grep -iE "persist" /var/log/openhab/openhab.log | tail -20` → keine Fehler/Warnungen zu `.persist`
- [ ] `ls /var/lib/openhab/jsondb/ | grep -i persist` → leer (UI-Config nicht neu angelegt)
- [ ] UI → Settings → Persistence: 4 Services, Konfiguration nicht editierbar (= aus Datei)
- [ ] UI → Model: Strasshof → Energie → Smart Meter (3 Werte) + Strompreis
- [ ] Nach ~10 min in InfluxDB/Grafana: `SmartMeter_Voltage_L1` ≈ 1 Punkt/min, `SmartMeter_Power` ≤ 6 Punkte/min,
      andere Items (z. B. Temperaturen) unverändert bei jeder Änderung

**Rollback**
```bash
sudo systemctl stop openhab
sudo mkdir -p /tmp/persist-rollback && sudo mv /etc/openhab/persistence/*.persist /tmp/persist-rollback/
sudo cp -p ~/PersistenceServiceConfiguration.json.bak-2026-09-12 \
           /var/lib/openhab/jsondb/org.openhab.core.persistence.PersistenceServiceConfiguration.json
sudo systemctl start openhab
```
Danach sauber auf Windows `git revert <commit>` + push, am Server `git checkout -- persistence/ && git pull`.

---

## Stufe 2 — Victron

**Voraussetzung:** Stufe 1 läuft stabil (Energie-Gruppen existieren, Drosselung aktiv).

**Was dazukommt:** `things/MQTT_Victron.things` (eigene Bridge zum Cerbo 10.1.0.50), `items/Victron.items`
(8 Dashboard- + 70 Diagnose-Items), `rules/victron_keepalive.rules` (ohne Keepalive sendet der Cerbo nach 60 s nichts mehr).

**Ablauf (Server):** `cd /etc/openhab && sudo git pull` — kein Restart nötig.

**Prüfen**
- [ ] UI → Things: `Victron Cerbo GX` + 8 Topic-Things ONLINE
- [ ] Nach ~10 s haben `Victron_Battery_Soc`, `Victron_PV_Power`, `Victron_Consumption` Werte (Full-Republish nach 5 s)
- [ ] `Victron_MultiPlus_Mode` / `Victron_ESS_MinSoc` haben Werte (kommen nur per Full-Republish)
- [ ] `tail -f /var/log/openhab/events.log` → keine Victron-Spannungen/-Leistungen, nur Status-Änderungen
- [ ] Generator aus → `Victron_Generator_ChargePower` nach 2 min = 0 W
- [ ] Grobe Plausibilität: `Victron_Consumption` ≈ `SmartMeter_Power` + `Victron_MultiPlus_AcOut_Power`

**Rollback:** Windows `git revert <commit>` + push, Server `git pull`. Die Bridge trennt sich, Keepalive-Rule verschwindet,
der Cerbo stellt das Publizieren nach 60 s von selbst ein.

---

## Offene Punkte
- [ ] Cerbo Security-Profil „Unsecured“ + IoT-VLAN: jeder im VLAN 100 kann `W/`-Topics schreiben → [[Hardening-Session]] / [[MQTT-Härtung]]
- [ ] MultiPlus AC-Eingang nicht verbunden (seit ~9 Tagen nur Wechselrichterbetrieb) — gewollt?
- [ ] Control-Channels (ESS-Sollwert, Min-SOC, Modus, Stromlimit) bewusst auskommentiert — bei Bedarf einzeln aktivieren
- [ ] Energie-Page (`pages/energy.yml`) für Dashboard + Diagnose
