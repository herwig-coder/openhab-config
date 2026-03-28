# Security Guidelines for OpenHAB Rules

**CRITICAL**: OpenHAB runs with significant system access. Follow these guidelines to prevent security vulnerabilities.

---

## Command Injection Prevention

### **NEVER** pass untrusted input to executeCommandLine

```xtend
// ❌ DANGEROUS - Command injection if itemValue is malicious
val String deviceName = MyItem.state.toString
val String result = Exec.executeCommandLine(
    Duration.ofSeconds(10),
    "/usr/bin/python3",
    "/opt/script.py",
    "--device", deviceName  // ⚠️ INJECTION RISK
)
```

**Attack example**: If `MyItem` contains `"device1; rm -rf /"`, the semicolon executes a second command.

### ✅ SAFE: Validate input first

```xtend
val String deviceName = MyItem.state.toString

// Whitelist validation
val allowedDevices = newArrayList("shelly1", "shelly2", "sensor1")
if (!allowedDevices.contains(deviceName)) {
    logError("Security", "Invalid device name rejected: {}", deviceName)
    return;
}

// Now safe to use
val String result = Exec.executeCommandLine(
    Duration.ofSeconds(10),
    "/usr/bin/python3",
    "/opt/script.py",
    "--device", deviceName
)
```

### ✅ SAFE: Use regex validation

```xtend
// Only allow alphanumeric characters
if (!deviceName.matches("^[a-zA-Z0-9_-]+$")) {
    logError("Security", "Device name contains invalid characters: {}", deviceName)
    return;
}
```

### Best Practices for executeCommandLine

1. **Always use absolute paths**: `/usr/bin/python3` not `python3`
2. **Validate ALL arguments** from items, HTTP responses, or user input
3. **Use whitelist validation** when possible (known good values)
4. **Never use shell expansion** (wildcards, pipes, redirects)
5. **Set appropriate timeouts** to prevent hanging processes

---

## Credential Management

### **NEVER** hardcode credentials in rules

```xtend
// ❌ DANGEROUS - Credentials in plaintext
headers.put("Authorization", "Bearer sk-1234567890abcdef")
val apiKey = "secret_api_key_123"
```

**Risks**:
- Visible in UI configuration
- Exposed in backups
- Logged in error messages
- Committed to version control

### ✅ SAFE: Use transformation files

Create `/etc/openhab/transform/secrets.map`:
```
api_key=your_secret_key_here
bearer_token=your_bearer_token_here
```

Set restrictive permissions:
```bash
sudo chmod 600 /etc/openhab/transform/secrets.map
sudo chown openhab:openhab /etc/openhab/transform/secrets.map
```

Use in rules:
```xtend
val String apiKey = transform("MAP", "secrets.map", "api_key")
headers.put("Authorization", "Bearer " + apiKey)
```

### ✅ SAFE: Environment variables (for Python scripts)

`.env` file permissions:
```bash
chmod 600 /opt/script-name/.env
chown openhab:openhab /opt/script-name/.env
```

Never commit `.env` to git:
```bash
echo ".env" >> .gitignore
```

---

## Input Validation & Sanitization

### HTTP Response Parsing

```xtend
// ❌ DANGEROUS - No error handling
val String response = HTTP.sendHttpGetRequest(url, timeout)
val int start = response.indexOf("\"temp\":") + 7
val String raw = response.substring(start, response.indexOf(",", start))
val double temp = Double.parseDouble(raw)  // Can crash
```

### ✅ SAFE: Validate before parsing

```xtend
val String response = HTTP.sendHttpGetRequest(url, timeout)

// NULL check
if (response === null || response.empty) {
    logError("HTTP", "No response from {}", url)
    return;
}

// Bounds checking
val int start = response.indexOf("\"temp\":")
if (start == -1) {
    logError("HTTP", "Key 'temp' not found in response")
    return;
}

val int valueStart = start + 7
val int end = response.indexOf(",", valueStart)
if (end == -1) {
    end = response.indexOf("}", valueStart)
}

if (end == -1 || end <= valueStart) {
    logError("HTTP", "Malformed JSON response")
    return;
}

// Try-catch for parsing
try {
    val String raw = response.substring(valueStart, end).trim
    val double temp = Double.parseDouble(raw)
    postUpdate(TempItem, temp)
} catch (Exception e) {
    logError("HTTP", "Failed to parse temperature: {}", e.message)
}
```

### Telegram Message Sanitization

```xtend
// ❌ RISKY - Untrusted input directly in message
val String deviceName = MQTT_Item.state.toString
telegramAction.sendTelegram("Device " + deviceName + " is offline")
```

**Risk**: If MQTT topic is compromised, attacker controls message content.

### ✅ SAFE: Sanitize untrusted input

```xtend
// Remove special characters that could exploit Telegram markdown
def static String sanitizeForTelegram(String input) {
    return input.replaceAll("[*_`\\[\\]()]", "")
}

val String deviceName = sanitizeForTelegram(MQTT_Item.state.toString)
telegramAction.sendTelegram("Device " + deviceName + " is offline")
```

---

## SSRF Prevention

### URL Validation for HTTP Calls

```xtend
// ❌ DANGEROUS - User-controlled URL
val String url = URL_Item.state.toString
val String response = HTTP.sendHttpGetRequest(url, timeout)
```

**Attack**: User sets `URL_Item` to:
- `http://localhost:8080/rest/` (access internal API)
- `http://192.168.1.1/admin` (scan internal network)
- `http://169.254.169.254/latest/meta-data/` (cloud metadata)

### ✅ SAFE: Validate URL format and destination

```xtend
val String url = URL_Item.state.toString

// Check URL scheme
if (!url.startsWith("http://") && !url.startsWith("https://")) {
    logError("Security", "Invalid URL scheme: {}", url)
    return;
}

// Whitelist allowed hosts
val allowedHosts = newArrayList(
    "api.openweathermap.org",
    "192.168.1.100"  // Known device IP
)

// Extract hostname (simple check)
var String host = url.substring(url.indexOf("://") + 3)
if (host.contains("/")) {
    host = host.substring(0, host.indexOf("/"))
}
if (host.contains(":")) {
    host = host.substring(0, host.indexOf(":"))
}

if (!allowedHosts.contains(host)) {
    logError("Security", "Host not in whitelist: {}", host)
    return;
}

// Now safe to call
val String response = HTTP.sendHttpGetRequest(url, timeout)
```

---

## Rate Limiting & DoS Prevention

### HTTP Call Rate Limiting

```xtend
var Timer rateLimitTimer = null
var int requestCount = 0
val int MAX_REQUESTS_PER_MINUTE = 10

rule "Rate Limited API Call"
when
    Item TriggerItem changed
then
    if (requestCount >= MAX_REQUESTS_PER_MINUTE) {
        logWarn("RateLimit", "API rate limit exceeded, skipping request")
        return;
    }

    requestCount = requestCount + 1
    val String response = HTTP.sendHttpGetRequest(url, timeout)

    // Reset counter after 60 seconds
    if (rateLimitTimer === null) {
        rateLimitTimer = createTimer(now.plusSeconds(60)) [ |
            requestCount = 0
            rateLimitTimer = null
        ]
    }
end
```

### Exponential Backoff on Failures

```xtend
var int failureCount = 0
var int backoffSeconds = 1

rule "API Call with Backoff"
when
    Time cron "0 * * * * ?"  // Every minute
then
    if (failureCount > 5) {
        logError("API", "Too many failures, pausing requests")
        return;
    }

    val String response = HTTP.sendHttpGetRequest(url, timeout)

    if (response === null) {
        failureCount = failureCount + 1
        backoffSeconds = backoffSeconds * 2  // 1, 2, 4, 8, 16 seconds
        logWarn("API", "Request failed, backing off for {} seconds", backoffSeconds)
        return;
    }

    // Success - reset counters
    failureCount = 0
    backoffSeconds = 1
end
```

---

## File System Security

### Script Deployment Permissions

```bash
# ✅ CORRECT - Restrictive permissions
chmod 755 /opt/script-name/                    # Directory: executable, not writable by others
chmod 644 /opt/script-name/script_name.py     # Script: readable by all, writable by owner
chmod 600 /opt/script-name/.env               # Secrets: readable by owner only
chown -R openhab:openhab /opt/script-name/    # Owned by openhab user

# ❌ WRONG - Overly permissive
chmod 777 /opt/script-name/  # Anyone can modify scripts
chmod 644 .env               # Secrets readable by all users
```

### Never Run Scripts as Root

```xtend
// ❌ DANGEROUS
val String result = Exec.executeCommandLine(
    Duration.ofSeconds(10),
    "sudo",  // ⚠️ NEVER USE SUDO IN RULES
    "/opt/script.py"
)

// ✅ CORRECT - Run as openhab user (default)
val String result = Exec.executeCommandLine(
    Duration.ofSeconds(10),
    "/opt/script-name/venv/bin/python",
    "/opt/script-name/script.py"
)
```

**If script needs elevated privileges**:
- Use `sudo` configuration to allow specific command only
- Never allow password-less sudo for arbitrary commands
- Consider using capabilities instead of sudo

---

## Logging & Monitoring

### Safe Logging (Avoid Sensitive Data)

```xtend
// ❌ DANGEROUS - Logs credentials
logInfo("API", "Calling API with key: {}", apiKey)

// ❌ DANGEROUS - Logs full response (may contain PII)
logInfo("API", "Response: {}", response)

// ✅ SAFE - Logs sanitized info
logInfo("API", "Calling API with key: ***REDACTED***")
logInfo("API", "Response received, length: {} bytes", response.length.toString)
```

### Monitor for Security Events

Create monitoring rules:
```xtend
rule "Security: Command Injection Attempt"
when
    Item SuspiciousItem changed
then
    val String value = SuspiciousItem.state.toString

    // Detect shell metacharacters
    if (value.matches(".*[;|&$`\\(\\)].*")) {
        val telegramAction = getActions("telegram", "telegram:telegramBot:SecurityAlerts")
        telegramAction.sendTelegram(
            "⚠️ SECURITY: Possible command injection attempt detected in " +
            SuspiciousItem.name
        )
        logError("Security", "Suspicious input detected: {}", value)
    }
end
```

---

## Security Checklist

### Before deploying any rule:

**Command Execution:**
- [ ] All executeCommandLine arguments validated against whitelist or regex
- [ ] Absolute paths used for executables
- [ ] Timeout set for all commands
- [ ] No shell metacharacters allowed in user input

**HTTP Calls:**
- [ ] Timeout set for all HTTP requests
- [ ] NULL response checked before parsing
- [ ] URL validated if not hardcoded
- [ ] Rate limiting implemented for frequent calls
- [ ] Try-catch around response parsing

**Credentials:**
- [ ] No hardcoded tokens, passwords, or API keys
- [ ] Secrets stored in transform files or environment variables
- [ ] Secret files have 600 permissions
- [ ] Secrets never logged

**Input Validation:**
- [ ] All external input (items, HTTP, MQTT) validated before use
- [ ] Bounds checking for string operations
- [ ] Type validation before casting
- [ ] Sanitization for output to external systems

**File Permissions:**
- [ ] Scripts owned by openhab user
- [ ] Scripts not writable by others (644 or 600)
- [ ] .env files have 600 permissions
- [ ] No sudo usage in rules

**Monitoring:**
- [ ] Failed requests logged
- [ ] Suspicious input patterns detected
- [ ] Security events sent to dedicated Telegram bot
- [ ] Rate limits enforced and logged

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [CWE-918: SSRF](https://cwe.mitre.org/data/definitions/918.html)
- [OpenHAB Security Best Practices](https://www.openhab.org/docs/installation/security.html)
