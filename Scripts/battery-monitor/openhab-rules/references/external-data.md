# External Data in OpenHAB 4.x Rules DSL

When no binding exists for a service, Rules DSL provides two main approaches.

---

## Method 1: HTTP Actions (preferred for REST APIs)

### Setup
The `HTTP` actions are available without extra imports in OH4, but be explicit:

```xtend
import org.openhab.core.model.script.actions.HTTP
```

### GET Request

```xtend
rule "Fetch data from REST API"
when
    Time cron "0 */5 * * * ?"   // every 5 minutes
then
    val String url     = "http://192.168.1.100/api/status"
    val int    timeout = 5000   // milliseconds — always set a timeout!

    val String response = HTTP.sendHttpGetRequest(url, timeout)

    if (response === null) {
        logError("ExternalData", "HTTP GET failed or timed out: {}", url)
        return;
    }

    logInfo("ExternalData", "Response: {}", response)

    // Parse a simple JSON value — DSL has no JSON library, use string operations
    // For response like: {"temperature": 21.5}
    val int    start = response.indexOf("\"temperature\":") + 14
    val int    end   = response.indexOf(",", start)
    val String raw   = response.substring(start, if (end == -1) response.length - 1 else end).trim
    val double temp  = Double.parseDouble(raw)

    postUpdate(MyTemperatureItem, temp)
    logInfo("ExternalData", "Temperature updated: {}", temp.toString)
end
```

### POST Request with Body

```xtend
val String url     = "http://192.168.1.100/api/control"
val String body    = "{\"action\": \"on\", \"channel\": 1}"
val String ct      = "application/json"
val int    timeout = 5000

val String response = HTTP.sendHttpPostRequest(url, ct, body, timeout)

if (response === null) {
    logError("ExternalData", "POST failed to: {}", url)
    return;
}
logInfo("ExternalData", "POST response: {}", response)
```

### GET with Custom Headers (OH4)

```xtend
import java.util.Map
import java.util.HashMap

val Map<String, String> headers = new HashMap

// ⚠️ SECURITY: Never hardcode credentials - use transform files
// See security-guidelines.md for safe credential storage
val String token = transform("MAP", "secrets.map", "api_token")
headers.put("Authorization", "Bearer " + token)
headers.put("Accept", "application/json")

val String response = HTTP.sendHttpGetRequest(url, headers, timeout)
```

---

## Method 2: executeCommandLine (for shell/CLI tools)

Use when you need to call a local script, curl, or any system command.

**⚠️ SECURITY WARNING**: `executeCommandLine` is a command injection risk if arguments come from items, HTTP responses, or user input. **ALWAYS** validate input first. See [security-guidelines.md](security-guidelines.md) for safe patterns.

### Execute and capture output

```xtend
import org.openhab.core.model.script.actions.Exec

// Run a shell command and capture stdout
val String result = Exec.executeCommandLine(
    Duration.ofSeconds(10),     // timeout
    "/usr/bin/curl",
    "-s",
    "http://192.168.1.100/api/status"
)

if (result === null || result.empty) {
    logError("ExternalData", "curl returned nothing")
    return;
}

logInfo("ExternalData", "curl result: {}", result)
```

### Call a Python script

```xtend
// ⚠️ SECURITY: If --device value comes from item state, validate first!
// See security-guidelines.md for input validation patterns

val String result = Exec.executeCommandLine(
    Duration.ofSeconds(15),
    "/usr/bin/python3",
    "/etc/openhab/scripts/fetch_data.py",
    "--device", "shelly1"  // Only safe if hardcoded
)
postUpdate(MyItem, result.trim)
```

---

## JSON Parsing — No Library Available in DSL

The Rules DSL has no built-in JSON parser. Use these patterns:

### Simple key extraction (flat JSON)

```xtend
// Response: {"power": 45.2, "energy": 1200}
def static double extractJsonDouble(String json, String key) {
    val String search = "\"" + key + "\":"
    val int start = json.indexOf(search)
    if (start == -1) return -1.0

    val int valueStart = start + search.length
    var int end = json.indexOf(",", valueStart)
    if (end == -1) end = json.indexOf("}", valueStart)

    // ✅ SECURITY: Bounds checking
    if (end == -1 || end <= valueStart) return -1.0

    // ✅ SECURITY: Try-catch for parsing
    try {
        return Double.parseDouble(json.substring(valueStart, end).trim)
    } catch (Exception e) {
        logError("JSON", "Failed to parse: {}", e.message)
        return -1.0
    }
}

// Usage
val double power = extractJsonDouble(response, "power")
if (power != -1.0) {
    postUpdate(PowerItem, power)
}
```

### When JSON is complex

If the API returns complex/nested JSON, write a small Python helper script
at `/etc/openhab/scripts/parse_response.py` that does the parsing and prints
a simple value. Then call it via `executeCommandLine`. This is cleaner than
string-hacking nested JSON in DSL.

---

## Error Handling Checklist

Every external call must handle:

- [ ] `null` response (timeout, network error)
- [ ] Empty response
- [ ] Unexpected format (key not found in JSON)
- [ ] Always set a **timeout** — never use default (can block rule engine)
- [ ] Log both success and failure paths

---

## Shelly Direct API Example (no binding needed)

```xtend
rule "Read Shelly Power Meter"
when
    Time cron "0 * * * * ?"   // every minute
then
    val String url      = "http://192.168.1.55/meter/0"
    val int    timeout  = 3000
    val String response = HTTP.sendHttpGetRequest(url, timeout)

    if (response === null) {
        logWarn("Shelly", "No response from Shelly at {}", url)
        return;
    }

    // Shelly response: {"power":12.50,"overpower":false,"is_valid":true,...}
    val int    pStart = response.indexOf("\"power\":") + 8
    val int    pEnd   = response.indexOf(",", pStart)
    val double power  = Double.parseDouble(response.substring(pStart, pEnd).trim)

    postUpdate(Shelly_LivingRoom_Power, power)
    logInfo("Shelly", "Living room power: {} W", power.toString)
end
```
