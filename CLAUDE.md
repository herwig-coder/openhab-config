# OpenHAB Configuration

Smart home monorepo: OpenHAB config files + Python helper scripts.
Protocols: KNX, MQTT, Z-Wave, BLE. Cloud: OpenWeatherMap, Awattar, ÖBB HAFAS, Telegram.

## Directory Structure

```
Config/                         ← git repo root
├── items/                      # OpenHAB item definitions (.items)
├── rules/                      # Automation logic (.rules — Xtend/DSL)
├── things/                     # Device/bridge configuration (.things)
├── scripts/
│   ├── battery-monitor/        # Python: detect dead batteries via REST API + persistence
│   └── train-tracker/          # Python: ÖBB train delays via HAFAS API → JSON → OpenHAB rules
├── deploy.sh                   # SSH/rsync deployment script
├── .env.example                # Template for all secrets — copy to .env
└── .gitignore
```

## Secrets / Credential Management

Four things files contain credentials and are **gitignored**. Their `.template` counterparts (with `YOUR_*` placeholders) are tracked in git:

| Gitignored (real) | Template (in git) |
|---|---|
| `things/MQTT_broker.things` | `things/MQTT_broker.things.template` |
| `things/openweathermap.things` | `things/openweathermap.things.template` |
| `things/telegrambot.things` | `things/telegrambot.things.template` |
| `things/ReolinkCameras.things` | `things/ReolinkCameras.things.template` |

All secrets are documented in `.env.example`. Copy it to `.env` (gitignored) to store real values locally.

## Integrations Overview

- **KNX** — Building automation (lights, blinds/raffstores, temperatures) via IP tunnel at 10.1.0.16
- **MQTT** — Broker at 10.1.0.10; connects Shelly, Gosund, Weatherstation, Smartmeter, Ulanzi, Matrix
- **Z-Wave** — Additional sensors/actuators
- **BLE** — Bluetooth Low Energy sensors
- **OpenWeatherMap** — External weather data (API v3, location: 48.317,16.675)
- **Awattar** — Real-time electricity pricing (also drives Ulanzi LED display via `scripts/` Python)
- **Telegram** — Notifications (main bot + washing machine bot)
- **Reolink** — 6 IP cameras via NVR at 10.1.2.1 (channels 0–3, 6, 7)
- **iCalendar** — Garbage collection calendar
- **ÖBB trains** — Real-time delays via HAFAS API (`scripts/train-tracker/`)

## Python Scripts

### scripts/train-tracker/
Queries the ÖBB HAFAS API for the next train on a configured route and outputs JSON.
OpenHAB rules (`rules/trains.rules`) call it via `executeCommandLine()` every 15 min (6–10 AM, Mon–Fri).
Server deploy path: `/opt/openhab-scripts/train-tracker/`

### scripts/battery-monitor/
Queries OpenHAB REST API + persistence to find battery-powered devices with no activity.
Sends Telegram alerts for dead batteries. Run manually or via cron.
Server deploy path: `/opt/openhab-scripts/battery-monitor/`

## Deploying to the OpenHAB Server

1. Copy `.env.example` → `.env` and fill in `OPENHAB_HOST`, `OPENHAB_SSH_USER`, `OPENHAB_CONFIG_PATH`, `OPENHAB_SCRIPTS_PATH`
2. Set up SSH key auth: `ssh-copy-id $OPENHAB_SSH_USER@$OPENHAB_HOST`
3. Run the deploy script:

```bash
./deploy.sh             # deploy everything (config + scripts)
./deploy.sh items       # deploy only items/
./deploy.sh rules       # deploy only rules/
./deploy.sh things      # deploy only things/
./deploy.sh scripts     # deploy Python scripts to /opt/openhab-scripts/
./deploy.sh rules/trains.rules   # deploy a single file
```

OpenHAB watches config directories — no restart needed for items/rules/things changes.

**First-time scripts setup** (after first `./deploy.sh scripts`):
```bash
ssh $OPENHAB_SSH_USER@$OPENHAB_HOST
cd /opt/openhab-scripts/train-tracker && bash setup.sh
cd /opt/openhab-scripts/battery-monitor && bash setup.sh
```

## Rules Notes

- Several rules have `_FIXED` versions (`ulanzimessages_FIXED.rules`, `senddewpointalert_FIXED.rules`) — these are the active versions; the originals without the suffix are kept for reference. See `rules/FIXES_APPLIED.md`.
- Dew point calculation: `rules/dewpoint.rules`
- Train tracker: `rules/trains.rules` (calls `scripts/train-tracker/train_tracker.py`)
- Ulanzi LED display: `rules/ulanzimessages_FIXED.rules` + `scripts/battery-monitor/../StrompreisUlanzi.py`
