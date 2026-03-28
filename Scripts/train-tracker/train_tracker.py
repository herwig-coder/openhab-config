#!/usr/bin/env python3
"""
Train Tracker for ÖBB/HAFAS
Fetches train delay information and outputs JSON.
"""

import json
import requests
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import logging
import sys
import os
from pathlib import Path

# Import pyhafas for ÖBB API access
try:
    from pyhafas import HafasClient
    from oebb_profile import OEBBProfile
except ImportError as e:
    print(json.dumps({
        'status': 'ERROR',
        'error': 'Required library not installed. Run: pip install -r requirements.txt',
        'details': str(e)
    }))
    exit(1)


def load_env_file(env_path: str = '.env'):
    """Load environment variables from .env file without external dependencies."""
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


# Load environment variables from .env file
script_dir = Path(__file__).parent
env_file = script_dir / '.env'
load_env_file(str(env_file))

# Configure logging - send to stderr so stdout is clean JSON
# Use WARNING by default (only errors/warnings), INFO/DEBUG only with --verbose
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class TrainTracker:
    def __init__(self):
        """Initialize the Train Tracker with HAFAS client."""
        self.station_cache = {}

        # Initialize HAFAS client with ÖBB profile
        try:
            self.hafas = HafasClient(OEBBProfile())
            logger.debug("Initialized HAFAS client with ÖBB profile")
        except Exception as e:
            logger.error(f"Failed to initialize HAFAS client: {e}")
            raise

    def lookup_station_id(self, station_name: str) -> str:
        """
        Lookup station ID from station name using pyhafas.

        Args:
            station_name: Name of the station (e.g., "Wien Hbf")

        Returns:
            Station ID string

        Raises:
            ValueError: If station not found
        """
        # Check cache first
        if station_name in self.station_cache:
            logger.debug(f"Using cached station ID for '{station_name}': {self.station_cache[station_name]}")
            return self.station_cache[station_name]

        logger.info(f"Looking up station ID for: {station_name}")

        try:
            # Search for locations using pyhafas
            locations = self.hafas.locations(station_name)

            if not locations or len(locations) == 0:
                raise ValueError(f"Station '{station_name}' not found")

            # Take the first result (best match)
            station = locations[0]
            station_id = station.id

            if not station_id:
                raise ValueError(f"No ID found for station '{station_name}'")

            station_label = station.name or station_name
            logger.info(f"Found station: {station_label} (ID: {station_id})")

            # Cache the result
            self.station_cache[station_name] = station_id

            return station_id

        except Exception as e:
            logger.error(f"Failed to lookup station '{station_name}': {e}")
            raise ValueError(f"Cannot lookup station '{station_name}': {e}")

    def get_direct_connections(
        self,
        origin_id: str,
        destination_id: str,
        departure_time: datetime,
        max_changes: int = 0
    ) -> Optional[Dict]:
        """
        Get direct connections using HAFAS mgate API directly.
        Returns the first connection with <= max_changes.

        Args:
            origin_id: Origin station ID
            destination_id: Destination station ID
            departure_time: Departure time
            max_changes: Maximum number of changes allowed (0 = direct only)

        Returns:
            Connection dictionary with journey details or None
        """
        logger.info(f"Searching for connections from {origin_id} to {destination_id} (max {max_changes} changes)")

        # HAFAS mgate API endpoint
        url = "https://fahrplan.oebb.at/bin/mgate.exe"

        # Format datetime for HAFAS API
        date_str = departure_time.strftime("%Y%m%d")
        time_str = departure_time.strftime("%H%M%S")

        # Build HAFAS request
        request_body = {
            "lang": "deu",
            "svcReqL": [{
                "cfg": {"polyEnc": "GPA"},
                "meth": "TripSearch",
                "req": {
                    "depLocL": [{"type": "S", "state": "F", "extId": origin_id}],
                    "arrLocL": [{"type": "S", "state": "F", "extId": destination_id}],
                    "outDate": date_str,
                    "outTime": time_str,
                    "numF": 5,
                    "maxChg": max_changes,
                    "getPasslist": True,
                    "getPolyline": False
                }
            }],
            "client": {"id": "OEBB", "v": "6140000", "type": "AND", "name": "oebbPROD-AND"},
            "ext": "OEBB.1",
            "ver": "1.57",
            "auth": {"type": "AID", "aid": "OWDL4fE4ixNiPBBm"}
        }

        try:
            # Make API request
            response = requests.post(url, json=request_body, timeout=15)
            response.raise_for_status()

            data = response.json()

            # Check for errors
            if "svcResL" not in data or len(data["svcResL"]) == 0:
                logger.error("No service response from HAFAS API")
                return None

            svc_res = data["svcResL"][0]

            if svc_res.get("err") != "OK":
                logger.error(f"HAFAS API error: {svc_res.get('err')}")
                return None

            # Get outbound connections
            if "res" not in svc_res or "outConL" not in svc_res["res"]:
                logger.warning("No connections found")
                return None

            connections = svc_res["res"]["outConL"]

            if not connections:
                logger.warning(f"No connections with max {max_changes} changes found")
                return None

            # Take the first connection
            connection = connections[0]

            # Parse connection details
            num_changes = int(connection.get("chg", 0))
            duration_seconds = int(connection.get("dur", 0))

            logger.info(f"Found connection with {num_changes} change(s), duration: {duration_seconds//60} min")

            # Get first leg for departure info
            if "secL" not in connection or not connection["secL"]:
                logger.error("No sections in connection")
                return None

            first_leg = connection["secL"][0]
            last_leg = connection["secL"][-1]

            # Extract train type/line from first leg
            train_type = "Unknown"
            train_name = None
            if "jny" in first_leg:
                jny = first_leg["jny"]
                # Try to get train name directly
                train_name = jny.get("name", "")

                # Try to extract train type from product information
                if "prodX" in jny and "common" in svc_res["res"] and "prodL" in svc_res["res"]["common"]:
                    prod_idx = jny["prodX"]
                    prod_list = svc_res["res"]["common"]["prodL"]
                    if 0 <= prod_idx < len(prod_list):
                        product = prod_list[prod_idx]
                        # Get product name (e.g., "REX", "S", "RJ")
                        train_type = product.get("name", train_type)
                        if not train_name:
                            train_name = product.get("addName", "") or product.get("nameS", "")

                # If we have a train name but no type, try to extract type from name
                if train_name and train_type == "Unknown":
                    # Extract train type from name (e.g., "REX 1" -> "REX")
                    parts = train_name.split()
                    if parts:
                        train_type = parts[0]

            logger.info(f"Train type: {train_type}, Train name: {train_name}")

            # Parse departure and arrival times
            dep_data = first_leg.get("dep", {})
            arr_data = last_leg.get("arr", {})

            planned_dep = dep_data.get("dTimeS")  # Planned departure timestamp
            actual_dep = dep_data.get("aTimeS")   # Actual departure timestamp
            arrival_time = arr_data.get("aTimeS") or arr_data.get("dTimeS")

            # Helper function to parse HAFAS timestamps (supports both full and time-only formats)
            def parse_hafas_time(time_str: str, base_date: datetime) -> Optional[datetime]:
                if not time_str:
                    return None
                try:
                    # Try full format first (YYYYmmddHHMMSS)
                    if len(time_str) == 14:
                        return datetime.strptime(time_str, "%Y%m%d%H%M%S")
                    # Try time-only format (HHMMSS)
                    elif len(time_str) == 6:
                        time_part = datetime.strptime(time_str, "%H%M%S").time()
                        return datetime.combine(base_date.date(), time_part)
                    else:
                        logger.warning(f"Unknown time format: '{time_str}'")
                        return None
                except ValueError as e:
                    logger.warning(f"Could not parse time '{time_str}': {e}")
                    return None

            # Convert timestamps to datetime
            planned_dt = parse_hafas_time(planned_dep, departure_time) or departure_time
            actual_dt = parse_hafas_time(actual_dep, departure_time) or planned_dt
            arrival_dt = parse_hafas_time(arrival_time, departure_time)

            # Calculate delay in seconds
            delay_seconds = 0
            if planned_dt and actual_dt:
                delay_seconds = int((actual_dt - planned_dt).total_seconds())

            actual_departure = actual_dt if actual_dt else planned_dt

            return {
                'plannedWhen': planned_dt.isoformat(),
                'when': actual_departure.isoformat(),
                'delay': delay_seconds,
                'cancelled': connection.get("isCanc", False),
                'num_changes': num_changes,
                'arrival_time': arrival_dt.isoformat() if arrival_dt else None,
                'duration_minutes': duration_seconds // 60,
                'direction': f"{num_changes} change(s)" if num_changes > 0 else "Direct",
                'train_type': train_type,
                'train_name': train_name
            }

        except requests.RequestException as e:
            logger.error(f"Failed to call HAFAS API: {e}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"Failed to parse HAFAS response: {e}")
            logger.debug(f"Response data: {json.dumps(data, indent=2) if 'data' in locals() else 'N/A'}")
            return None

    def calculate_delay_status(self, departure_data: Optional[Dict]) -> Dict:
        """
        Calculate delay status from departure data.

        Args:
            departure_data: Departure dictionary from API or None

        Returns:
            Dictionary with status, delay_minutes, departure_time
        """
        if not departure_data:
            return {
                'status': 'NOT_FOUND',
                'delay_minutes': 0,
                'planned_time': None,
                'actual_time': None,
                'departure_time': None,
                'arrival_time': None,
                'train_type': None,
                'train_name': None
            }

        # Check if cancelled
        cancelled = departure_data.get('cancelled', False)
        if cancelled:
            logger.warning("Train is cancelled")
            return {
                'status': 'CANCELLED',
                'delay_minutes': 0,
                'planned_time': departure_data.get('plannedWhen'),
                'actual_time': None,
                'departure_time': None,
                'arrival_time': None,
                'train_type': departure_data.get('train_type'),
                'train_name': departure_data.get('train_name')
            }

        # Get planned and actual times
        planned_when_str = departure_data.get('plannedWhen')
        delay_seconds = departure_data.get('delay', 0)

        if not planned_when_str:
            logger.error("No planned departure time in data")
            return {
                'status': 'ERROR',
                'delay_minutes': 0,
                'planned_time': None,
                'actual_time': None,
                'departure_time': None,
                'arrival_time': None,
                'train_type': departure_data.get('train_type'),
                'train_name': departure_data.get('train_name')
            }

        # Parse timestamps
        try:
            planned_dt = datetime.fromisoformat(planned_when_str.replace('Z', '+00:00'))

            # Calculate actual time from delay
            delay_minutes = int(delay_seconds / 60) if delay_seconds else 0
            actual_dt = planned_dt + timedelta(seconds=delay_seconds) if delay_seconds else planned_dt

            # Determine status based on delay
            if delay_minutes <= 2:
                status = 'ON_TIME'
            else:
                status = 'DELAYED'

            # Get arrival time if available
            arrival_time_str = departure_data.get('arrival_time')
            arrival_time_formatted = None
            if arrival_time_str:
                try:
                    arrival_dt = datetime.fromisoformat(arrival_time_str.replace('Z', '+00:00'))
                    arrival_time_formatted = arrival_dt.strftime('%Y-%m-%dT%H:%M:%S')
                except (ValueError, AttributeError):
                    pass

            logger.info(f"Train status: {status} (delay: {delay_minutes} min)")

            return {
                'status': status,
                'delay_minutes': delay_minutes,
                'planned_time': planned_dt.strftime('%H:%M'),
                'actual_time': actual_dt.strftime('%H:%M'),
                'departure_time': actual_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'arrival_time': arrival_time_formatted,
                'train_type': departure_data.get('train_type'),
                'train_name': departure_data.get('train_name')
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse departure times: {e}")
            return {
                'status': 'ERROR',
                'delay_minutes': 0,
                'planned_time': None,
                'actual_time': None,
                'departure_time': None,
                'arrival_time': None,
                'train_type': departure_data.get('train_type') if departure_data else None,
                'train_name': departure_data.get('train_name') if departure_data else None
            }

    def check_train_status(
        self,
        origin_station: str,
        destination_station: str,
        scheduled_time: str,
        max_changes: int = 0
    ) -> Dict:
        """
        Check train status and return information as dictionary.

        Args:
            origin_station: Origin station name
            destination_station: Destination station name
            scheduled_time: Scheduled departure time (HH:MM format)
            max_changes: Maximum number of train changes allowed (0 = direct only)

        Returns:
            Dictionary with train status information
        """
        logger.info(f"Checking train: {origin_station} → {destination_station} at {scheduled_time}")

        try:
            # Parse scheduled time
            try:
                today = datetime.now().date()
                scheduled_dt = datetime.strptime(scheduled_time, '%H:%M')
                scheduled_dt = datetime.combine(today, scheduled_dt.time())
            except ValueError:
                raise ValueError(f"Invalid time format: {scheduled_time}. Use HH:MM (e.g., 08:15)")

            # Lookup station IDs for both origin and destination
            origin_id = self.lookup_station_id(origin_station)
            destination_id = self.lookup_station_id(destination_station)

            # Get connections using HAFAS API
            departure = self.get_direct_connections(
                origin_id,
                destination_id,
                scheduled_dt,
                max_changes=max_changes
            )

            # Calculate delay status
            status_info = self.calculate_delay_status(departure)

            logger.info(f"Train status: {status_info['status']}, Delay: {status_info['delay_minutes']} min")

            return {
                'success': True,
                'origin': origin_station,
                'destination': destination_station,
                'scheduled': scheduled_time,
                **status_info
            }

        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            return {
                'success': False,
                'status': 'ERROR',
                'error': str(e),
                'delay_minutes': 0
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                'success': False,
                'status': 'ERROR',
                'error': str(e),
                'delay_minutes': 0
            }


def main():
    parser = argparse.ArgumentParser(
        description='Fetch train delay information from ÖBB/HAFAS and output JSON'
    )
    parser.add_argument(
        '--origin',
        default=os.getenv('ORIGIN_STATION'),
        help='Origin station name (default: from ORIGIN_STATION env)'
    )
    parser.add_argument(
        '--destination',
        default=os.getenv('DESTINATION_STATION'),
        help='Destination station name (default: from DESTINATION_STATION env)'
    )
    parser.add_argument(
        '--time',
        default=os.getenv('SCHEDULED_TIME'),
        help='Scheduled departure time in HH:MM format (default: from SCHEDULED_TIME env)'
    )
    parser.add_argument(
        '--max-changes',
        type=int,
        default=int(os.getenv('MAX_TRAIN_CHANGES', '0')),
        help='Maximum number of train changes allowed (default: from MAX_TRAIN_CHANGES env or 0 for direct only)'
    )
    parser.add_argument(
        '--test-station',
        help='Test station lookup and exit (provide station name)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (output to stderr)'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Test station lookup mode
    if args.test_station:
        logger.info(f"Testing station lookup for: {args.test_station}")
        tracker = TrainTracker()
        try:
            station_id = tracker.lookup_station_id(args.test_station)
            result = {
                'success': True,
                'station_name': args.test_station,
                'station_id': station_id
            }
            print(json.dumps(result, indent=2))
            return
        except ValueError as e:
            result = {
                'success': False,
                'error': str(e)
            }
            print(json.dumps(result, indent=2))
            sys.exit(1)

    # Validate required parameters
    if not args.origin:
        print(json.dumps({
            'success': False,
            'status': 'ERROR',
            'error': 'Origin station is required (--origin or ORIGIN_STATION env)',
            'delay_minutes': 0
        }))
        sys.exit(1)

    if not args.destination:
        print(json.dumps({
            'success': False,
            'status': 'ERROR',
            'error': 'Destination station is required (--destination or DESTINATION_STATION env)',
            'delay_minutes': 0
        }))
        sys.exit(1)

    if not args.time:
        print(json.dumps({
            'success': False,
            'status': 'ERROR',
            'error': 'Scheduled time is required (--time or SCHEDULED_TIME env)',
            'delay_minutes': 0
        }))
        sys.exit(1)

    # Initialize tracker
    tracker = TrainTracker()

    # Check train status
    result = tracker.check_train_status(
        origin_station=args.origin,
        destination_station=args.destination,
        scheduled_time=args.time,
        max_changes=args.max_changes
    )

    # Output JSON to stdout
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
