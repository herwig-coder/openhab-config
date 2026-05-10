# Pool Modbus Commissioning Log

Living record of the Waveshare 2-channel Modbus gateway commissioning and the
verified register maps for the SugarValley Oxilife salt chlorinator and the
Poolsana InverPower Ultra heat pump.

Plan: [docs/superpowers/plans/2026-05-10-pool-modbus-integration.md](superpowers/plans/2026-05-10-pool-modbus-integration.md)
Spec: [docs/superpowers/specs/2026-05-10-pool-modbus-integration-design.md](superpowers/specs/2026-05-10-pool-modbus-integration-design.md)

---

## 1. Waveshare gateway

Firmware: V1.486 (or later)

| Channel | Device Name | IP        | Port | MAC                | Baud   | Parity | Slave id | Connected device           |
|---------|-------------|-----------|------|--------------------|--------|--------|----------|----------------------------|
| 1       | PoolSalt    | 10.1.0.18 | 502  | 04-EE-E8-13-A3-78  | 19200  | 8N1    | ?        | SugarValley Oxilife        |
| 2       | PoolHP      | 10.1.0.21 | 502  | (record from UI)   | 9600   | 8N1    | ?        | Poolsana InverPower Ultra  |

Common settings on both channels:

- Work Mode: TCP Server
- Subnet Mask: 255.255.0.0
- Gateway: 10.1.0.1
- IP mode: Static
- Protocol: Modbus TCP to RTU
- Enable Multi-host: No
- Reconnect-time: 12 s

pfSense static DHCP mappings: (record once added)

| MAC | IP | Hostname |
|-----|----|----------|
| 04-EE-E8-13-A3-78 | 10.1.0.18 | PoolSalt |
| ?? | 10.1.0.21 | PoolHP |

---

## 2. SugarValley Oxilife — verified registers

Source documentation: (link/path to official Oxilife / NeoPool Modbus map)

`FC` = function code (3 = read holding, 4 = read input, 6 = write single, 16 = write multiple).
`Scale`: applied to the raw integer to obtain engineering units (e.g. `/100` means raw 712 → 7.12).
`RW`: `R` = read-only, `RW` = read + write.

| Item                          | FC | Addr | Type   | Scale | Unit | RW | Live read | Notes |
|-------------------------------|----|------|--------|-------|------|----|-----------|-------|
| Pool_Salt_pH                  |    |      |        |       | —    | R  |           |       |
| Pool_Salt_ORP                 |    |      |        |       | mV   | R  |           |       |
| Pool_Salt_Salinity            |    |      |        |       | g/L  | R  |           |       |
| Pool_Salt_WaterTemp           |    |      |        |       | °C   | R  |           |       |
| Pool_Salt_Production          |    |      |        |       | %    | R  |           |       |
| Pool_Salt_FlowAlarm           |    |      |        |       | bit  | R  |           |       |
| Pool_Salt_LowSaltAlarm        |    |      |        |       | bit  | R  |           |       |
| Pool_Salt_CellPolarity        |    |      |        |       | —    | R  |           |       |
| Pool_Salt_Setpoint_pH         |    |      |        |       | —    | RW |           |       |
| Pool_Salt_Setpoint_ORP        |    |      |        |       | mV   | RW |           |       |
| Pool_Salt_Setpoint_Production |    |      |        |       | %    | RW |           |       |
| Pool_Salt_Mode                |    |      |        |       | enum | RW |           | enum values: 0=Off 1=Auto 2=Boost 3=Manual (verify) |

`modpoll` template:

```bat
modpoll -m tcp -a 1 -r <addr> -c 1 -t 4:int -1 10.1.0.18 -p 502
```

(`-t 3:int` for input registers, `-t 4:hex` for unknown content.)

---

## 3. Poolsana InverPower Ultra — verified registers

Source: community Modbus map (search "InverPower Ultra Modbus" / "IPS Pro Modbus" — Poolsana rebrands a Phnix/IPS-Pro inverter). All addresses below are unverified until a live `modpoll` read returns a plausible value. Drop any row whose register returns garbage or a Modbus exception.

| Item                  | FC | Addr | Type   | Scale | Unit | RW | Live read | Notes |
|-----------------------|----|------|--------|-------|------|----|-----------|-------|
| Pool_HP_WaterTempIn   |    |      |        |       | °C   | R  |           |       |
| Pool_HP_WaterTempOut  |    |      |        |       | °C   | R  |           |       |
| Pool_HP_AmbientTemp   |    |      |        |       | °C   | R  |           |       |
| Pool_HP_CompressorState|   |      |        |       | bit  | R  |           |       |
| Pool_HP_FanSpeed      |    |      |        |       |      | R  |           |       |
| Pool_HP_Power         |    |      |        |       | W    | R  |           |       |
| Pool_HP_ErrorCode     |    |      |        |       | —    | R  |           | 0 = OK |
| Pool_HP_Status        |    |      |        |       | enum | R  |           |       |
| Pool_HP_Setpoint      |    |      |        |       | °C   | RW |           |       |
| Pool_HP_Mode          |    |      |        |       | enum | RW |           | Heat / Cool / Auto / Off |
| Pool_HP_OnOff         |    |      |        |       | bit  | RW |           |       |

`modpoll` template:

```bat
modpoll -m tcp -a 1 -r <addr> -c 1 -t 4:int -1 10.1.0.21 -p 502
```

---

## 4. Notes / surprises during commissioning

(free-form log — record anything unexpected: registers that returned exception
codes, scaling factors that differed from the doc, slave IDs other than 1,
RS485 termination issues, etc.)
