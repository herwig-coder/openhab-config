#!/usr/bin/env python3
"""
Router MAC ACL Controller for ZTE A1 WLAN Box
Reads and sets the WLAN MAC Access Control List (ACL) via the router's web UI.

Usage:
    python router_acl.py --status              Read current ACL state → JSON
    python router_acl.py --state ON            Enable ACL → JSON
    python router_acl.py --state OFF           Disable ACL → JSON
    python router_acl.py --probe               Discover router web interface (setup/debug)
    python router_acl.py --verbose ...         Enable debug logging to stderr

JSON output (stdout):
    { "success": true,  "acl_enabled": true,  "state": "ON"  }
    { "success": false, "error": "..." }

Configuration (Scripts/router-acl/.env):
    ROUTER_URL               e.g. http://10.0.0.138
    ROUTER_USERNAME          e.g. admin
    ROUTER_PASSWORD          e.g. (blank by default)
    ROUTER_LOGIN_PATH        path to POST login form (default: /)
    ROUTER_LOGIN_USER_FIELD  form field name for username (default: loginUsername)
    ROUTER_LOGIN_PASS_FIELD  form field name for password (default: loginPassword)
    ROUTER_WLAN_ADV_PATH     path to WLAN Advanced page (default: see below)
    ROUTER_ACL_FIELD         form field name for MAC filter mode (default: MACFilterMode)
    ROUTER_ACL_ENABLE_VALUE  form value for ACL enabled (default: 1)
    ROUTER_ACL_DISABLE_VALUE form value for ACL disabled (default: 0)
    ROUTER_ACL_SUBMIT_PATH   path to POST the WLAN settings form (default: auto-detect)

Run --probe once after setup to discover the correct paths for your router model,
then update the .env file accordingly.
"""

import json
import logging
import os
import sys
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging — stderr only so stdout stays clean JSON
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
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


script_dir = Path(__file__).parent
load_env(str(script_dir / '.env'))


# ---------------------------------------------------------------------------
# Configuration helper
# ---------------------------------------------------------------------------
def _env(key: str, default: str = '') -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
class RouterACLController:
    """Interacts with the ZTE A1 WLAN Box web UI to read/write the MAC ACL."""

    def __init__(self) -> None:
        self.base_url = _env('ROUTER_URL', 'http://10.0.0.138').rstrip('/')
        self.username = _env('ROUTER_USERNAME', 'admin')
        self.password = _env('ROUTER_PASSWORD', '')

        # Login form
        self.login_path = _env('ROUTER_LOGIN_PATH', '/')
        # ZTE Lua firmware uses UserName / UserPassword + IF_ACTION=login
        self.login_user_field = _env('ROUTER_LOGIN_USER_FIELD', 'UserName')
        self.login_pass_field = _env('ROUTER_LOGIN_PASS_FIELD', 'UserPassword')
        # Extra action field sent with login POST (ZTE Lua requires IF_ACTION=login)
        self.login_action_field = _env('ROUTER_LOGIN_ACTION_FIELD', 'IF_ACTION')
        self.login_action_value = _env('ROUTER_LOGIN_ACTION_VALUE', 'login')

        # WLAN Advanced page
        self.wlan_adv_path = _env(
            'ROUTER_WLAN_ADV_PATH',
            '/html/advance/wlanAdvance.html',
        )

        # ACL form field
        self.acl_field = _env('ROUTER_ACL_FIELD', 'MACFilterMode')
        self.acl_enable_value = _env('ROUTER_ACL_ENABLE_VALUE', '1')
        self.acl_disable_value = _env('ROUTER_ACL_DISABLE_VALUE', '0')

        # Optional explicit submit path; if empty we auto-detect from the form action
        self.acl_submit_path = _env('ROUTER_ACL_SUBMIT_PATH', '')

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; OpenHAB-RouterACL)',
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return self.base_url + path

    def _get(self, path: str, **kwargs) -> requests.Response:
        url = self._url(path)
        logger.debug('GET %s', url)
        r = self.session.get(url, timeout=10, **kwargs)
        r.raise_for_status()
        return r

    def _post(self, path: str, data: dict, **kwargs) -> requests.Response:
        url = self._url(path)
        logger.debug('POST %s  data=%s', url, data)
        r = self.session.post(url, data=data, timeout=10,
                              allow_redirects=True, **kwargs)
        r.raise_for_status()
        return r

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate with the router and establish a session."""
        logger.info('Logging in as %s …', self.username)

        # Fetch the home page first — sets initial cookies and gives us existing
        # form hidden fields (ZTE Lua needs IF_LogOff / IF_LanguageSwitch too)
        try:
            pre = self.session.get(self._url(self.login_path), timeout=10)
            pre.raise_for_status()
            logger.debug('Home page status: %d  size: %d bytes', pre.status_code, len(pre.content))
        except requests.RequestException as exc:
            raise RuntimeError(f'Cannot reach router at {self.base_url}: {exc}') from exc

        # Build payload: start from existing form fields so hidden values are included
        soup = BeautifulSoup(pre.text, 'html.parser')
        login_form = soup.find('form')
        payload = self._extract_form_data(login_form) if login_form else {}

        # Determine submit URL from form action (empty action → post to same path)
        submit_path = self.login_path
        if login_form:
            action = login_form.get('action', '')
            if action.startswith('/'):
                submit_path = action
            elif action.startswith('http'):
                submit_path = action.replace(self.base_url, '')
        logger.debug('Login POST target: %s', submit_path)

        # Overlay credentials and action field
        payload[self.login_user_field] = self.username
        payload[self.login_pass_field] = self.password
        if self.login_action_field:
            payload[self.login_action_field] = self.login_action_value
        logger.debug('Login payload keys: %s', list(payload.keys()))

        resp = self._post(submit_path, payload)
        logger.debug('Login response status: %d  size: %d bytes', resp.status_code, len(resp.content))

        # Some routers respond with JSON on failed login
        if 'application/json' in resp.headers.get('Content-Type', ''):
            data = resp.json()
            if not data.get('success', True):
                raise RuntimeError(f'Login failed (JSON): {data}')

        # ZTE Lua firmware checks the Referer header on all sub-pages.
        # Set it now so every subsequent request in this session looks like it
        # came from within the router UI.
        self.session.headers['Referer'] = self.base_url + '/'

        # Verify by fetching the WLAN Advanced page — unauthenticated (or missing
        # Referer) returns a 69-byte JS redirect; authenticated returns several KB.
        verify = self.session.get(self._url(self.wlan_adv_path), timeout=10)
        logger.debug('Login verify page: %d bytes', len(verify.content))
        if len(verify.content) < 500:
            raise RuntimeError(
                f'Login failed — WLAN Advanced page returned only {len(verify.content)} bytes. '
                f'Body: {verify.text!r}. '
                'Check ROUTER_USERNAME / ROUTER_PASSWORD in .env.'
            )

        logger.info('Login successful.')

    # ------------------------------------------------------------------
    # Read ACL state
    # ------------------------------------------------------------------
    def get_acl_state(self) -> bool:
        """Return True if MAC ACL is currently enabled on the router."""
        logger.info('Reading WLAN Advanced page …')
        resp = self._get(self.wlan_adv_path)
        soup = BeautifulSoup(resp.text, 'html.parser')

        field = self._find_acl_field(soup)
        if field is None:
            raise RuntimeError(
                f'ACL field "{self.acl_field}" not found on {self.wlan_adv_path}. '
                'Run --probe to inspect the page and update ROUTER_ACL_FIELD in .env.'
            )

        current_value = field.get('value', '')
        logger.debug('ACL field current value: %r', current_value)
        return current_value == self.acl_enable_value

    def _find_acl_field(self, soup: BeautifulSoup):
        """Locate the ACL input element by configured field name."""
        # Try exact name match
        elem = soup.find('input', {'name': self.acl_field})
        if elem:
            return elem
        elem = soup.find('select', {'name': self.acl_field})
        if elem:
            # For <select>, return the selected <option>
            selected = elem.find('option', {'selected': True})
            return selected if selected else elem.find('option')
        return None

    # ------------------------------------------------------------------
    # Set ACL state
    # ------------------------------------------------------------------
    def set_acl_state(self, enable: bool) -> bool:
        """
        Set the MAC ACL to the desired state.
        Returns the verified state after the change (True = enabled).
        """
        target_value = self.acl_enable_value if enable else self.acl_disable_value
        logger.info('Setting ACL to %s (value=%s) …', 'ON' if enable else 'OFF', target_value)

        resp = self._get(self.wlan_adv_path)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find the form containing the ACL field
        form = self._find_acl_form(soup)
        if form is None:
            raise RuntimeError(
                f'Could not find a form containing "{self.acl_field}" on {self.wlan_adv_path}. '
                'Run --probe to inspect the page structure.'
            )

        # Build payload: start with all existing form fields
        payload = self._extract_form_data(form)
        if self.acl_field not in payload:
            raise RuntimeError(
                f'Field "{self.acl_field}" not found in form payload. '
                f'Available fields: {list(payload.keys())}. '
                'Update ROUTER_ACL_FIELD in .env.'
            )
        payload[self.acl_field] = target_value
        logger.debug('Submit payload: %s', payload)

        # Determine submit URL
        if self.acl_submit_path:
            submit_path = self.acl_submit_path
        else:
            action = form.get('action', self.wlan_adv_path)
            submit_path = action if action.startswith('/') else self.wlan_adv_path
        logger.debug('Submitting form to: %s', submit_path)

        self._post(submit_path, payload)

        # Verify the new state
        verified = self.get_acl_state()
        if verified != enable:
            logger.warning(
                'State after submission (%s) does not match requested (%s). '
                'The form submit path or field values may be wrong.',
                verified, enable,
            )
        return verified

    def _find_acl_form(self, soup: BeautifulSoup):
        """Return the <form> element that contains the ACL field."""
        for form in soup.find_all('form'):
            if form.find('input', {'name': self.acl_field}):
                return form
            if form.find('select', {'name': self.acl_field}):
                return form
        return None

    @staticmethod
    def _extract_form_data(form) -> dict:
        """Extract all visible form field values into a dict."""
        data = {}
        for inp in form.find_all(['input', 'textarea']):
            name = inp.get('name')
            if not name:
                continue
            itype = inp.get('type', 'text').lower()
            if itype in ('submit', 'button', 'image', 'reset'):
                continue
            if itype == 'checkbox':
                if inp.get('checked'):
                    data[name] = inp.get('value', 'on')
            elif itype == 'radio':
                if inp.get('checked'):
                    data[name] = inp.get('value', 'on')
            else:
                data[name] = inp.get('value', '')
        for sel in form.find_all('select'):
            name = sel.get('name')
            if not name:
                continue
            selected = sel.find('option', {'selected': True})
            if selected:
                data[name] = selected.get('value', '')
            else:
                first = sel.find('option')
                data[name] = first.get('value', '') if first else ''
        return data

    # ------------------------------------------------------------------
    # Probe / discovery
    # ------------------------------------------------------------------
    def probe(self) -> None:
        """
        Explore the router web interface and print findings to stderr.
        Use this to identify the correct paths and form field names for .env.
        """
        print('=== ROUTER ACL PROBE ===', file=sys.stderr)
        print(f'Router: {self.base_url}', file=sys.stderr)

        print('\n[1] Fetching home page …', file=sys.stderr)
        try:
            home = self.session.get(self.base_url + '/', timeout=10)
        except requests.RequestException as exc:
            print(f'  ERROR: {exc}', file=sys.stderr)
            return

        soup = BeautifulSoup(home.text, 'html.parser')

        # Show all forms on the login/home page
        forms = soup.find_all('form')
        print(f'  Forms found on home page: {len(forms)}', file=sys.stderr)
        for i, form in enumerate(forms):
            print(f'  Form {i}: action={form.get("action")}  method={form.get("method")}',
                  file=sys.stderr)
            for inp in form.find_all(['input', 'select']):
                print(f'    <{inp.name} name={inp.get("name")!r} '
                      f'type={inp.get("type", "text")!r} '
                      f'value={inp.get("value", "")!r}>',
                      file=sys.stderr)

        # Collect all links that look WLAN/wireless related
        print('\n[2] WLAN-related links found on home page:', file=sys.stderr)
        wlan_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if any(kw in href.lower() or kw in text.lower()
                   for kw in ('wlan', 'wireless', 'wifi', 'mac', 'filter', 'acl', 'advance')):
                print(f'  {text!r:30s} → {href}', file=sys.stderr)
                wlan_links.append(href)

        if not wlan_links:
            print('  (none found without auth — will try again after login)', file=sys.stderr)

        # Log in before fetching authenticated pages
        print('\n[2b] Logging in …', file=sys.stderr)
        try:
            self.login()
            print('  Login OK', file=sys.stderr)
        except RuntimeError as exc:
            print(f'  Login FAILED: {exc}', file=sys.stderr)
            print(
                '  → Check ROUTER_USERNAME, ROUTER_PASSWORD, '
                'ROUTER_LOGIN_USER_FIELD, ROUTER_LOGIN_PASS_FIELD in .env',
                file=sys.stderr,
            )

        # Always show cookies so we can tell whether a session was established
        cookies = dict(self.session.cookies)
        print(f'  Session cookies after login: {cookies}', file=sys.stderr)
        if not cookies:
            print(
                '  WARNING: no cookies set — the router may use a different login endpoint.',
                file=sys.stderr,
            )
        # Continue so we can still show what the page returns

        # Try the configured WLAN Advanced path
        print(f'\n[3] Fetching WLAN Advanced page: {self.wlan_adv_path}', file=sys.stderr)
        try:
            adv = self.session.get(self._url(self.wlan_adv_path), timeout=10)
            adv.raise_for_status()
            adv_soup = BeautifulSoup(adv.text, 'html.parser')
            forms_adv = adv_soup.find_all('form')
            print(f'  HTTP {adv.status_code}  size: {len(adv.content)} bytes  Forms: {len(forms_adv)}',
                  file=sys.stderr)
            if len(adv.content) < 500:
                print(f'  Raw response body: {adv.text!r}', file=sys.stderr)
            for i, form in enumerate(forms_adv):
                print(f'  Form {i}: action={form.get("action")}  method={form.get("method")}',
                      file=sys.stderr)
                for inp in form.find_all(['input', 'select']):
                    print(f'    <{inp.name} name={inp.get("name")!r} '
                          f'type={inp.get("type", "text")!r} '
                          f'value={inp.get("value", "")!r}>',
                          file=sys.stderr)

            # Search for radio buttons / selects that look like they control filtering
            print('\n  Radio/select fields that may control filtering:', file=sys.stderr)
            for inp in adv_soup.find_all(['input', 'select']):
                name = (inp.get('name') or '').lower()
                if any(kw in name for kw in ('filter', 'mac', 'acl', 'mode', 'enable', 'block')):
                    print(f'    <{inp.name} name={inp.get("name")!r} '
                          f'value={inp.get("value", "")!r} '
                          f'checked={inp.get("checked", False)}>',
                          file=sys.stderr)

        except requests.RequestException as exc:
            print(f'  ERROR: {exc}', file=sys.stderr)
            print(
                '  → Update ROUTER_WLAN_ADV_PATH in .env and run --probe again.',
                file=sys.stderr,
            )

        print('\n=== END PROBE ===', file=sys.stderr)
        print(
            '\nNext steps:\n'
            '  1. Identify the login form fields → set ROUTER_LOGIN_USER_FIELD / ROUTER_LOGIN_PASS_FIELD\n'
            '  2. Log in with --probe --state ON (or run login then probe)\n'
            '  3. Identify the WLAN Advanced page path → set ROUTER_WLAN_ADV_PATH\n'
            '  4. Identify the ACL field name → set ROUTER_ACL_FIELD\n'
            '  5. Identify enable/disable values → set ROUTER_ACL_ENABLE_VALUE / ROUTER_ACL_DISABLE_VALUE\n'
            '  6. Identify the submit form action → set ROUTER_ACL_SUBMIT_PATH',
            file=sys.stderr,
        )


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
    group.add_argument(
        '--probe',
        action='store_true',
        help='Discover router web interface structure (for setup/debugging).',
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

    # ---- Probe mode (no JSON output, just stderr diagnostics) ----
    if args.probe:
        try:
            ctrl.probe()
        except Exception as exc:  # noqa: BLE001
            print(f'Probe error: {exc}', file=sys.stderr)
            sys.exit(1)
        return

    # ---- Status / Set mode (JSON to stdout) ----
    try:
        ctrl.login()

        if args.status:
            enabled = ctrl.get_acl_state()
            result = {
                'success': True,
                'acl_enabled': enabled,
                'state': 'ON' if enabled else 'OFF',
            }
        else:  # --state ON|OFF
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
