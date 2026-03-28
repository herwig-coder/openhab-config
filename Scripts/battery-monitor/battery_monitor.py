#!/usr/bin/env python3
"""
OpenHAB Battery Monitor
Detects dead batteries by checking when device items last updated.
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import logging
import os
from pathlib import Path


def load_env_file(env_path: str = '.env'):
    """Load environment variables from .env file without external dependencies."""
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


# Load environment variables from .env file
script_dir = Path(__file__).parent
env_file = script_dir / '.env'
load_env_file(str(env_file))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpenHABBatteryMonitor:
    def __init__(self, base_url: str, api_token: str):
        """
        Initialize the OpenHAB Battery Monitor.

        Args:
            base_url: OpenHAB server URL (e.g., http://localhost:8080)
            api_token: API token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json'
        }

    def get_all_items(self) -> List[Dict]:
        """Fetch all items from OpenHAB."""
        try:
            response = requests.get(
                f'{self.base_url}/rest/items',
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch items: {e}")
            return []

    def get_all_things(self) -> List[Dict]:
        """Fetch all things from OpenHAB."""
        try:
            response = requests.get(
                f'{self.base_url}/rest/things',
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch things: {e}")
            return []

    def get_thing_status(self, thing_uid: str) -> Optional[Dict]:
        """
        Get the status of a specific thing.

        Args:
            thing_uid: The Thing UID

        Returns:
            Thing status info or None
        """
        try:
            response = requests.get(
                f'{self.base_url}/rest/things/{thing_uid}',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                thing = response.json()
                status_info = thing.get('statusInfo', {})
                return {
                    'status': status_info.get('status'),
                    'statusDetail': status_info.get('statusDetail'),
                    'description': status_info.get('description')
                }
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to fetch thing status for {thing_uid}: {e}")
            return None

    def get_persistence_services(self) -> List[str]:
        """
        Get list of available persistence services.

        Returns:
            List of service IDs
        """
        try:
            response = requests.get(
                f'{self.base_url}/rest/persistence',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                services_data = response.json()
                logger.debug(f"Raw persistence services response: {services_data}")

                # Extract service IDs from the response
                # Response is typically a list of objects with 'id' field
                service_ids = []
                if isinstance(services_data, list):
                    for service in services_data:
                        if isinstance(service, dict):
                            service_id = service.get('id')
                            if service_id:
                                service_ids.append(service_id)
                        elif isinstance(service, str):
                            service_ids.append(service)

                return service_ids
            return []
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to fetch persistence services: {e}")
            return []

    def get_item_state_since(self, item_name: str, since: datetime, service_id: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Get item state history since a given time.

        Args:
            item_name: Name of the item
            since: DateTime to check from
            service_id: Persistence service ID (optional, tries multiple if None)

        Returns:
            List of state changes or None if error
        """
        # Try different service IDs if not specified
        service_ids_to_try = [service_id] if service_id else [None, 'rrd4j', 'influxdb', 'jdbc', 'mapdb']

        for sid in service_ids_to_try:
            try:
                # OpenHAB persistence API format - try ISO format with timezone
                since_str = since.strftime('%Y-%m-%dT%H:%M:%S')

                params = {'starttime': since_str}
                if sid:
                    params['serviceId'] = sid

                logger.debug(f"Querying persistence for {item_name} with serviceId={sid}, starttime={since_str}")

                response = requests.get(
                    f'{self.base_url}/rest/persistence/items/{item_name}',
                    headers=self.headers,
                    params=params,
                    timeout=10
                )

                logger.debug(f"Persistence API response status: {response.status_code}")

                if response.status_code == 404:
                    logger.debug(f"No persistence data for {item_name} with service {sid}")
                    continue

                if response.status_code != 200:
                    logger.debug(f"Persistence API returned {response.status_code} for {item_name}")
                    continue

                response.raise_for_status()
                data = response.json()

                logger.debug(f"Persistence response type: {type(data)}, content: {json.dumps(data, indent=2)[:500]}")

                # Handle different response formats
                result = None
                if isinstance(data, dict):
                    result = data.get('data', [])
                elif isinstance(data, list):
                    result = data

                if result and len(result) > 0:
                    logger.debug(f"Found {len(result)} persistence entries for {item_name} with service {sid}")
                    return result
                else:
                    logger.debug(f"Empty persistence data for {item_name} with service {sid}")

            except requests.exceptions.RequestException as e:
                logger.debug(f"Failed to fetch history for {item_name} with service {sid}: {e}")
                continue

        logger.debug(f"No persistence data found for {item_name} with any service")
        return None

    def get_thing_items(self, thing: Dict, all_items: List[Dict]) -> List[Dict]:
        """
        Get all items linked to a Thing's channels.

        Args:
            thing: Thing dictionary from API
            all_items: List of all items

        Returns:
            List of items linked to this thing
        """
        thing_uid = thing.get('UID', '')
        linked_items = []
        item_names = set()

        # Get channel UIDs from the thing
        channels = thing.get('channels', [])
        for channel in channels:
            channel_uid = channel.get('uid', '')
            linked_item_names = channel.get('linkedItems', [])

            for item_name in linked_item_names:
                if item_name not in item_names:
                    item_names.add(item_name)
                    # Find the actual item object
                    for item in all_items:
                        if item.get('name') == item_name:
                            linked_items.append(item)
                            break

        logger.debug(f"Thing {thing_uid} has {len(linked_items)} linked items: {item_names}")
        return linked_items

    def has_battery_item(self, items: List[Dict]) -> Optional[Dict]:
        """
        Check if any of the items is a battery item.

        Args:
            items: List of items

        Returns:
            First battery item found, or None
        """
        for item in items:
            name = item.get('name', '').lower()
            label = item.get('label', '').lower()
            tags = [tag.lower() for tag in item.get('tags', [])]

            if ('battery' in name or
                'batt' in name or
                'battery' in label or
                'batt' in label or
                'battery' in tags or
                'lowbattery' in name):
                return item

        return None

    def has_value_changed(self, item: Dict, hours: int = 24) -> bool:
        """
        Check if an item's value has actually changed within the given time period.
        This helps detect RRD4j interpolation vs real updates.

        Args:
            item: Item dictionary
            hours: Hours to look back (default: 24)

        Returns:
            True if value has changed, False if unchanged
        """
        item_name = item.get('name', 'unknown')

        # Get from state metadata if available
        state = item.get('state')
        if not state or state in ['NULL', 'UNDEF']:
            logger.debug(f"Item {item_name} has no valid state")
            return False

        # Check history from persistence
        since = datetime.now() - timedelta(hours=hours)
        history = self.get_item_state_since(item_name, since)

        if not history or len(history) == 0:
            logger.debug(f"Item {item_name} has no persistence history in last {hours} hours")
            return False

        # Check if all values are the same (indicating no real change)
        states = [entry.get('state') for entry in history if 'state' in entry]

        if not states:
            return False

        # Convert all states to strings for comparison
        states_str = [str(s) for s in states]
        unique_states = set(states_str)

        if len(unique_states) == 1:
            logger.debug(f"Item {item_name} has unchanged value '{states[0]}' over {hours} hours ({len(history)} entries)")
            return False
        else:
            logger.debug(f"Item {item_name} has {len(unique_states)} different values over {hours} hours")
            return True

    def get_last_update_time(self, item: Dict) -> Optional[datetime]:
        """
        Get the last update time for an item.

        Args:
            item: Item dictionary

        Returns:
            Last update datetime or None
        """
        item_name = item.get('name', 'unknown')

        # Get from state metadata if available
        state = item.get('state')
        if not state or state in ['NULL', 'UNDEF']:
            logger.debug(f"Item {item_name} has no valid state")
            return None

        # Check last 48 hours of history from persistence
        since = datetime.now() - timedelta(hours=48)
        history = self.get_item_state_since(item_name, since)

        if history and len(history) > 0:
            logger.debug(f"Item {item_name} has {len(history)} history entries")
            # Get the most recent entry
            latest = max(history, key=lambda x: x.get('time', 0))
            timestamp = latest.get('time')
            if timestamp:
                # Convert from milliseconds
                last_update = datetime.fromtimestamp(timestamp / 1000)
                logger.debug(f"Item {item_name} last update: {last_update}")
                return last_update
        else:
            logger.debug(f"Item {item_name} has no persistence history in last 48 hours")

        return None

    def check_device_activity(
        self,
        thing_uid: str,
        items: List[Dict],
        threshold_hours: int = 24
    ) -> tuple[bool, Optional[datetime], List[str], Optional[str]]:
        """
        Check if a device has had any activity recently.

        Args:
            thing_uid: Thing UID to check
            items: Items belonging to the thing
            threshold_hours: Hours of inactivity to flag as dead

        Returns:
            Tuple of (is_dead, last_activity_time, inactive_items, thing_status)
        """
        # First check: Is the Thing offline or unknown?
        thing_status_info = self.get_thing_status(thing_uid)
        thing_status = None
        status_indicates_dead = False

        if thing_status_info:
            thing_status = thing_status_info.get('status')
            logger.debug(f"Thing {thing_uid} status: {thing_status}")

            # If thing is OFFLINE or UNKNOWN, it's likely a dead battery
            # UNKNOWN means OpenHAB doesn't know the state (device not communicating)
            if thing_status in ['OFFLINE', 'UNKNOWN']:
                logger.info(f"Thing {thing_uid} is {thing_status} - status indicates dead battery")
                status_indicates_dead = True

        # Second check: Look at actual value changes in items
        # Check if ANY item has had a real value change (not just RRD4j storage)
        has_any_activity = False
        latest_activity = None
        inactive_items = []
        battery_at_100 = False

        for item in items:
            item_name = item.get('name', '').lower()

            # Battery items get a longer threshold (2 weeks) since they change slowly
            # Non-battery items get the standard threshold (24 hours)
            is_battery_item = ('battery' in item_name or 'batt' in item_name)

            # Special case: Battery at 100% is considered OK (smoke detectors, etc.)
            if is_battery_item:
                battery_state = str(item.get('state', '')).strip()
                # Check if battery is at 100% (handles "100", "100.0", "100 %", etc.)
                if battery_state and (battery_state.startswith('100') or battery_state == '100'):
                    logger.info(f"Battery item {item['name']} is at 100% - considering device as OK")
                    battery_at_100 = True
                    has_any_activity = True
                    continue

            item_threshold_hours = 336 if is_battery_item else threshold_hours  # 336 = 2 weeks

            # Check if this item's value has actually changed
            has_changed = self.has_value_changed(item, item_threshold_hours)

            if has_changed:
                has_any_activity = True
                # Get the last update time for reporting
                last_update = self.get_last_update_time(item)
                if last_update and (latest_activity is None or last_update > latest_activity):
                    latest_activity = last_update
            else:
                inactive_items.append(item['name'])

        # Device is considered dead if:
        # 1. Thing status is OFFLINE/UNKNOWN AND no value changes detected, OR
        # 2. No value changes detected at all (regardless of status)
        is_dead = status_indicates_dead or not has_any_activity

        if is_dead:
            reason = []
            if status_indicates_dead:
                reason.append(f"status={thing_status}")
            if not has_any_activity:
                reason.append("no value changes")
            logger.info(f"Thing {thing_uid} marked as dead: {', '.join(reason)}")

        return is_dead, latest_activity, inactive_items, thing_status

    def scan_for_dead_batteries(
        self,
        threshold_hours: int = 24
    ) -> List[Dict]:
        """
        Scan all battery-powered devices and find those with dead batteries.

        Args:
            threshold_hours: Hours of inactivity to consider device dead

        Returns:
            List of dictionaries with dead battery information
        """
        logger.info("Fetching items and things from OpenHAB...")

        # Check available persistence services
        persistence_services = self.get_persistence_services()
        if persistence_services:
            logger.info(f"Found persistence services: {', '.join(persistence_services)}")
        else:
            logger.warning("No persistence services found - activity tracking may not work")

        all_items = self.get_all_items()
        all_things = self.get_all_things()

        if not all_items:
            logger.error("No items found or failed to fetch items")
            return []

        logger.info(f"Found {len(all_items)} items and {len(all_things)} things")

        dead_batteries = []

        # Iterate through all Things and check if they have battery items
        for thing in all_things:
            thing_uid = thing.get('UID', '')
            if not thing_uid:
                continue

            # Get items linked to this thing
            thing_items = self.get_thing_items(thing, all_items)

            if not thing_items:
                continue

            # Check if this thing has a battery item
            battery_item = self.has_battery_item(thing_items)

            if not battery_item:
                # No battery item, skip this thing
                continue

            logger.info(f"Checking device: {thing_uid}")

            # Check device activity
            is_dead, last_activity, inactive_items, thing_status = self.check_device_activity(
                thing_uid,
                thing_items,
                threshold_hours
            )

            if is_dead:
                battery_level = battery_item.get('state', 'UNKNOWN')
                thing_label = thing.get('label', thing_uid)
                dead_batteries.append({
                    'thing_uid': thing_uid,
                    'thing_label': thing_label,
                    'battery_item': battery_item['name'],
                    'battery_level': battery_level,
                    'last_activity': last_activity,
                    'inactive_items': inactive_items,
                    'total_items': len(thing_items),
                    'thing_status': thing_status
                })

                status_msg = f" (Status: {thing_status})" if thing_status else ""
                logger.warning(
                    f"Dead battery detected: {thing_uid}{status_msg} "
                    f"(Battery: {battery_level}%, "
                    f"Last activity: {last_activity or 'Never'})"
                )

        logger.info(f"Scan complete. Found {len(dead_batteries)} devices with dead batteries")
        return dead_batteries

    def get_telegram_config(self, telegram_thing_uid: str = "telegram:telegramBot:Telegram_Bot") -> Optional[Dict]:
        """
        Get Telegram bot configuration (token and chat IDs).

        Args:
            telegram_thing_uid: Telegram bot Thing UID

        Returns:
            Dict with 'bot_token' and 'chat_id' or None
        """
        try:
            response = requests.get(
                f'{self.base_url}/rest/things/{telegram_thing_uid}',
                headers=self.headers,
                timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Failed to get Telegram Thing: {response.status_code}")
                return None

            thing = response.json()
            config = thing.get('configuration', {})

            # Get bot token
            bot_token = config.get('botToken') or config.get('token')
            if not bot_token:
                logger.error("No bot token found in Telegram Thing configuration")
                return None

            # Get chat ID
            chat_ids = config.get('chatIds') or config.get('chatId')
            chat_id = None

            if chat_ids:
                # chatIds might be a list or comma-separated string
                if isinstance(chat_ids, list) and len(chat_ids) > 0:
                    chat_id = str(chat_ids[0])
                elif isinstance(chat_ids, str):
                    chat_id = chat_ids.split(',')[0].strip()

            if not chat_id:
                logger.error("No chat ID found in Telegram Thing configuration")
                return None

            logger.info(f"Retrieved Telegram config: chat_id={chat_id}")
            return {'bot_token': bot_token, 'chat_id': chat_id}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Telegram Thing: {e}")
            return None

    def send_telegram_message(self, message: str, telegram_thing_uid: str = "telegram:telegramBot:Telegram_Bot") -> bool:
        """
        Send a message via Telegram bot.
        Uses Telegram Bot API directly with bot configuration from OpenHAB Thing.

        Args:
            message: Message text to send
            telegram_thing_uid: Telegram bot Thing UID

        Returns:
            True if message sent successfully
        """
        # Get Telegram bot configuration from OpenHAB
        config = self.get_telegram_config(telegram_thing_uid)
        if not config:
            logger.error("Could not retrieve Telegram bot configuration")
            return False

        bot_token = config['bot_token']
        chat_id = config['chat_id']

        # Send message via Telegram Bot API
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        try:
            response = requests.post(
                telegram_api_url,
                json={
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'  # Allows basic formatting
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Telegram message sent successfully to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send Telegram message: HTTP {response.status_code}, Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_notification(self, dead_batteries: List[Dict]) -> bool:
        """
        Send notification about dead batteries via Telegram.

        Args:
            dead_batteries: List of dead battery info

        Returns:
            True if notification sent successfully
        """
        if not dead_batteries:
            logger.info("No dead batteries to report")
            return True

        # Create notification message
        message = f"🔋 Dead Battery Alert - {len(dead_batteries)} device(s) need attention:\n\n"

        for device in dead_batteries:
            thing_label = device.get('thing_label', device['thing_uid'])
            battery_level = device['battery_level']
            last_activity = device['last_activity']

            if last_activity:
                hours_ago = (datetime.now() - last_activity).total_seconds() / 3600
                time_str = f"{hours_ago:.1f} hours ago"
            else:
                time_str = "Never"

            message += f"• {thing_label}\n"
            message += f"  Battery Level: {battery_level}%\n"
            message += f"  Last Activity: {time_str}\n\n"

        logger.info(f"Notification message:\n{message}")

        # Send via Telegram
        success = self.send_telegram_message(message)

        if not success:
            logger.warning("Failed to send Telegram notification")

        return success


def main():
    parser = argparse.ArgumentParser(
        description='Monitor OpenHAB battery-powered devices'
    )
    parser.add_argument(
        '--url',
        default=os.getenv('OPENHAB_URL', 'http://localhost:8080'),
        help='OpenHAB server URL (default: from OPENHAB_URL env or http://localhost:8080)'
    )
    parser.add_argument(
        '--token',
        default=os.getenv('OPENHAB_TOKEN'),
        help='OpenHAB API token (default: from OPENHAB_TOKEN env)'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=int(os.getenv('THRESHOLD_HOURS', '24')),
        help='Hours of inactivity to consider device dead (default: from THRESHOLD_HOURS env or 24)'
    )
    parser.add_argument(
        '--notify',
        action='store_true',
        default=os.getenv('ENABLE_NOTIFICATIONS', 'false').lower() == 'true',
        help='Send notification for dead batteries (default: from ENABLE_NOTIFICATIONS env)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate that token is provided
    if not args.token:
        parser.error("OpenHAB API token is required. Provide via --token argument or OPENHAB_TOKEN environment variable.")

    # Initialize monitor
    monitor = OpenHABBatteryMonitor(args.url, args.token)

    # Scan for dead batteries
    logger.info(f"Scanning for devices inactive for {args.threshold}+ hours...")
    dead_batteries = monitor.scan_for_dead_batteries(args.threshold)

    # Print results
    print("\n" + "="*60)
    print(f"BATTERY MONITOR REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    if dead_batteries:
        print(f"⚠️  Found {len(dead_batteries)} device(s) with dead batteries:\n")

        for idx, device in enumerate(dead_batteries, 1):
            thing_label = device.get('thing_label', device['thing_uid'])
            print(f"{idx}. {thing_label}")
            print(f"   Thing UID: {device['thing_uid']}")
            print(f"   Battery Item: {device['battery_item']}")
            print(f"   Battery Level: {device['battery_level']}%")

            if device.get('thing_status'):
                print(f"   Thing Status: {device['thing_status']}")

            if device['last_activity']:
                hours_ago = (datetime.now() - device['last_activity']).total_seconds() / 3600
                print(f"   Last Activity: {device['last_activity'].strftime('%Y-%m-%d %H:%M:%S')} ({hours_ago:.1f}h ago)")
            else:
                print(f"   Last Activity: Never recorded")

            print(f"   Inactive Items: {len(device['inactive_items'])}/{device['total_items']}")
            print()

        # Send notification if requested
        if args.notify:
            monitor.send_notification(dead_batteries)
    else:
        print("✅ All battery-powered devices are functioning normally!\n")

    print("="*60)


if __name__ == '__main__':
    main()
