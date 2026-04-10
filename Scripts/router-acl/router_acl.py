#!/usr/bin/env python3
"""
Router MAC ACL Controller for ZTE A1 WLAN Box
Reads and sets the WLAN MAC Access Control List (ACL) via the router's XML API.

Usage:
    python router_acl.py --status              Read current ACL state → JSON
    python router_acl.py --state ON            Enable ACL → JSON
    python router_acl.py --state OFF           Disable ACL → JSON
    python router_acl.py --verbose ...         Enable debug logging to stderr

JSON output (stdout):
    { "success": true,  "acl_enabled": true,  "state": "ON"  }
    { "success": false, "error": "..." }

Authentication (ZTE A1 WLAN Box):
    1. GET /  →  extract _sessionTOKEN from page JS
    2. GET token endpoint  →  get password salt
    3. SHA256(password + salt)  →  hashed password
    4. POST / with Username, Password (hashed), action=login, _sessionTOKEN

ACL API:
    GET  /common_page/Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua  →  XML with ACLPolicy
    POST same URL with IF_ACTION=apply&ACLPolicy=Allow|Disabled
"""

import hashlib
import json
import logging
import os
import re
import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Logging — stderr only, stdout stays clean JSON.
# Default level is ERROR so nothing reaches stderr during normal OH operation
# (executeCommandLine combines stdout+stderr, which breaks JSONPATH parsing).
# Pass --verbose to see INFO/DEBUG/WARNING output.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .env loader (no external dependency)
# ---------------------------------------------------------------------------
def load_env(env_path: str) -> None:
    p = Path(env_path)
    if not p.exists():
        return
    with open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env(str(Path(__file__).parent / '.env'))


def _env(key: str, default: str = '') -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------
def _parse_xml(text: str) -> ET.Element:
    """Parse router XML response, raising RuntimeError on failure."""
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise RuntimeError(f'Could not parse XML response: {exc}\nBody: {text!r}') from exc


def _xml_check_ok(root: ET.Element) -> None:
    """Raise RuntimeError if the XML response indicates an error."""
    error_type = root.findtext('IF_ERRORTYPE', '')
    if error_type not in ('SUCC', ''):
        error_str = root.findtext('IF_ERRORSTR', '')
        raise RuntimeError(f'Router API error: {error_type} — {error_str}')


def _parse_instance_params(root: ET.Element, obj_id: str) -> dict:
    """
    Extract ParaName/ParaValue pairs from a ZTE XML instance block.
    The format alternates siblings: <ParaName>K</ParaName><ParaValue>V</ParaValue> …
    """
    instance = root.find(f'.//{obj_id}/Instance')
    if instance is None:
        return {}
    children = list(instance)
    params = {}
    for name_el, val_el in zip(children[0::2], children[1::2]):
        if name_el.tag == 'ParaName' and val_el.tag == 'ParaValue':
            params[name_el.text] = (val_el.text or '')
    return params


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
class RouterACLController:
    """Interacts with the ZTE A1 WLAN Box XML API to read/write the MAC ACL."""

    # Fixed API paths — verified by inspecting the router web UI
    _TOKEN_PATH = '/function_module/login_module/login_page/logintoken_lua.lua'

    def __init__(self) -> None:
        self.base_url = _env('ROUTER_URL', 'http://10.0.0.138').rstrip('/')
        self.username = _env('ROUTER_USERNAME', 'admin')
        self.password = _env('ROUTER_PASSWORD', '')

        # WLAN Advanced page — must be loaded before calling the ACL API.
        # The router tracks page context server-side; direct API calls without
        # this navigation step return SessionTimeout.
        self.wlan_adv_path = _env(
            'ROUTER_WLAN_ADV_PATH',
            '/getpage.lua?pid=123&nextpage=Localnet_WlanAdvanced_t.lp&Menu3Location=0',
        )
        self.acl_api_path = _env(
            'ROUTER_ACL_API_PATH',
            '/common_page/Localnet_WlanAdvanced_MACFilterACLPolicy_lua.lua',
        )
        self.acl_enable_value  = _env('ROUTER_ACL_ENABLE_VALUE',  'Allow')
        self.acl_disable_value = _env('ROUTER_ACL_DISABLE_VALUE', 'Disabled')

        self._session_tmp_token: str = ''   # populated by _open_wlan_page()

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; OpenHAB-RouterACL)',
            'Referer': self.base_url + '/',
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return self.base_url + path

    def _get(self, path: str) -> requests.Response:
        url = self._url(path)
        logger.debug('GET %s', url)
        r = self.session.get(url, timeout=10)
        r.raise_for_status()
        return r

    def _post(self, path: str, data: dict) -> requests.Response:
        url = self._url(path)
        logger.debug('POST %s  data=%s', url, data)
        r = self.session.post(url, data=data, timeout=10)
        r.raise_for_status()
        return r

    @staticmethod
    def _decode_hex_escapes(s: str) -> str:
        """Decode JavaScript \\xNN hex escapes (e.g. '\\x39\\x36' → '96')."""
        return re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)

    def _open_wlan_page(self, raise_on_fail: bool = False) -> None:
        """
        Load the WLAN Advanced page to establish server-side page context.

        The router requires this navigation step before any ACL API call —
        direct API requests without it return SessionTimeout.
        The authenticated page is ~67 KB; unauthenticated is ~69 bytes.

        Also extracts _sessionTmpToken, which the router requires in the POST
        body to apply setting changes (not needed for reads).
        """
        logger.debug('Opening WLAN Advanced page …')
        resp = self.session.get(self._url(self.wlan_adv_path), timeout=10)
        logger.debug('WLAN page: %d bytes', len(resp.content))
        if len(resp.content) < 1000:
            msg = (
                f'WLAN Advanced page returned only {len(resp.content)} bytes — '
                f'login may have failed or ROUTER_WLAN_ADV_PATH is wrong. '
                f'Body: {resp.text!r}'
            )
            if raise_on_fail:
                raise RuntimeError(msg)
            logger.warning(msg)

        # Extract _sessionTmpToken — required in POST body for write operations.
        # It is embedded as a hex-escaped JS string: _sessionTmpToken = "\x39\x36…";
        m = re.search(r'_sessionTmpToken\s*=\s*"([^"]+)"', resp.text)
        if m:
            self._session_tmp_token = self._decode_hex_escapes(m.group(1))
            logger.debug('_sessionTmpToken: %s', self._session_tmp_token)
        else:
            self._session_tmp_token = ''
            logger.warning('_sessionTmpToken not found in WLAN Advanced page')

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """
        Authenticate against the ZTE A1 WLAN Box.

        The router uses a two-step challenge:
          1. A _sessionTOKEN is embedded in the home page JS on every load.
          2. A separate salt is fetched from the token endpoint.
          3. Password is sent as SHA256(password + salt).
        """
        logger.info('Fetching home page for session token …')
        try:
            home = self.session.get(self._url('/'), timeout=10)
            home.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f'Cannot reach router at {self.base_url}: {exc}') from exc

        # Extract the _sessionTOKEN baked into the page JS
        m = re.search(r'addParameter\("_sessionTOKEN",\s*"(\d+)"\)', home.text)
        if not m:
            raise RuntimeError(
                'Could not find _sessionTOKEN in home page JS. '
                'The router firmware may have changed — check the page source.'
            )
        session_token = m.group(1)
        logger.debug('_sessionTOKEN: %s', session_token)

        # Fetch the password salt from the token endpoint
        logger.info('Fetching password salt …')
        salt_resp = self.session.get(self._url(self._TOKEN_PATH), timeout=10)
        salt_resp.raise_for_status()
        salt_root = _parse_xml(salt_resp.text)
        salt = salt_root.text or ''
        logger.debug('Salt: %s', salt)

        # Compute SHA256(password + salt)
        pw_hash = hashlib.sha256(
            (self.password + salt).encode('utf-8')
        ).hexdigest()
        logger.debug('SHA256(password+salt): %s', pw_hash)

        # POST login
        logger.info('Posting login …')
        self._post('/', {
            'Username':      self.username,
            'Password':      pw_hash,
            'action':        'login',
            '_sessionTOKEN': session_token,
        })

        # Verify by loading the WLAN Advanced page.
        # Unauthenticated: ~69-byte JS redirect.  Authenticated: ~67 KB of HTML.
        self._open_wlan_page(raise_on_fail=True)

        logger.info('Login successful.')

    # ------------------------------------------------------------------
    # Read ACL state
    # ------------------------------------------------------------------
    def get_acl_state(self) -> bool:
        """Return True if MAC ACL is currently enabled (ACLPolicy=Allow)."""
        logger.info('Reading ACL state …')
        self._open_wlan_page()
        resp = self._get(self.acl_api_path)
        root = _parse_xml(resp.text)
        _xml_check_ok(root)
        params = _parse_instance_params(root, 'OBJ_WLANACLCFG_ID')
        logger.debug('ACL params: %s', params)
        if 'ACLPolicy' not in params:
            raise RuntimeError(
                f'ACLPolicy not found in API response. Params: {params}. '
                'Update ROUTER_ACL_API_PATH in .env if the path has changed.'
            )
        return params['ACLPolicy'] == self.acl_enable_value

    # ------------------------------------------------------------------
    # Set ACL state
    # ------------------------------------------------------------------
    def set_acl_state(self, enable: bool) -> bool:
        """
        Set the MAC ACL to the desired state.
        Returns the verified state after the change (True = enabled).
        """
        value = self.acl_enable_value if enable else self.acl_disable_value
        logger.info('Setting ACLPolicy to %s …', value)

        self._open_wlan_page()
        post_data = {
            'IF_ACTION':    'apply',
            'ACLPolicy':    value,
        }
        if self._session_tmp_token:
            post_data['_sessionTOKEN'] = self._session_tmp_token
        resp = self._post(self.acl_api_path, post_data)

        root = _parse_xml(resp.text)
        _xml_check_ok(root)
        params = _parse_instance_params(root, 'OBJ_WLANACLCFG_ID')
        logger.debug('ACL params after set: %s', params)

        verified_value = params.get('ACLPolicy', '')
        verified = (verified_value == self.acl_enable_value)

        if verified != enable:
            logger.warning(
                'State after submission (%r) does not match requested (%r).',
                verified_value, value,
            )
        return verified


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description='Control the MAC ACL on a ZTE A1 WLAN Box router.',
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--status',
        action='store_true',
        help='Read and print the current ACL state.',
    )
    group.add_argument(
        '--state',
        choices=['ON', 'OFF'],
        metavar='ON|OFF',
        help='Set ACL to ON (enabled) or OFF (disabled).',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug logging to stderr.',
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ctrl = RouterACLController()

    try:
        ctrl.login()

        if args.status:
            enabled = ctrl.get_acl_state()
            result = {
                'success': True,
                'acl_enabled': enabled,
                'state': 'ON' if enabled else 'OFF',
            }
        else:
            desired = args.state == 'ON'
            verified = ctrl.set_acl_state(desired)
            result = {
                'success': True,
                'acl_enabled': verified,
                'state': 'ON' if verified else 'OFF',
                'requested': args.state,
                'applied': verified == desired,
            }

    except Exception as exc:  # noqa: BLE001
        logger.exception('Unhandled error')
        result = {
            'success': False,
            'error': str(exc),
        }
        print(json.dumps(result), flush=True)
        sys.exit(1)

    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
