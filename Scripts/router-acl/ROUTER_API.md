# ZTE A1 WLAN Box — Web Interface Internals

Reverse-engineered 2026-04-10 by inspecting live HTTP traffic.
Router at `http://10.0.0.138`, firmware: ZTE A1 WLAN Box HW V1.1.1.

---

## Architecture

The router runs a **Lua CGI backend** (`*.lua`, `*.lp` scripts) with a
JavaScript SPA frontend. The 136 KB home page bundle is always served
identically; page data is loaded via AJAX using a session cookie (`SID`).

---

## Authentication

Login is a two-step challenge — the password is never sent in plain text.

### Step 1 — Fetch `_sessionTOKEN` from the home page JS

```
GET /
```

The response embeds a dynamic token directly in the JavaScript source:

```javascript
LoginFormObj.addParameter("_sessionTOKEN", "577582443874214496996430");
```

Extract with regex: `addParameter\("_sessionTOKEN",\s*"(\d+)"\)`

This token changes on every page load.

### Step 2 — Fetch the password salt

```
GET /function_module/login_module/login_page/logintoken_lua.lua
```

Response (plain XML):

```xml
<ajax_response_xml_root>91792772</ajax_response_xml_root>
```

The numeric value is the one-time salt.

### Step 3 — Compute the hashed password

```
hashed_password = SHA256(plain_password + salt)
```

For an empty password: `SHA256("" + "91792772")` → hex digest.

### Step 4 — POST login

```
POST /
Content-Type: application/x-www-form-urlencoded

Username=admin&Password=<sha256_hex>&action=login&_sessionTOKEN=<token_from_step1>
```

A successful login returns **HTTP 302** and redirects to `/` (the
authenticated 186 KB home page). A failed login returns HTTP 200
with the same 136 KB login page. Use the HTTP status code or the
final page size to detect success — not the response body directly.
`requests.Session` follows the redirect automatically.

### Step 5 — Verify login

```
GET /getpage.lua?pid=123&nextpage=Localnet_WlanAdvanced_t.lp&Menu3Location=0
```

- Unauthenticated: 69-byte JS redirect → `window.location.href = "/";`
- Authenticated: ~67 KB of HTML — confirms the session is valid.

**Important:** Loading this page also establishes the server-side page
context required for subsequent ACL API calls (see below).

---

## Session cookie

| Cookie | Notes |
|---|---|
| `SID` | Session token (hex string, ~64 chars). Set by login POST. |
| `_TESTCOOKIESUPPORT` | Always `1`. Set by initial GET to `/`. |

All requests after login must include these cookies (handled automatically
by `requests.Session`).

All requests must include `Referer: http://10.0.0.138/` — the router
checks the Referer header on sub-page requests.

---

## MAC ACL API

### Page context requirement

The ACL API endpoint is an AJAX handler that the router only serves in the
context of a loaded WLAN Advanced page. A direct call without first loading
the parent page returns a `SessionTimeout` HTML error (~1 200 bytes), even
with a valid `SID` cookie. Always GET the WLAN Advanced page first.

```
GET /getpage.lua?pid=123&nextpage=Localnet_WlanAdvanced_t.lp&Menu3Location=0
```

### Read current ACL state

```
GET /common_page/Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua
```

Response (XML):

```xml
<ajax_response_xml_root>
  <IF_ERRORPARAM>SUCC</IF_ERRORPARAM>
  <IF_ERRORTYPE>SUCC</IF_ERRORTYPE>
  <IF_ERRORSTR>SUCC</IF_ERRORSTR>
  <IF_ERRORID>0</IF_ERRORID>
  <OBJ_WLANACLCFG_ID>
    <Instance>
      <ParaName>_InstID</ParaName><ParaValue>DEV.WIFI.AP1</ParaValue>
      <ParaName>Alias</ParaName><ParaValue>SSID1</ParaValue>
      <ParaName>ACLPolicy</ParaName><ParaValue>Disabled</ParaValue>
    </Instance>
  </OBJ_WLANACLCFG_ID>
</ajax_response_xml_root>
```

`ACLPolicy` values: `Disabled` (ACL off) | `Allow` (ACL on — only listed MACs allowed).

Note: `<ParaName>`/`<ParaValue>` are alternating siblings within `<Instance>`,
not parent/child pairs.

### Set ACL state

```
POST /common_page/Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua
Content-Type: application/x-www-form-urlencoded

IF_ACTION=apply&ACLPolicy=Allow
```

or

```
IF_ACTION=apply&ACLPolicy=Disabled
```

The response has the same XML structure as the GET, with the new state
reflected in `ACLPolicy`. Check `IF_ERRORTYPE=SUCC` to confirm success.

The `_sessionTOKEN` parameter **is required** to actually apply a change.
Without it the router returns SUCC but silently ignores the new value.
The token is extracted from the WLAN Advanced page JS after it is loaded:

```javascript
_sessionTmpToken = "\x31\x34\x32\x37…";   // hex-encoded digit string
```

Decode with: `re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), raw)`

---

## XML response format

All API endpoints return XML wrapped in `<ajax_response_xml_root>`.

Error detection:

| Field | Success value | Failure example |
|---|---|---|
| `IF_ERRORTYPE` | `SUCC` | `ERROR` |
| `IF_ERRORSTR` | `SUCC` | `SessionTimeout` |
| `IF_ERRORID` | `0` | non-zero |

`SessionTimeout` typically means either the session cookie is invalid or
the page context was not established (WLAN page not loaded first).

---

## URL structure

Pages are served via `getpage.lua`:

```
/getpage.lua?pid=<section_id>&nextpage=<lua_template>&Menu3Location=<nav_state>
```

Known `pid` values observed:
- `123` — WLAN / Local Network section
- `1005` — Internet / SNTP section

`Menu3Location` appears to be a UI navigation hint; `0` works for direct access.

The `_=<timestamp>` parameter sometimes appended by jQuery is a cache-buster
and can be omitted.
