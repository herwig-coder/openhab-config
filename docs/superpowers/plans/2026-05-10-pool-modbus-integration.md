# Pool Modbus Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate SugarValley Oxilife (salt chlorinator) and Poolsana InverPower Ultra (heat pump) into OpenHAB via a Waveshare 2-channel Modbus-TCP gateway, with full monitoring + control.

**Architecture:** Phased rollout. Hardware commissioning and register verification first, then OpenHAB read-only items, then write items, then rules and UI. Each phase has its own commit so risky pieces (writes, rules) are isolated and reversible.

**Tech Stack:** OpenHAB 4.x Modbus binding (`org.openhab.binding.modbus`), Waveshare 2-Ch Modbus-TCP-to-RTU gateway, RS485, Xtend rules DSL, JavaScript transforms (Nashorn-style `.js` files in `transform/`).

**Spec:** [docs/superpowers/specs/2026-05-10-pool-modbus-integration-design.md](../specs/2026-05-10-pool-modbus-integration-design.md)

**Convention used in this plan:**
- Tasks marked **[HW]** require physical hardware work (wiring, button presses on a device, web UI of the Waveshare adapter). They cannot be done by an agentic worker — the human user runs them and reports back.
- Tasks marked **[CFG]** are file edits / commits that an agent can do.
- Tasks marked **[VERIFY]** require an agent or human to observe a runtime side effect (logs, OH5 UI, Telegram message).
- Register addresses written `$REG_<name>` are placeholders that get filled in from the commissioning document `docs/pool-modbus-commissioning.md` produced in Task 4. Don't proceed past Task 7 until that document has concrete values.

---

## Phase 1 — Hardware Commissioning

### Task 1 — Configure the Waveshare gateway [HW]

**Files:**
- Create: `docs/pool-modbus-commissioning.md` (initial skeleton)

- [ ] **Step 1: Power up Waveshare and discover IP**

Connect Waveshare to LAN and 12 V supply. Each of the two RS485 channels has its own network interface — the device exposes **two MAC addresses, two IPs**, both via DHCP by default. Check the router DHCP table for both new MACs, or use the official `Vircom` discovery tool (Windows). Note both discovered IPs.

- [ ] **Step 2: Open Waveshare web UI for each interface**

Browser → `http://<discovered-ip-1>` for channel 1 and `http://<discovered-ip-2>` for channel 2. Each interface has its own admin UI. Default credentials are usually `admin` / `admin` (printed on the device label otherwise).

- [ ] **Step 3: Apply the full per-channel configuration in each interface's web UI**

The Waveshare web UI presents these sections (verified against firmware V1.486):
**Device Information**, **Network Settings**, **Serial Settings**, **Advanced Settings**, **Multi-Host Settings**, **Modify Web Login Key**.

Set every field per channel exactly as listed below. Fields marked **[CHANGE]** are different from the factory default and must be touched.

#### Channel 1 — SugarValley Oxilife (web UI of interface 1)

**Device Information**
| Field | Value | Note |
|---|---|---|
| Device Name | `PoolSalt` | **[CHANGE]** rename from default `WSDEV0001` for clarity |
| Firmware Version | (read-only) | expected ≥ V1.486 |
| Device MAC | (read-only) | record in commissioning doc |

**Network Settings**
| Field | Value | Note |
|---|---|---|
| Device IP | `10.1.0.18` | static |
| Device Port | `502` | **[CHANGE]** Modbus TCP standard port (factory default 4196) |
| Device Web Port | `80` | leave default |
| Work Mode | `TCP Server` | gateway listens for OpenHAB |
| Subnet Mask | `255.255.0.0` | `/16` per pfSense |
| Gateway | `10.1.0.1` | pfSense |
| Destination IP/DNS | `0.0.0.0` (or leave) | unused in TCP Server mode |
| Destination Port | `4196` (or leave) | unused in TCP Server mode |
| IP mode | `Static` | **[CHANGE]** factory default `DHCP` would overwrite the IP above on reboot |

**Serial Settings**
| Field | Value |
|---|---|
| Baud Rate | `19200` |
| Databits | `8` |
| Parity | `None` |
| Stopbits | `1` |
| Flow control | `None` |

**Advanced Settings**
| Field | Value | Note |
|---|---|---|
| No-Data-Restart | `Disable` | leave default |
| No Data Restart Time | `300` sec | leave default |
| Reconnect-time | `12` sec | leave default |

**Multi-Host Settings**
| Field | Value | Note |
|---|---|---|
| Protocol | `Modbus TCP to RTU` | critical — this is the gateway mode |
| Instruction Time out | `0` ms | auto when Multi-host disabled |
| Enable Multi-host | `No` | only OpenHAB polls |
| RS485 Conflict Time Gap | `0` ms | unused with single host |

**Modify Web Login Key:** leave empty unless you want to change the admin password.

#### Channel 2 — Poolsana InverPower Ultra (web UI of interface 2)

Identical to Channel 1 **except** these fields:

| Field | Value |
|---|---|
| Device Name | `PoolHeatPump` |
| Device IP | `10.1.0.21` |
| Baud Rate | `9600` |

All other fields (Device Port `502`, Subnet Mask `255.255.0.0`, Gateway `10.1.0.1`, Work Mode `TCP Server`, IP mode `Static`, Databits `8`, Parity `None`, Stopbits `1`, Flow control `None`, Protocol `Modbus TCP to RTU`, Enable Multi-host `No`, etc.) are the **same** as Channel 1.

- [ ] **Step 4: Click Submit on each interface and reboot the adapter**

The web UI requires a reboot for IP-mode and IP-address changes to take effect. After reboot, both interfaces should be reachable at their new static IPs.

Verify:

```bat
ping 10.1.0.18
ping 10.1.0.21
```

Both should reply.

**Recommended:** add a pfSense static DHCP mapping for each MAC → IP so the assignment is documented network-side and protected against an accidental factory reset.

- [ ] **Step 5: Create commissioning skeleton document**

Create `docs/pool-modbus-commissioning.md` with this exact starting content:

```markdown
# Pool Modbus Commissioning Log

## 1. Waveshare gateway

Firmware: V1.486 (or later)

| Channel | Device Name | IP        | Port | MAC                | Baud   | Parity | Slave id | Connected device           |
|---------|-------------|-----------|------|--------------------|--------|--------|----------|----------------------------|
| 1       | PoolSalt    | 10.1.0.18 | 502  | 04-EE-E8-13-A3-78  | 19200  | 8N1    | ?        | SugarValley Oxilife        |
| 2       | PoolHeatPump| 10.1.0.21 | 502  | (record from UI)   | 9600   | 8N1    | ?        | Poolsana InverPower Ultra  |

Common settings on both channels:
- Work Mode: TCP Server
- Subnet Mask: 255.255.0.0
- Gateway: 10.1.0.1
- IP mode: Static
- Protocol: Modbus TCP to RTU
- Enable Multi-host: No
- Reconnect-time: 12 s

## 2. SugarValley Oxilife — verified registers

(filled in Task 3)

## 3. Poolsana InverPower Ultra — verified registers

(filled in Task 3)
```

- [ ] **Step 6: Commit the skeleton**

```bash
git add docs/pool-modbus-commissioning.md
git commit -m "docs: pool modbus commissioning skeleton"
```

---

### Task 2 — RS485 wiring [HW]

- [ ] **Step 1: Wire channel 1 (Oxilife)**

Three wires from Waveshare channel-1 terminal block to the Oxilife Modbus port: `A` (D+), `B` (D−), `GND`. Use one twisted pair (e.g. CAT-cable orange/orange-white) for A/B and a separate conductor for GND.

- [ ] **Step 2: Wire channel 2 (heat pump)**

Same A/B/GND from channel-2 terminal block to the InverPower Ultra Modbus port.

- [ ] **Step 3: Apply termination**

If either run is longer than ~3 m, place a 120 Ω resistor across A/B at *each* end of that run. The Waveshare often has a built-in DIP/jumper for the gateway end; the device end usually needs an external resistor (or a built-in termination jumper if the device exposes one).

- [ ] **Step 4: Power on devices and confirm link lights**

Both channel LEDs on the Waveshare should be present; once the binding starts polling later, the TX/RX LEDs will blink.

(Nothing to commit — physical work only.)

---

### Task 3 — Discover and verify registers with `modpoll` [HW] [VERIFY]

**Files:**
- Modify: `docs/pool-modbus-commissioning.md`

- [ ] **Step 1: Install modpoll on Windows**

Download `modpoll` from `https://www.modbusdriver.com/modpoll.html`, unzip, add to PATH.

- [ ] **Step 2: Pull the SugarValley Oxilife official Modbus document**

The user has noted official documentation exists. Fetch the PDF/spreadsheet (search for "SugarValley NeoPool Modbus" or the Hayward equivalent — Oxilife uses the same protocol family). Extract for each datapoint listed in the design spec table "SugarValley Oxilife — read/write": the register address (decimal), function code (3 = holding, 4 = input), data type (int16, uint16, int32), and scaling factor.

- [ ] **Step 3: Read each Oxilife register**

For every datapoint, run (substituting `<addr>` with the address from the doc, `<count>` = 1 or 2):

```bat
modpoll -m tcp -a 1 -r <addr> -c <count> -t 4:int -1 10.1.0.18 -p 502
```

`-t 4:int` reads holding registers as int16. Use `-t 3:int` for input registers, `-t 4:hex` for unknown content. `-1` performs one poll then exits.

A live, plausible value (e.g. pH around 700 = 7.00 with /100 scaling, water temp around 250 = 25.0 °C with /10 scaling) confirms the address. Record observed raw value, scaling, and engineering unit.

- [ ] **Step 4: Read each Poolsana InverPower Ultra register**

Repeat Step 3 against `10.1.0.21:502` with the community-sourced addresses (search "InverPower Ultra Modbus" or "IPS Pro Modbus map" — Poolsana rebrands a Phnix/IPS-Pro inverter). For each address, sanity-check the read value before trusting it. If a register returns garbage or a Modbus exception 02 (illegal address) / 03 (illegal value), drop that datapoint from the design — YAGNI.

```bat
modpoll -m tcp -a 1 -r <addr> -c 1 -t 4:int -1 10.1.0.21 -p 502
```

- [ ] **Step 5: Fill in `docs/pool-modbus-commissioning.md`**

Replace sections 2 and 3 with a verified register table. Use this exact format so later tasks can grep:

```markdown
## 2. SugarValley Oxilife — verified registers

| Item                          | FC | Addr | Type   | Scale | Unit | RW | Notes |
|-------------------------------|----|------|--------|-------|------|----|-------|
| Pool_Salt_pH                  | 3  | 100  | int16  | /100  | —    | R  | live: 712 → 7.12 |
| Pool_Salt_ORP                 | 3  | 101  | int16  | x1    | mV   | R  | live: 720 |
| Pool_Salt_Salinity            | 3  | 102  | int16  | /10   | g/L  | R  | live: 45 → 4.5 |
| Pool_Salt_WaterTemp           | 3  | 103  | int16  | /10   | °C   | R  | live: 248 → 24.8 |
| Pool_Salt_Production          | 3  | 104  | int16  | x1    | %    | R  |       |
| Pool_Salt_FlowAlarm           | 3  | 110  | uint16 | x1    | bit  | R  | 0/1   |
| Pool_Salt_LowSaltAlarm        | 3  | 111  | uint16 | x1    | bit  | R  | 0/1   |
| Pool_Salt_CellPolarity        | 3  | 112  | int16  | x1    | —    | R  |       |
| Pool_Salt_Setpoint_pH         | 3  | 200  | int16  | /100  | —    | RW | echoed |
| Pool_Salt_Setpoint_ORP        | 3  | 201  | int16  | x1    | mV   | RW |       |
| Pool_Salt_Setpoint_Production | 3  | 202  | int16  | x1    | %    | RW |       |
| Pool_Salt_Mode                | 3  | 203  | uint16 | x1    | enum | RW | 0=Off 1=Auto 2=Boost 3=Manual |

(Above values are illustrative — replace with actual addresses/values from the official doc and live reads.)
```

Same table format for section 3 (heat pump). Drop any row whose register did not respond cleanly during Step 3/4.

- [ ] **Step 6: Commit the verified commissioning log**

```bash
git add docs/pool-modbus-commissioning.md
git commit -m "docs: verified pool modbus register map (commissioning)"
```

**Gate:** Phase 2 cannot start until `docs/pool-modbus-commissioning.md` has both Oxilife and heat pump tables populated with actually-verified addresses.

---

## Phase 2 — Read-Only OpenHAB Integration

### Task 4 — Install the Modbus binding [HW]

- [ ] **Step 1: Install via OpenHAB UI**

Browser → `http://10.1.100.101:8080` → Settings → Add-ons → Bindings → search "Modbus" → install **Modbus Binding** (the umbrella one — the TCP and serial sub-bindings come with it).

- [ ] **Step 2: Verify install**

OpenHAB main UI → Settings → Things → Add Thing → "Modbus Binding" should appear in the list. (We won't add things via the UI — but its presence confirms the bundle started.)

(No file changes — OpenHAB stores add-on state separately.)

---

### Task 5 — Create the JS transforms [CFG]

**Files:**
- Create: `transform/div10.js`
- Create: `transform/div100.js`
- Create: `transform/mul10.js`
- Create: `transform/mul100.js`

- [ ] **Step 1: Create `transform/div10.js`**

```javascript
(function(i) {
    return parseFloat(i) / 10.0;
})(input)
```

- [ ] **Step 2: Create `transform/div100.js`**

```javascript
(function(i) {
    return parseFloat(i) / 100.0;
})(input)
```

- [ ] **Step 3: Create `transform/mul10.js`**

```javascript
(function(i) {
    return Math.round(parseFloat(i) * 10.0);
})(input)
```

- [ ] **Step 4: Create `transform/mul100.js`**

```javascript
(function(i) {
    return Math.round(parseFloat(i) * 100.0);
})(input)
```

- [ ] **Step 5: Verify JS transformation add-on installed**

OpenHAB UI → Settings → Add-ons → Transformations → install **JavaScript Transformation** if not already present. (One-time, like the Modbus binding.)

- [ ] **Step 6: Commit**

```bash
git add transform/div10.js transform/div100.js transform/mul10.js transform/mul100.js
git commit -m "add: js transforms for modbus scaling (div/mul 10/100)"
```

---

### Task 6 — Add semantic-model equipment groups [CFG]

**Files:**
- Modify: `items/semantic_model.items` (after line 44, the existing `gPoolEngineering` group)

- [ ] **Step 1: Read current location**

Find the line in `items/semantic_model.items` that defines `gPoolEngineering`:

```
Group    gPoolEngineering   "Pooltechnik"         <if:ic:baseline-engineering>  (gPool)          ["Location","Pooltechnik"]                 {widgetOrder="280"}
```

- [ ] **Step 2: Insert the two new equipment groups directly after that line**

```
Group    gPool_SaltSystem   "Salzanlage Oxilife"  <if:mdi:flask>                (gPoolEngineering) ["Equipment"]                            {widgetOrder="281"}
Group    gPool_HeatPump     "Wärmepumpe Poolsana" <if:mdi:heat-pump>            (gPoolEngineering) ["Equipment"]                            {widgetOrder="282"}
```

- [ ] **Step 3: Reload — OpenHAB watches `items/`. No restart.**

Verify in OH5 Model view: under `gPool` → `gPoolEngineering` you should see two new empty equipment groups.

- [ ] **Step 4: Commit**

```bash
git add items/semantic_model.items
git commit -m "add: semantic groups for pool salt system and heat pump"
```

---

### Task 7 — Create read-only Modbus things [CFG]

**Files:**
- Create: `things/Modbus_Pool.things`

**Pre-condition:** `docs/pool-modbus-commissioning.md` is filled in (Task 3 done). Replace `$REG_*` below with the actual addresses from that document.

- [ ] **Step 1: Create the things file with both bridges and the read pollers**

```xtend
// Pool Modbus Integration — Waveshare 2-Channel Gateway
// Each RS485 channel exposes its own IP, both on Modbus TCP port 502.
// Channel 1: 10.1.0.18 → SugarValley Oxilife salt chlorinator (19200 8N1)
// Channel 2: 10.1.0.21 → Poolsana InverPower Ultra heat pump (9600 8N1)
// Register addresses verified in docs/pool-modbus-commissioning.md

// ---------- Salt System (Oxilife) ----------
Bridge modbus:tcp:oxilife "Oxilife TCP" [
    host="10.1.0.18",
    port=502,
    id=1,
    timeBetweenTransactionsMillis=100,
    timeBetweenReconnectMillis=10000,
    connectMaxTries=3,
    reconnectAfterMillis=30000
] {
    // Group reads by contiguous block. Adjust start/length to actual addresses.
    Bridge poller readings "Readings" [start=$REG_OXI_BLOCK1_START, length=$REG_OXI_BLOCK1_LEN, refresh=10000, type="holding"] {
        Thing data ph              "pH"             [readStart="$REG_PH",            readValueType="int16",  readTransform="JS(div100.js)"]
        Thing data orp             "ORP"            [readStart="$REG_ORP",           readValueType="int16"]
        Thing data salinity        "Salinity"       [readStart="$REG_SALINITY",      readValueType="int16",  readTransform="JS(div10.js)"]
        Thing data waterTemp       "Water Temp"     [readStart="$REG_SALT_WATERTEMP", readValueType="int16", readTransform="JS(div10.js)"]
        Thing data production      "Production"    [readStart="$REG_PRODUCTION",    readValueType="int16"]
    }
    Bridge poller alarms "Alarms" [start=$REG_OXI_BLOCK2_START, length=$REG_OXI_BLOCK2_LEN, refresh=10000, type="holding"] {
        Thing data flowAlarm       "Flow Alarm"     [readStart="$REG_FLOW_ALARM",    readValueType="uint16"]
        Thing data lowSaltAlarm    "Low Salt Alarm" [readStart="$REG_LOWSALT_ALARM", readValueType="uint16"]
        Thing data cellPolarity    "Cell Polarity"  [readStart="$REG_CELL_POLARITY", readValueType="int16"]
    }
}

// ---------- Heat Pump (Poolsana InverPower Ultra) ----------
Bridge modbus:tcp:heatpump "Heat Pump TCP" [
    host="10.1.0.21",
    port=502,
    id=1,
    timeBetweenTransactionsMillis=100,
    timeBetweenReconnectMillis=10000,
    connectMaxTries=3,
    reconnectAfterMillis=30000
] {
    Bridge poller readings "Readings" [start=$REG_HP_BLOCK1_START, length=$REG_HP_BLOCK1_LEN, refresh=10000, type="holding"] {
        Thing data waterTempIn     "Water In"       [readStart="$REG_HP_WATER_IN",   readValueType="int16",  readTransform="JS(div10.js)"]
        Thing data waterTempOut    "Water Out"      [readStart="$REG_HP_WATER_OUT",  readValueType="int16",  readTransform="JS(div10.js)"]
        Thing data ambientTemp     "Ambient"        [readStart="$REG_HP_AMBIENT",    readValueType="int16",  readTransform="JS(div10.js)"]
        Thing data compressorState "Compressor"     [readStart="$REG_HP_COMPRESSOR", readValueType="uint16"]
        Thing data fanSpeed        "Fan Speed"      [readStart="$REG_HP_FAN",        readValueType="int16"]
        Thing data power           "Power"          [readStart="$REG_HP_POWER",      readValueType="int16"]
        Thing data errorCode       "Error Code"     [readStart="$REG_HP_ERROR",      readValueType="int16"]
        Thing data status          "Status"         [readStart="$REG_HP_STATUS",     readValueType="int16"]
    }
}
```

- [ ] **Step 2: Substitute every `$REG_*` placeholder**

Open `docs/pool-modbus-commissioning.md` side-by-side. For every `$REG_…`, paste the verified address from the table. Determine block start/length per poller as `min(addresses)` and `max(addresses)−min(addresses)+1`.

- [ ] **Step 3: Save and watch openhab.log**

```bash
ssh herwig@10.1.100.101 'tail -f /var/log/openhab/openhab.log'
```

Expected lines within 10 s of saving:

```
[INFO ] [...modbus.handler.ModbusTcpThingHandler] - About to connect ...10.1.0.18:502
[INFO ] [...modbus.handler.ModbusTcpThingHandler] - About to connect ...10.1.0.21:502
[INFO ] [...modbus.handler.ModbusPollerThingHandler] - Poller readings updating ...
```

If you see exception `Connection refused`, the Waveshare config from Task 1 is wrong. If `Modbus exception code 2` appears, an address is wrong — fix in commissioning doc, then re-edit the things file.

- [ ] **Step 4: Verify all things show ONLINE in OH5**

OH5 → Settings → Things → filter "modbus" → all `modbus:data:*` entries should be ONLINE (green). Click any one → "Channels" tab → see a "Number" channel with a current value matching what `modpoll` returned.

- [ ] **Step 5: Commit**

```bash
git add things/Modbus_Pool.things
git commit -m "add: read-only modbus things for pool salt system and heat pump"
```

---

### Task 8 — Create read-only items linked to Modbus channels [CFG]

**Files:**
- Create: `items/pool_modbus.items`

- [ ] **Step 1: Create the items file**

```xtend
// Pool Modbus Items
// Read-only items (Phase 2). Write items added in Phase 3.
// Channels are auto-named by the Modbus binding: modbus:data:<bridge>:<poller>:<thing>:number (or :switch / :string)

Group gPool_SaltSystem_All "Salzanlage Werte" (gPool_SaltSystem)
Group gPool_HeatPump_All   "Wärmepumpe Werte" (gPool_HeatPump)

// ---------- SugarValley Oxilife ----------
Number               Pool_Salt_pH            "Pool pH [%.2f]"                <if:mdi:flask>            (gPool_SaltSystem, gPool_SaltSystem_All)  ["Measurement","pH"]                  {channel="modbus:data:oxilife:readings:ph:number"}
Number:Dimensionless Pool_Salt_ORP           "Pool ORP [%d mV]"              <if:mdi:flash>            (gPool_SaltSystem, gPool_SaltSystem_All)  ["Measurement"]                       {unit="mV", channel="modbus:data:oxilife:readings:orp:number"}
Number               Pool_Salt_Salinity      "Pool Salzgehalt [%.1f g/L]"    <if:mdi:shaker-outline>   (gPool_SaltSystem, gPool_SaltSystem_All)  ["Measurement"]                       {channel="modbus:data:oxilife:readings:salinity:number"}
Number:Temperature   Pool_Salt_WaterTemp     "Pool Salz Wassertemp [%.1f °C]" <if:mdi:thermometer>     (gPool_SaltSystem, gPool_SaltSystem_All)  ["Measurement","Temperature"]         {unit="°C", channel="modbus:data:oxilife:readings:waterTemp:number"}
Number:Dimensionless Pool_Salt_Production    "Pool Chlorproduktion [%d %%]"  <if:mdi:percent>          (gPool_SaltSystem, gPool_SaltSystem_All)  ["Status"]                            {unit="%", channel="modbus:data:oxilife:readings:production:number"}
Switch               Pool_Salt_FlowAlarm     "Pool Salz Flow Alarm"          <if:mdi:water-alert>      (gPool_SaltSystem, gPool_SaltSystem_All)  ["Alarm"]                             {channel="modbus:data:oxilife:alarms:flowAlarm:switch"}
Switch               Pool_Salt_LowSaltAlarm  "Pool Salz Niedrig Alarm"       <if:mdi:alert>            (gPool_SaltSystem, gPool_SaltSystem_All)  ["Alarm"]                             {channel="modbus:data:oxilife:alarms:lowSaltAlarm:switch"}
Number               Pool_Salt_CellPolarity  "Pool Salz Zellpolarität"       <if:mdi:swap-horizontal>  (gPool_SaltSystem, gPool_SaltSystem_All)  ["Status"]                            {channel="modbus:data:oxilife:alarms:cellPolarity:number"}

// ---------- Poolsana InverPower Ultra ----------
Number:Temperature   Pool_HP_WaterTempIn     "WP Wasser Zulauf [%.1f °C]"    <if:mdi:thermometer-low>    (gPool_HeatPump, gPool_HeatPump_All) ["Measurement","Temperature"]      {unit="°C", channel="modbus:data:heatpump:readings:waterTempIn:number"}
Number:Temperature   Pool_HP_WaterTempOut    "WP Wasser Ablauf [%.1f °C]"    <if:mdi:thermometer-high>   (gPool_HeatPump, gPool_HeatPump_All) ["Measurement","Temperature"]      {unit="°C", channel="modbus:data:heatpump:readings:waterTempOut:number"}
Number:Temperature   Pool_HP_AmbientTemp     "WP Außenluft [%.1f °C]"        <if:mdi:weather-windy>      (gPool_HeatPump, gPool_HeatPump_All) ["Measurement","Temperature"]      {unit="°C", channel="modbus:data:heatpump:readings:ambientTemp:number"}
Switch               Pool_HP_CompressorState "WP Kompressor"                 <if:mdi:engine>             (gPool_HeatPump, gPool_HeatPump_All) ["Status"]                          {channel="modbus:data:heatpump:readings:compressorState:switch"}
Number               Pool_HP_FanSpeed        "WP Lüfterdrehzahl [%d]"        <if:mdi:fan>                (gPool_HeatPump, gPool_HeatPump_All) ["Status"]                          {channel="modbus:data:heatpump:readings:fanSpeed:number"}
Number:Power         Pool_HP_Power           "WP Leistung [%d W]"            <if:mdi:lightning-bolt>     (gPool_HeatPump, gPool_HeatPump_All) ["Measurement","Power"]            {unit="W", channel="modbus:data:heatpump:readings:power:number"}
Number               Pool_HP_ErrorCode       "WP Fehlercode [%d]"            <if:mdi:alert-circle>       (gPool_HeatPump, gPool_HeatPump_All) ["Alarm"]                           {channel="modbus:data:heatpump:readings:errorCode:number"}
Number               Pool_HP_StatusRaw       "WP Status (raw) [%d]"          <if:mdi:state-machine>      (gPool_HeatPump, gPool_HeatPump_All) ["Status"]                          {channel="modbus:data:heatpump:readings:status:number"}
```

- [ ] **Step 2: Drop any items whose register was not verified**

If Task 3 dropped a Poolsana register (e.g. fan speed not exposed), delete the matching `Pool_HP_FanSpeed` line. YAGNI — no items without working channels.

- [ ] **Step 3: Save and verify in OH5**

OH5 → Model → `gPool` → `gPoolEngineering` → both equipment groups should now show all listed items, each with a current value.

Open `events.log` (`tail -f /var/log/openhab/events.log` on the server) — within 10–30 s every item should emit at least one state-update event.

- [ ] **Step 4: 24-hour soak**

Leave the system running. Re-check the next day:
- No `Pool_*` items stuck on `NULL` or `UNDEF`
- No spam errors in `openhab.log` related to `modbus.*`
- Values still updating (compare a temperature now vs. ten minutes ago — should differ slightly)

If a value is implausible (e.g. pH = 32700 = signed-int overflow), the `readValueType` is wrong — switch between `int16` ↔ `uint16` ↔ `int32` and re-test.

- [ ] **Step 5: Commit**

```bash
git add items/pool_modbus.items
git commit -m "add: read-only modbus items for pool salt system and heat pump"
```

---

## Phase 3 — Read-Write Control

### Task 9 — Add write pollers and data things [CFG]

**Files:**
- Modify: `things/Modbus_Pool.things`

- [ ] **Step 1: Add a setpoints poller inside the `oxilife` bridge**

Insert after the `alarms` poller, still inside the `oxilife` bridge braces:

```xtend
    Bridge poller setpoints "Setpoints" [start=$REG_OXI_SP_START, length=$REG_OXI_SP_LEN, refresh=30000, type="holding"] {
        Thing data setpointPh         "Setpoint pH"          [readStart="$REG_SP_PH",         readValueType="int16",  readTransform="JS(div100.js)", writeStart="$REG_SP_PH",         writeValueType="int16",  writeTransform="JS(mul100.js)", writeType="holding"]
        Thing data setpointOrp        "Setpoint ORP"         [readStart="$REG_SP_ORP",        readValueType="int16",                                  writeStart="$REG_SP_ORP",        writeValueType="int16",                                writeType="holding"]
        Thing data setpointProduction "Setpoint Production"  [readStart="$REG_SP_PROD",       readValueType="int16",                                  writeStart="$REG_SP_PROD",       writeValueType="int16",                                writeType="holding"]
        Thing data mode               "Mode"                 [readStart="$REG_SP_MODE",       readValueType="uint16",                                 writeStart="$REG_SP_MODE",       writeValueType="uint16",                               writeType="holding"]
    }
```

Substitute placeholders from `docs/pool-modbus-commissioning.md` (the RW rows in section 2).

- [ ] **Step 2: Add a setpoints poller inside the `heatpump` bridge**

Insert before the closing `}` of the `heatpump` bridge:

```xtend
    Bridge poller setpoints "Setpoints" [start=$REG_HP_SP_START, length=$REG_HP_SP_LEN, refresh=30000, type="holding"] {
        Thing data setpoint "Setpoint" [readStart="$REG_HP_SP",   readValueType="int16",  readTransform="JS(div10.js)", writeStart="$REG_HP_SP",   writeValueType="int16",  writeTransform="JS(mul10.js)", writeType="holding"]
        Thing data mode     "Mode"     [readStart="$REG_HP_MODE", readValueType="uint16",                                writeStart="$REG_HP_MODE", writeValueType="uint16",                                writeType="holding"]
        Thing data onoff    "On/Off"   [readStart="$REG_HP_ONOFF",readValueType="uint16",                                writeStart="$REG_HP_ONOFF",writeValueType="uint16",                                writeType="holding"]
    }
```

- [ ] **Step 3: Save, watch the log**

Same `tail -f openhab.log`. Expect new poller bridges going ONLINE. Verify in OH5 → Things filter "setpoints" — all data things ONLINE.

- [ ] **Step 4: Commit**

```bash
git add things/Modbus_Pool.things
git commit -m "add: write-capable modbus things for pool setpoints"
```

---

### Task 10 — Add write items [CFG]

**Files:**
- Modify: `items/pool_modbus.items`

- [ ] **Step 1: Append the write items block**

```xtend
// ---------- Setpoints (write-capable) ----------
Number               Pool_Salt_Setpoint_pH         "Pool pH Sollwert [%.2f]"        <if:mdi:flask-outline>   (gPool_SaltSystem, gPool_SaltSystem_All)  ["Setpoint"]               {channel="modbus:data:oxilife:setpoints:setpointPh:number"}
Number:Dimensionless Pool_Salt_Setpoint_ORP        "Pool ORP Sollwert [%d mV]"      <if:mdi:flash-outline>   (gPool_SaltSystem, gPool_SaltSystem_All)  ["Setpoint"]               {unit="mV", channel="modbus:data:oxilife:setpoints:setpointOrp:number"}
Number:Dimensionless Pool_Salt_Setpoint_Production "Pool Produktion Sollwert [%d %%]" <if:mdi:percent>      (gPool_SaltSystem, gPool_SaltSystem_All)  ["Setpoint"]               {unit="%", channel="modbus:data:oxilife:setpoints:setpointProduction:number"}
Number               Pool_Salt_Mode                "Pool Salzanlage Modus [%d]"     <if:mdi:cog>             (gPool_SaltSystem, gPool_SaltSystem_All)  ["Control"]                {channel="modbus:data:oxilife:setpoints:mode:number"}

Number:Temperature   Pool_HP_Setpoint              "WP Solltemperatur [%.1f °C]"    <if:mdi:thermometer-plus> (gPool_HeatPump, gPool_HeatPump_All)     ["Setpoint","Temperature"]  {unit="°C", channel="modbus:data:heatpump:setpoints:setpoint:number"}
Number               Pool_HP_Mode                  "WP Modus [%d]"                  <if:mdi:cog>              (gPool_HeatPump, gPool_HeatPump_All)     ["Control"]                 {channel="modbus:data:heatpump:setpoints:mode:number"}
Switch               Pool_HP_OnOff                 "WP Ein/Aus"                     <if:mdi:power>            (gPool_HeatPump, gPool_HeatPump_All)     ["Switch"]                  {channel="modbus:data:heatpump:setpoints:onoff:switch"}
```

- [ ] **Step 2: Save and verify reads work first**

Before any write attempt, confirm each new setpoint item shows the device's *current* setpoint value (read-side of the data thing). Otherwise the registers are wrong.

- [ ] **Step 3: Commit**

```bash
git add items/pool_modbus.items
git commit -m "add: write-capable modbus items for pool setpoints"
```

---

### Task 11 — Test each write individually [VERIFY]

**Method per setpoint:**
1. Note current value in OH5.
2. From the OH5 item detail view, set a new value differing by a small, safe amount (see table below).
3. Watch `events.log` for `Pool_X received command Y` followed by `Pool_X changed from A to Y`.
4. Verify on the physical device's display panel that the setpoint changed.
5. Wait 30 s for the next read poll → OH5 echo confirms the value persists.
6. Restore original value.

**Safe deltas for testing:**

| Item | Safe test value |
|---|---|
| `Pool_Salt_Setpoint_pH` | current ± 0.05 |
| `Pool_Salt_Setpoint_ORP` | current ± 10 mV |
| `Pool_Salt_Setpoint_Production` | current ± 5 % |
| `Pool_Salt_Mode` | swap Auto ↔ Manual then back |
| `Pool_HP_Setpoint` | current ± 0.5 °C |
| `Pool_HP_Mode` | swap Heat ↔ Auto then back |
| `Pool_HP_OnOff` | OFF → ON → OFF (only when filter pump is running) |

- [ ] **Step 1: Run through each row of the table above**

If any write *appears* to succeed in events.log but the device display does not change, the write register is wrong → revert and update commissioning doc + things file.

- [ ] **Step 2: Watch openhab.log for `Modbus exception code N`**

| Code | Meaning | Likely cause |
|---|---|---|
| 1 | Illegal function | Wrong `writeType` |
| 2 | Illegal data address | Wrong `writeStart` |
| 3 | Illegal data value | Out-of-range value or wrong scaling |
| 4 | Slave device failure | Device not ready / interlock violated |

- [ ] **Step 3: Phase 3 done — no extra commit unless fixes were needed**

If you had to fix register addresses during this task, commit the fixes:

```bash
git add things/Modbus_Pool.things docs/pool-modbus-commissioning.md
git commit -m "fix: correct pool modbus write register addresses after live test"
```

---

## Phase 4 — Rules and Optional UI

### Task 12 — Filter-coupling dry-run protection rule [CFG]

**Files:**
- Create: `rules/pool_modbus.rules`

- [ ] **Step 1: Create the rules file with the dry-run protection rule**

```xtend
// Pool Modbus rules — see docs/superpowers/specs/2026-05-10-pool-modbus-integration-design.md

import org.openhab.core.library.types.OnOffType
import org.openhab.core.library.types.DecimalType

// --- Heat pump dry-run protection -----------------------------------
// When filter pump goes OFF, force heat pump OFF (no flow → unsafe).
// When filter pump comes ON, do nothing — user must re-enable manually.

rule "Pool HP dry-run protection"
when
    Item Pool_Filtering changed
then
    if (Pool_Filtering.state == OFF) {
        if (Pool_HP_OnOff.state == ON) {
            logInfo("PoolModbus", "Filter OFF — forcing heat pump OFF (dry-run protection)")
            Pool_HP_OnOff.sendCommand(OFF)
        }
    }
end

// --- Salt system dry-run protection ---------------------------------
// When filter pump goes OFF, force salt production to 0.
// Mode value 0 = Off (verify against commissioning doc enum).

rule "Pool Salt dry-run protection"
when
    Item Pool_Filtering changed
then
    if (Pool_Filtering.state == OFF) {
        if ((Pool_Salt_Mode.state as Number).intValue != 0) {
            logInfo("PoolModbus", "Filter OFF — forcing salt mode to Off (dry-run protection)")
            Pool_Salt_Mode.sendCommand(0)
        }
    }
end
```

- [ ] **Step 2: Save and watch openhab.log**

Toggle `Pool_Filtering` OFF (via OH5 or KNX). In `openhab.log`, expect:

```
[INFO ] [...PoolModbus] - Filter OFF — forcing heat pump OFF (dry-run protection)
[INFO ] [...PoolModbus] - Filter OFF — forcing salt mode to Off (dry-run protection)
```

In `events.log`: `Pool_HP_OnOff received command OFF` and `Pool_Salt_Mode received command 0`. Verify both at the devices.

- [ ] **Step 3: Restore filter ON, commit**

```bash
git add rules/pool_modbus.rules
git commit -m "add: pool modbus dry-run protection rules (filter coupling)"
```

---

### Task 13 — Telegram alert rules [CFG]

**Files:**
- Modify: `rules/pool_modbus.rules`

- [ ] **Step 1: Identify the existing Telegram action name**

In an existing rule file (e.g. `rules/senddewpointalert_FIXED.rules`), find the Telegram bot reference. Typical pattern:

```xtend
val telegramAction = getActions("telegram", "telegram:telegramBot:<botId>")
```

Note the exact Thing UID — same one used for new rules.

- [ ] **Step 2: Append alert rules to `rules/pool_modbus.rules`**

```xtend
// --- Telegram alerts ------------------------------------------------

rule "Pool Salt flow alarm"
when
    Item Pool_Salt_FlowAlarm changed to ON
then
    val telegramAction = getActions("telegram", "telegram:telegramBot:<REPLACE_WITH_BOT_UID>")
    telegramAction?.sendTelegram("⚠️ Pool Salzanlage: Kein Wasserdurchfluss!")
    logWarn("PoolModbus", "Salt flow alarm triggered")
end

rule "Pool Salt low-salt alarm"
when
    Item Pool_Salt_LowSaltAlarm changed to ON
then
    val telegramAction = getActions("telegram", "telegram:telegramBot:<REPLACE_WITH_BOT_UID>")
    telegramAction?.sendTelegram("⚠️ Pool Salzanlage: Salzgehalt zu niedrig — bitte nachsalzen!")
    logWarn("PoolModbus", "Low salt alarm triggered")
end

rule "Pool heat pump error"
when
    Item Pool_HP_ErrorCode changed
then
    val code = (Pool_HP_ErrorCode.state as Number).intValue
    if (code != 0) {
        val telegramAction = getActions("telegram", "telegram:telegramBot:<REPLACE_WITH_BOT_UID>")
        telegramAction?.sendTelegram("⚠️ Pool Wärmepumpe Fehler-Code: " + code)
        logWarn("PoolModbus", "Heat pump error code: " + code)
    }
end
```

Replace `<REPLACE_WITH_BOT_UID>` with the actual bot UID found in Step 1.

- [ ] **Step 3: Test by simulating an alarm**

Quickest test: temporarily set `Pool_HP_ErrorCode` from the OH5 item detail view to a non-zero value (this won't write to Modbus because the item is read-only on the binding side, but the rule fires on item state change). Telegram should beep within seconds.

If no message arrives:
- Check the Telegram thing UID is correct
- Confirm internet on the OpenHAB server
- Check `openhab.log` for `Telegram action` errors

- [ ] **Step 4: Commit**

```bash
git add rules/pool_modbus.rules
git commit -m "add: pool modbus telegram alerts for flow/salt/hp-error"
```

---

### Task 14 — Connection watchdog rule [CFG]

**Files:**
- Modify: `rules/pool_modbus.rules`
- Modify: `items/pool_modbus.items`

- [ ] **Step 1: Add status items to `items/pool_modbus.items`**

Append:

```xtend
// Bridge status items (driven by Modbus thing status, not channel)
String Pool_Modbus_Oxilife_Status  "Oxilife Modbus Status [%s]"   <if:mdi:lan>  (gPool_SaltSystem)
String Pool_Modbus_Heatpump_Status "Heatpump Modbus Status [%s]"  <if:mdi:lan>  (gPool_HeatPump)
```

These are *not* linked via channel — they are populated by a rule via the `getThingStatusInfo` action.

- [ ] **Step 2: Append the watchdog rule to `rules/pool_modbus.rules`**

```xtend
// --- Modbus connection watchdog -------------------------------------
// Polls the Thing status of both TCP bridges every minute.
// Sends a Telegram alert on transition into non-ONLINE.

var String oxilifeLastStatus = "ONLINE"
var String heatpumpLastStatus = "ONLINE"

rule "Pool Modbus connection watchdog"
when
    Time cron "0 * * * * ?"
then
    val oxStatus  = getThingStatusInfo("modbus:tcp:oxilife")?.getStatus?.toString  ?: "UNKNOWN"
    val hpStatus  = getThingStatusInfo("modbus:tcp:heatpump")?.getStatus?.toString ?: "UNKNOWN"
    Pool_Modbus_Oxilife_Status.postUpdate(oxStatus)
    Pool_Modbus_Heatpump_Status.postUpdate(hpStatus)

    if (oxStatus != "ONLINE" && oxilifeLastStatus == "ONLINE") {
        val telegramAction = getActions("telegram", "telegram:telegramBot:<REPLACE_WITH_BOT_UID>")
        telegramAction?.sendTelegram("⚠️ Modbus Salzanlage offline: " + oxStatus)
        logWarn("PoolModbus", "Oxilife bridge went " + oxStatus)
    }
    if (hpStatus != "ONLINE" && heatpumpLastStatus == "ONLINE") {
        val telegramAction = getActions("telegram", "telegram:telegramBot:<REPLACE_WITH_BOT_UID>")
        telegramAction?.sendTelegram("⚠️ Modbus Wärmepumpe offline: " + hpStatus)
        logWarn("PoolModbus", "Heatpump bridge went " + hpStatus)
    }

    oxilifeLastStatus = oxStatus
    heatpumpLastStatus = hpStatus
end
```

Replace bot UID as before.

- [ ] **Step 3: Test by unplugging the Waveshare network cable for ~2 min**

Watch `openhab.log`. After ~30 s the TCP bridge should go OFFLINE, then on the next minute boundary the watchdog rule fires and sends Telegram. Replug — within ~30 s status returns to ONLINE.

- [ ] **Step 4: Commit**

```bash
git add rules/pool_modbus.rules items/pool_modbus.items
git commit -m "add: pool modbus connection watchdog with telegram alert"
```

---

### Task 15 — Awattar coupling (optional)

**Files:**
- Modify: `rules/pool_modbus.rules`

**Skip if** you don't want price-based heat pump scheduling yet.

- [ ] **Step 1: Identify the Awattar price item**

`grep -r '^Number.*Awattar' items/Awattar.items` — pick the item that holds the current cent/kWh price (typical name `Awattar_CurrentPrice` or `Awattar_Now`). If unsure, log it once:

```xtend
rule "DEBUG awattar items"
when System started
then
    Awattar.allMembers.forEach[ logInfo("PoolModbus", it.name + " = " + it.state) ]
end
```

- [ ] **Step 2: Append the price-coupling rule**

```xtend
// --- Awattar low-price heat pump enable -----------------------------
// When current spot price is below threshold AND pool not at setpoint
// AND filter is running → ensure heat pump ON.
// When price exceeds upper threshold → switch off (saves money).

val Number AWATTAR_CHEAP_LIMIT_CT = 8.0    // ct/kWh
val Number AWATTAR_PRICY_LIMIT_CT = 25.0   // ct/kWh

rule "Pool HP awattar price scheduler"
when
    Item Awattar_CurrentPrice changed
then
    if (Pool_Filtering.state != ON) return;
    val price    = (Awattar_CurrentPrice.state as Number).doubleValue
    val current  = (Pool_HP_WaterTempIn.state as Number).doubleValue
    val setpoint = (Pool_HP_Setpoint.state as Number).doubleValue

    if (price < AWATTAR_CHEAP_LIMIT_CT.doubleValue && current < setpoint - 0.5 && Pool_HP_OnOff.state != ON) {
        logInfo("PoolModbus", "Cheap power (" + price + " ct) — heat pump ON")
        Pool_HP_OnOff.sendCommand(ON)
    } else if (price > AWATTAR_PRICY_LIMIT_CT.doubleValue && Pool_HP_OnOff.state == ON) {
        logInfo("PoolModbus", "Pricy power (" + price + " ct) — heat pump OFF")
        Pool_HP_OnOff.sendCommand(OFF)
    }
end
```

Replace `Awattar_CurrentPrice` with the actual item name from Step 1.

- [ ] **Step 3: Tune thresholds after a few days of observation, commit**

```bash
git add rules/pool_modbus.rules
git commit -m "add: pool heat pump awattar price-aware scheduling"
```

---

### Task 16 — OH5 widget (optional)

**Skip if** the default semantic-model equipment cards are sufficient.

- [ ] **Step 1: Design widget mockup**

In OH5: Settings → Pages → Custom Widgets → Add Widget. Pattern: a single card with two columns — left "Salzanlage" (pH, ORP, Salinity, Production %), right "Wärmepumpe" (Wasser ein/aus, Setpoint, Status, Power). Bottom row: alarms.

- [ ] **Step 2: Mind the lessons in `feedback_oh5_widgets.md`**

From the user's memory:
- YAML quoting: any expression starting with `=` must be quoted with `'...'`
- Card height: use `f7-card-content-padding` and `style: {height: 100%}` to stretch
- Canvas offset bug: layouts placed inside another widget have a +x offset
- Use `.state` for raw values, `.displayState` for formatted strings

- [ ] **Step 3: Save widget YAML to `pages/widgets/pool-overview.widget.yaml` (managed via UI; no file edit usually needed)**

If using textual config: place under OpenHAB user-data widgets directory and commit to git. Otherwise the widget is stored in OpenHAB's JSON DB and not part of this repo.

- [ ] **Step 4: Final commit (only if any files changed)**

```bash
git add -A
git commit -m "add: oh5 pool overview widget"
```

---

## Self-Review Checklist (run after writing — done)

- [x] Each spec section has a task: hardware (T1-T2), commissioning (T3), binding install (T4), transforms (T5), semantic model (T6), read things (T7), read items (T8), write things (T9), write items (T10), write tests (T11), filter rule (T12), telegram rule (T13), watchdog (T14), awattar (T15), widget (T16)
- [x] No "TBD" or "TODO" — `$REG_*` placeholders are resolved against a commissioning doc that's an explicit task output
- [x] Method/property names consistent: `Pool_HP_OnOff` not `Pool_HP_On_Off`; `setpointPh` (camelCase) consistently in things, `Pool_Salt_Setpoint_pH` consistently in items
- [x] Every Modbus channel name in items matches the data-thing structure: `modbus:data:<bridge>:<poller>:<thing>:<channel-type>`
- [x] Phases are independently committable so a failed phase 4 doesn't block phase 2-3 from being deployed
