# Ulanzi Rules - Fixes Applied

## Overview
Fixed `ulanzimessages.rules` to add critical NULL/UNDEF guards per OpenHAB skill requirements.

## Critical Issues Fixed

### 1. **ulanzistrompreis** rule (Line 6)
**Problem**: Missing NULL guard on `currentnet.state`
```xtend
// BEFORE - could crash if currentnet is NULL
val netprice = (currentnet.state as QuantityType<Number>).doubleValue

// AFTER - safe with NULL guard
if (currentnet.state == NULL || currentnet.state == UNDEF) {
    logWarn("ulanzistrompreis", "currentnet is NULL/UNDEF, skipping")
    return;
}
val netprice = (currentnet.state as QuantityType<Number>).doubleValue
```

### 2. **ulanzi_airing** rule (Lines 46-54)
**Problem**: Missing NULL guards on dewpoint alert items
```xtend
// AFTER - added NULL guards for all three items
if (Bathroom_DewPoint_Alert.state == NULL || Bathroom_DewPoint_Alert.state == UNDEF) return;
if (ParentsBedroom_DewPoint_Alert.state == NULL || ParentsBedroom_DewPoint_Alert.state == UNDEF) return;
if (ChildrenBedroom_DewPoint.state == NULL || ChildrenBedroom_DewPoint.state == UNDEF) return;
```

### 3. **ulanzi_muellmessage** rule (Lines 79-141)
**Problem**: Multiple NULL/UNDEF issues:
- Line 81: `NextCollectionDate` casting without guard
- Lines 103, 113, 123, 133: Collection items accessed without guards

**Fixed**:
```xtend
// Main collection date guard
if (NextCollectionDate.state == NULL || NextCollectionDate.state == UNDEF) {
    logWarn("ulanzi_muell", "NextCollectionDate is NULL/UNDEF, skipping")
    return;
}

// Each item collection now checks for NULL
if (Item0_Collection.state != NULL && Item0_Collection.state != UNDEF) {
    // safe to use Item0_Collection.state
}

// Combined guards for multiple items
if (Item1_Collection.state != NULL && Item1_Collection.state != UNDEF &&
    NextCollectionDate1.state != NULL && NextCollectionDate1.state != UNDEF &&
    NextCollectionDate.state == NextCollectionDate1.state) {
    // safe to use both items
}
```

### 4. **ulanzi_train message** rule (Lines 191, 203)
**Problem**: Multiple NULL issues with train data
```xtend
// Added guard for traincheck state
if (Ulanzi_01_traincheck.state == NULL || Ulanzi_01_traincheck.state == UNDEF) {
    logWarn("ulanzi_train", "Ulanzi_01_traincheck is NULL/UNDEF")
    return;
}

// Added guards for train data
if (TrainDeparture_Time.state == NULL || TrainDeparture_Time.state == UNDEF) {
    logWarn("ulanzi_train", "TrainDeparture_Time is NULL/UNDEF")
    return;
}
if (TrainStatus_Text.state == NULL || TrainStatus_Text.state == UNDEF) {
    logWarn("ulanzi_train", "TrainStatus_Text is NULL/UNDEF")
    return;
}

// Added guard for delay minutes
if (TrainDelay_Minutes.state == NULL || TrainDelay_Minutes.state == UNDEF) {
    logWarn("ulanzi_train", "TrainDelay_Minutes is NULL/UNDEF")
    return;
}
```

## Benefits

1. **No more crashes**: Rules won't crash if items are NULL/UNDEF
2. **Better logging**: Warning messages show which item caused the skip
3. **Clearer debugging**: Log entries help identify configuration issues
4. **Skill compliant**: Follows OpenHAB skill best practices

## Testing Recommendations

### Before Deployment
1. Check logs for any NULL/UNDEF warnings
2. Verify all items have initial values or are properly configured
3. Test each rule trigger to ensure proper behavior

### After Deployment
Monitor logs for warnings like:
```
WARN [ulanzi_train] - TrainDeparture_Time is NULL/UNDEF
```
These indicate items that need configuration fixes.

## Deployment

```bash
# Backup current rules
cp /etc/openhab/rules/ulanzimessages.rules /etc/openhab/rules/ulanzimessages.rules.backup

# Copy fixed version
cp ulanzimessages_FIXED.rules /etc/openhab/rules/ulanzimessages.rules

# Set permissions
sudo chown openhab:openhab /etc/openhab/rules/ulanzimessages.rules

# Restart OpenHAB
sudo systemctl restart openhab

# Monitor logs
tail -f /var/log/openhab/openhab.log | grep ulanzi
```

## Summary of Changes

| Rule | Lines Changed | Issue Fixed |
|------|---------------|-------------|
| ulanzistrompreis | 6-10 | NULL guard on `currentnet` |
| ulanzi_airing | 46-56 | NULL guards on 3 dewpoint items |
| ulanzi_muellmessage | 79, 103-141 | NULL guards on 6 collection items |
| ulanzi_train message | 188-205 | NULL guards on 4 train items |

**Total**: 13 NULL/UNDEF guards added across 4 rules

---

# Dewpoint Alert Rules - Fixes Applied

## Overview
Fixed `senddewpointalert.rules` to add critical NULL/UNDEF guards before casting item states.

## Critical Issues Fixed

### All Three Rules (dewpointBadAlert, dewpointBedroomAlert, dewpointBedroomTommyAlert)
**Problem**: Missing NULL guards before casting QuantityType items

**Lines affected**:
- Lines 9-12 (Bathroom)
- Lines 53-56 (Parents Bedroom)
- Lines 96-99 (Children Bedroom)

```xtend
// BEFORE - could crash if items are NULL
val temp = (Bathroom_DewPoint.state as QuantityType<Number>).toUnit("°C").doubleValue
val outtemp = (Weatherstation_Temperature_1.state as QuantityType<Number>).toUnit("°C").doubleValue

// AFTER - safe with NULL guards
if (Bathroom_DewPoint.state == NULL || Bathroom_DewPoint.state == UNDEF) {
    logWarn("Bad_Dewpoint_Alert", "Bathroom_DewPoint is NULL/UNDEF, skipping")
    return;
}
if (Weatherstation_Temperature_1.state == NULL || Weatherstation_Temperature_1.state == UNDEF) {
    logWarn("Bad_Dewpoint_Alert", "Weatherstation_Temperature_1 is NULL/UNDEF, skipping")
    return;
}

if (Bathroom_DewPoint.state instanceof QuantityType ) {
    val temp = (Bathroom_DewPoint.state as QuantityType<Number>).toUnit("°C").doubleValue
    val outtemp = (Weatherstation_Temperature_1.state as QuantityType<Number>).toUnit("°C").doubleValue
    // ... rest of logic
}
```

## Benefits

1. **No crashes on sensor failures**: Rules won't crash if temperature sensors become unavailable
2. **Better logging**: Warning messages identify which sensor is NULL
3. **Graceful degradation**: Rules skip execution instead of crashing
4. **Consistent with Ulanzi fixes**: Same NULL guard pattern applied

## Testing Recommendations

### Before Deployment
1. Check logs for any NULL/UNDEF warnings
2. Verify temperature sensors are reporting values
3. Test rule triggers by changing dewpoint values

### After Deployment
Monitor logs for warnings like:
```
WARN [Bad_Dewpoint_Alert] - Bathroom_DewPoint is NULL/UNDEF, skipping
WARN [Bad_Dewpoint_Alert] - Weatherstation_Temperature_1 is NULL/UNDEF, skipping
```
These indicate sensors that need attention.

## Deployment

```bash
# Backup current rules
cp /etc/openhab/rules/senddewpointalert.rules /etc/openhab/rules/senddewpointalert.rules.backup

# Copy fixed version
cp senddewpointalert_FIXED.rules /etc/openhab/rules/senddewpointalert.rules

# Set permissions
sudo chown openhab:openhab /etc/openhab/rules/senddewpointalert.rules

# Restart OpenHAB
sudo systemctl restart openhab

# Monitor logs
tail -f /var/log/openhab/openhab.log | grep Dewpoint_Alert
```

## Summary of Changes

| Rule | Items Protected | Issue Fixed |
|------|----------------|-------------|
| dewpointBadAlert | Bathroom_DewPoint, Weatherstation_Temperature_1 | NULL guards before QuantityType cast |
| dewpointBedroomAlert | ParentsBedroom_DewPoint, Weatherstation_Temperature_1 | NULL guards before QuantityType cast |
| dewpointBedroomTommyAlert | ChildrenBedroom_DewPoint, Weatherstation_Temperature_1 | NULL guards before QuantityType cast |

**Total**: 6 NULL/UNDEF guards added across 3 rules (2 items per rule)
