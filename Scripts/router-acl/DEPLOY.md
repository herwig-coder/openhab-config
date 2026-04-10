# Router ACL Controller — Deployment

Controls the WLAN MAC Access Control List on the ZTE A1 WLAN Box via its XML API.
Triggered by the `Router_MacACL` switch item in OpenHAB.

## Authentication (how it works)

The ZTE A1 WLAN Box uses a two-step challenge:
1. A `_sessionTOKEN` is embedded in the home page JS on every load.
2. A password salt is fetched from `/function_module/login_module/login_page/logintoken_lua.lua`.
3. The password is sent as `SHA256(password + salt)`.

This is handled automatically by the script.

## Server setup

```bash
cd /etc/openhab/Scripts/router-acl
bash setup.sh          # creates venv, installs deps, copies .env.example → .env
nano .env              # set ROUTER_PASSWORD when you change it from the default
```

The `.env` only needs three lines:
```
ROUTER_URL=http://10.0.0.138
ROUTER_USERNAME=admin
ROUTER_PASSWORD=
```

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
| `ROUTER_PASSWORD` | *(blank)* | Update after changing router password |
| `ROUTER_ACL_API_PATH` | `/common_page/Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua` | Should not need changing |
| `ROUTER_ACL_ENABLE_VALUE` | `Allow` | Should not need changing |
| `ROUTER_ACL_DISABLE_VALUE` | `Disabled` | Should not need changing |
