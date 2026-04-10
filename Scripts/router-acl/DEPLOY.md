# Router ACL Controller — Deployment

Controls the WLAN MAC Access Control List on the ZTE A1 WLAN Box via its web UI.
Triggered by the `Router_MacACL` switch item in OpenHAB.

## Server setup

```bash
cd /etc/openhab/Scripts/router-acl
bash setup.sh          # creates venv, installs deps, copies .env.example → .env
nano .env              # set ROUTER_PASSWORD (and paths after probing)
```

## Discover the router's form paths

The default paths in `.env` are educated guesses. Run the probe once to find
the real field names for your firmware:

```bash
source venv/bin/activate
python router_acl.py --probe --verbose
```

The probe logs in, dumps every form field on the WLAN Advanced page to stderr,
and tells you what to put in `.env`.

## Test manually

```bash
source venv/bin/activate
python router_acl.py --status          # read current state
python router_acl.py --state ON        # enable ACL
python router_acl.py --state OFF       # disable ACL
```

Expected output:
```json
{"success": true, "acl_enabled": true, "state": "ON", "requested": "ON", "applied": true}
```

## OpenHAB integration

| File | Purpose |
|---|---|
| `items/router.items` | `Router_MacACL` Switch item |
| `rules/router_acl.rules` | Apply switch → router; sync state on startup |

The rule calls the script with `--state ON/OFF`, reads back the verified
router state from JSON, and `postUpdate`s the item to match reality.
On system start a `--status` call initialises the item.

## .env keys

| Key | Default | Notes |
|---|---|---|
| `ROUTER_URL` | `http://10.0.0.138` | Router IP |
| `ROUTER_USERNAME` | `admin` | |
| `ROUTER_PASSWORD` | *(blank)* | Set after changing router password |
| `ROUTER_LOGIN_PATH` | `/` | Login form POST target |
| `ROUTER_LOGIN_USER_FIELD` | `loginUsername` | Form field name |
| `ROUTER_LOGIN_PASS_FIELD` | `loginPassword` | Form field name |
| `ROUTER_WLAN_ADV_PATH` | `/html/advance/wlanAdvance.html` | Page with ACL toggle |
| `ROUTER_ACL_FIELD` | `MACFilterMode` | HTML field name for ACL mode |
| `ROUTER_ACL_ENABLE_VALUE` | `1` | Value for ACL on |
| `ROUTER_ACL_DISABLE_VALUE` | `0` | Value for ACL off |
| `ROUTER_ACL_SUBMIT_PATH` | *(auto)* | Leave empty to auto-detect from form action |
