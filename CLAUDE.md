# OpenHAB Configuration

Smart home monorepo: OpenHAB config files + Python helper scripts.
Protocols: KNX, MQTT, Z-Wave, BLE. Cloud: OpenWeatherMap, Awattar, ÖBB HAFAS, Telegram.

## Directory Structure

```
Config/                         ← git repo root (cloned to /etc/openhab on server)
├── items/                      # OpenHAB item definitions (.items)
├── rules/                      # Automation logic (.rules — Xtend/DSL)
├── things/                     # Device/bridge configuration (.things)
├── persistence/                # influxdb/rrd4j/mapdb/inmemory .persist (file-based since 2026-09-12, no UI config!)
├── Scripts/
│   ├── battery-monitor/        # Python: detect dead batteries via REST API + persistence
│   └── train-tracker/          # Python: ÖBB train delays via HAFAS API → JSON → OpenHAB rules
├── deploy.sh                   # Just runs: git push (server pulls from GitHub)
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

These files already exist correctly on the server and are untouched by `git pull`.

`services/` is gitignored as a whole (`influxdb.cfg` holds credentials, `runtime.cfg` possibly too) — it lives only on the server; restore it from backup, not from git.
Also server-only: `html/` (garbage-calendar ICS served at `/static/`, see `things/MuellCalendar.things`) and `sounds/` (openHAB sample files).

## Integrations Overview

- **KNX** — Building automation (lights, blinds/raffstores, temperatures) via IP tunnel at 10.1.0.16
- **MQTT** — Broker at 10.1.0.10; connects Shelly, Gosund, Weatherstation, Smartmeter, Ulanzi, Matrix
- **Victron** — Cerbo GX at 10.1.0.50, its own MQTT broker (bridge `mqtt:broker:victron`, portal ID `c0619ab6f9ea`). Needs `rules/victron_keepalive.rules` or it stops publishing after 60 s
- **Z-Wave** — Additional sensors/actuators
- **BLE** — Bluetooth Low Energy sensors
- **OpenWeatherMap** — External weather data (API v3, location: 48.317,16.675)
- **Awattar** — Real-time electricity pricing (also drives Ulanzi LED display)
- **Telegram** — Notifications (main bot + washing machine bot)
- **Reolink** — 6 IP cameras via NVR at 10.1.2.1 (channels 0–3, 6, 7)
- **iCalendar** — Garbage collection calendar
- **ÖBB trains** — Real-time delays via HAFAS API (`Scripts/train-tracker/`)

## Python Scripts

### Scripts/train-tracker/
Queries the ÖBB HAFAS API for the next train on a configured route and outputs JSON.
OpenHAB rules (`rules/trains.rules`) call it via `executeCommandLine()` every 15 min (6–10 AM, Mon–Fri).
Server path: `/etc/openhab/Scripts/train-tracker/`

### Scripts/battery-monitor/
Queries OpenHAB REST API + persistence to find battery-powered devices with no activity.
Sends Telegram alerts for dead batteries. Run manually or via cron.
Server path: `/etc/openhab/Scripts/battery-monitor/`

## Deployment Workflow

```
Windows (edit) → git commit → git push → GitHub → server: sudo git pull
```

```bash
# Windows — after committing changes:
./deploy.sh

# Server — apply changes:
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

OpenHAB watches config directories — no restart needed for items/rules/things changes.

Server runs **openHAB 5.1** (no `default` persistence strategies). Outside the repo: `/var/lib/openhab/etc/log4j2.xml`
has an events.log RegexFilter for energy items — changes there need an openHAB restart. See `docs/energy-rollout.md`.

## Server Setup (one-time)

### 1. Create GitHub private repo and push

On GitHub: New repository → private → no README.

```bash
# In Config/ on Windows:
git remote add origin git@github.com:YOUR_USERNAME/openhab-config.git
git push -u origin main
```

### 2. Set up SSH key on the Debian server for GitHub

```bash
ssh herwig@10.1.100.101
ssh-keygen -t ed25519 -C "openhab-server" -f ~/.ssh/github_openhab
cat ~/.ssh/github_openhab.pub
```

Add that public key to GitHub: Settings → SSH and GPG keys → New SSH key.

Test: `ssh -T git@github.com`

### 3. Initialize git in /etc/openhab

The config files already exist there, so we init in-place:

```bash
cd /etc/openhab
sudo git init
sudo git remote add origin git@github.com:YOUR_USERNAME/openhab-config.git
sudo git fetch origin
sudo git checkout -t origin/main
```

If git complains about existing files being overwritten, it means those files differ
from the repo — review them first, then: `sudo git checkout -f main`

The gitignored things files (MQTT_broker.things etc.) are untracked and left untouched.

### 4. Set git to use your SSH key

```bash
sudo git config core.sshCommand "ssh -i /home/herwig/.ssh/github_openhab"
```

### 5. First-time Python venv setup

```bash
cd /etc/openhab/Scripts/train-tracker && bash setup.sh
cd /etc/openhab/Scripts/battery-monitor && bash setup.sh
```

## Rules Notes

- Several rules have `_FIXED` versions (`ulanzimessages_FIXED.rules`, `senddewpointalert_FIXED.rules`) — these are the active versions; the originals without the suffix are kept for reference. See `rules/FIXES_APPLIED.md`.
- Dew point calculation: `rules/dewpoint.rules`
- Bathroom window airing: v2 controller `rules/bathroomAiringController.rules` (shadow mode while `Bathroom_Airing_Shadow` != OFF), motor layer + v1 in `rules/bathroomAiring.rules`. Rollout/validation: `docs/bathroom-airing.md`
- Train tracker: `rules/trains.rules` → `/etc/openhab/Scripts/train-tracker/train_tracker.py`
- Ulanzi LED display: `rules/ulanzimessages_FIXED.rules` + `Scripts/StrompreisUlanzi.py`
