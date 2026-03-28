# Deployment Checklist

## Normal deployment (items / rules / things changes)

```bash
# 1. Commit and push on Windows
git add <files>
git commit -m "description"
git push                          # or: ./deploy.sh

# 2. Pull on server
ssh herwig@10.1.100.101 'cd /etc/openhab && sudo git pull'
```

OpenHAB hot-reloads items/rules/things — no restart needed.

---

## After deployment — check for errors

```bash
ssh herwig@10.1.100.101 'tail -100 /var/log/openhab/openhab.log | grep -E "ERROR|WARN"'
```

Common false positives (safe to ignore on startup):
- `Item 'X' needed for rule 'Y' removed` — transient, old items unloading
- `The method or field X is undefined` — LSP / IDE only, not runtime

Real errors to fix:
- `cannot be resolved to an item or type` — item name mismatch in rules
- `Could not cast NULL` — missing NULL guard in rules
- `Thing ... OFFLINE` — binding/device issue

---

## After renaming items — also update

- [ ] Rules files (`.rules`) — all references to renamed items
- [ ] UI Pages — paste updated YAML in OpenHAB UI (Developer Tools → Code tab)
- [ ] UI Rules (Blockly / Script) — update manually in OpenHAB UI (Settings → Rules)
  - These have auto-generated UIDs like `a3eaace4ca` and are not in git

---

## Gitignored things files (credentials — never in git, live on server only)

| File | Contains |
|------|----------|
| `things/MQTT_broker.things` | MQTT broker credentials |
| `things/openweathermap.things` | OpenWeatherMap API key |
| `things/telegrambot.things` | Telegram bot token |
| `things/ReolinkCameras.things` | Camera IPs / credentials |

These are **never touched by `git pull`** — safe to deploy at any time.

---

## Full OpenHAB restart (only if things won't initialize)

```bash
ssh herwig@10.1.100.101 'sudo systemctl restart openhab'
# wait ~30s then check logs:
ssh herwig@10.1.100.101 'tail -50 /var/log/openhab/openhab.log | grep -E "ERROR|WARN"'
```

---

## Server details

| | |
|---|---|
| Server | `herwig@10.1.100.101` |
| Config path | `/etc/openhab` |
| Log | `/var/log/openhab/openhab.log` |
| REST API | `http://10.1.100.101:8080/rest/` |
