// KNX tunnel recovery
//
// The Siemens N 148/22 (10.1.0.16) occasionally loses tunnel sequence sync
// ("tunneling request with invalid rcv-seq X, expected Y" in openhab.log).
// The tunnel then stays up but every incoming telegram is discarded until the
// 8-bit counter wraps around (~256 telegrams, 11-54 min). The binding does not
// reconnect by itself.
//
// Detection: knx_main pings 1.1.103 every 60 s (pingInterval in
// things/KNX_tunnel.things); the ping times out and knx_main goes
// OFFLINE (COMMUNICATION_ERROR).
// Recovery: disable and re-enable the bridge, which opens a fresh tunnel.
//
// Background: docs/projects/knx-todo.md

const BRIDGE_UID = 'knx:ip:bridge:bridge';
const DEVICE_UID = 'knx:device:bridge:knx_main';
const REENABLE_DELAY_MS = 5 * 1000;
const VERIFY_DELAY_MS = 2 * 60 * 1000;
const COOLDOWN_MS = 10 * 60 * 1000;

const log = console;

function statusDetail(uid) {
  const thing = things.getThing(uid);
  if (thing === null) return 'MISSING';
  return thing.rawThing.getStatusInfo().getStatusDetail().toString();
}

rules.JSRule({
  name: 'KNX tunnel recovery',
  description: 'Re-opens the KNX tunnel when knx_main goes OFFLINE because of a communication error',
  triggers: [triggers.ThingStatusChangeTrigger(DEVICE_UID, 'OFFLINE')],
  execute: () => {
    const bridge = things.getThing(BRIDGE_UID);
    const device = things.getThing(DEVICE_UID);
    if (bridge === null || device === null) {
      log.warn('Bridge or knx_main not found, nothing to do');
      return;
    }

    // Disabling the bridge itself takes knx_main OFFLINE (BRIDGE_OFFLINE) and
    // retriggers this rule; a real gateway outage shows on the bridge. Only a
    // failing ping on a live bridge is the desync case.
    const detail = statusDetail(DEVICE_UID);
    if (detail !== 'COMMUNICATION_ERROR') {
      log.info(`knx_main OFFLINE (${detail}), not a tunnel desync - ignored`);
      return;
    }
    if (bridge.status !== 'ONLINE') {
      log.info(`Bridge is ${bridge.status}, binding handles the reconnect - ignored`);
      return;
    }

    const now = Date.now();
    const last = cache.private.get('lastRecovery') || 0;
    if (now - last < COOLDOWN_MS) {
      log.warn(`knx_main OFFLINE again ${Math.round((now - last) / 1000)} s after last recovery - cooldown, not toggling`);
      return;
    }
    cache.private.put('lastRecovery', now);

    log.warn('knx_main OFFLINE (COMMUNICATION_ERROR) - tunnel probably desynced, disabling bridge');
    bridge.setEnabled(false);

    setTimeout(() => {
      log.info('Re-enabling bridge');
      things.getThing(BRIDGE_UID).setEnabled(true);
    }, REENABLE_DELAY_MS);

    setTimeout(() => {
      const bridgeStatus = things.getThing(BRIDGE_UID).status;
      const deviceStatus = things.getThing(DEVICE_UID).status;
      if (bridgeStatus === 'ONLINE' && deviceStatus === 'ONLINE') {
        log.info('KNX tunnel recovered, bridge and knx_main ONLINE');
      } else {
        log.error(`KNX tunnel NOT recovered: bridge ${bridgeStatus}, knx_main ${deviceStatus}`);
      }
    }, VERIFY_DELAY_MS);
  }
});
