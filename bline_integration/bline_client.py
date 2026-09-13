"""Thin HTTP client for Bline's documented /api/v1 REST contract.

Kept free of frappe.throw: callers decide whether a failure should surface as
an error dialog (frappe.throw), a structured return value (Test Connection),
or a stored error message (Bline Call Request), so all failures here are
raised as plain BlineAPIError with a human-readable message.
"""

import frappe
import requests

TIMEOUT = 20


class BlineAPIError(Exception):
    pass


def _base_url(settings):
    base_url = (settings.bline_base_url or "").strip().rstrip("/")
    if not base_url:
        raise BlineAPIError(frappe._("Set the Bline Base URL in Bline Settings first."))
    return base_url


def _token(settings):
    token = settings.get_password("api_token", raise_exception=False)
    if not token:
        raise BlineAPIError(frappe._("Set the Bline API Token in Bline Settings first."))
    return token


def _extract_error(response):
    try:
        payload = response.json()
        message = (payload.get("error") or {}).get("message")
        if message:
            return message
    except ValueError:
        pass
    return frappe._("Bline request failed with HTTP {0}").format(response.status_code)


def request(settings, method, path, **kwargs):
    url = f"{_base_url(settings)}/api/v1{path}"
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {_token(settings)}"
    try:
        response = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise BlineAPIError(frappe._("Could not reach Bline at {0}: {1}").format(url, exc))
    if response.status_code >= 400:
        raise BlineAPIError(_extract_error(response))
    if not response.content:
        return {}
    return response.json()


def get(settings, path, params=None):
    return request(settings, "GET", path, params=params)


def post(settings, path, json_body=None):
    return request(settings, "POST", path, json=json_body)
