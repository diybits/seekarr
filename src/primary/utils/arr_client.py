#!/usr/bin/env python3
"""
Shared *Arr API HTTP client.

Single implementation of the request plumbing used by every per-app
``arr_request()`` in ``src/primary/apps/{app}/api.py``:

- URL / API-key validation (presence + http(s) scheme)
- per-app logging (logs route to the same app loggers as before)
- SSL verification via the user setting (``get_ssl_verify_setting``)
- connection reuse via one shared ``requests.Session``
- User-Agent built from a single version source (``version.txt`` at the
  project root, written by publish.yml at build time, "dev" fallback)
- consistent JSON parsing and detailed error logging

The per-app modules keep their own ``arr_request()`` wrappers (stable
signatures, app-specific settings fallback where applicable) and delegate
here.
"""

import json
import os
import traceback
from typing import Any, Dict, Optional

import requests

from src.primary.settings_manager import get_ssl_verify_setting
from src.primary.utils.logger import get_logger

# Project root: src/primary/utils/arr_client.py -> up four levels
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Single session shared by all apps (connection pooling across apps)
session = requests.Session()

DEFAULT_VERSION = "dev"
SEEKARR_URL = "https://github.com/diybits/seekarr"


def get_version() -> str:
    """
    Read the running version from version.txt, falling back to "dev".

    version.txt is written by publish.yml at image build time and is the
    same file the UI serves at /version.txt, so the User-Agent always
    matches the running version.
    """
    try:
        with open(os.path.join(_PROJECT_ROOT, "version.txt"), "r", encoding="utf-8") as f:
            return f.read().strip() or DEFAULT_VERSION
    except OSError:
        return DEFAULT_VERSION


def get_user_agent() -> str:
    """Build the User-Agent header from the running version."""
    return f"Seekarr/{get_version()} ({SEEKARR_URL})"


def arr_request(
    app_type: str,
    api_url: str,
    api_key: str,
    api_timeout: int,
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    api_prefix: str = "v3",
    ssl_verify: Optional[bool] = None,
) -> Any:
    """
    Make a request to an *Arr instance API.

    Args:
        app_type: App name used for per-app logging (e.g. "sonarr", "lidarr").
        api_url: The base URL of the *Arr API (must start with http:// or https://).
        api_key: The API key for authentication.
        api_timeout: Timeout for the API request in seconds.
        endpoint: The API endpoint to call (relative, without the /api/<prefix>/ part).
        method: HTTP method (GET, POST, PUT, DELETE).
        data: Optional JSON payload for POST/PUT requests.
        params: Optional query parameters (sent on GET requests).
        api_prefix: API version path segment ("v3" for Sonarr/Radarr/Whisparr v2/Eros,
            "v1" for Lidarr/Readarr).
        ssl_verify: Optional explicit SSL verification override. When None (the
            default) the user setting is read via get_ssl_verify_setting().
            Per-app wrappers pass the resolved setting so their existing
            test/monkeypatch points on the app module keep working.

    Returns:
        The parsed JSON response, an empty dict for an empty 2xx response,
        or None if the request failed.
    """
    app_logger = get_logger(app_type)
    try:
        if not api_url or not api_key:
            app_logger.error("No URL or API key provided")
            return None

        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            app_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return None

        full_url = f"{api_url.rstrip('/')}/api/{api_prefix}/{endpoint.lstrip('/')}"

        app_logger.debug(f"Making {method} request to: {full_url}")

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": get_user_agent(),
        }

        verify_ssl = get_ssl_verify_setting() if ssl_verify is None else ssl_verify

        if not verify_ssl:
            app_logger.debug("SSL verification disabled by user setting")

        try:
            if method.upper() == "GET":
                response = session.get(full_url, headers=headers, params=params, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "POST":
                response = session.post(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "PUT":
                response = session.put(full_url, headers=headers, json=data, timeout=api_timeout, verify=verify_ssl)
            elif method.upper() == "DELETE":
                response = session.delete(full_url, headers=headers, timeout=api_timeout, verify=verify_ssl)
            else:
                app_logger.error(f"Unsupported HTTP method: {method}")
                return None

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                app_logger.error(f"Error during {method} request to {endpoint}: {e}, Status Code: {response.status_code}")
                app_logger.debug(f"Response content: {response.text[:200]}")
                return None

            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError as jde:
                    app_logger.error(f"Error decoding JSON response from {endpoint}: {str(jde)}")
                    app_logger.error(f"Response status code: {response.status_code}")
                    app_logger.error(f"Response content (first 200 chars): {response.text[:200]}")
                    return None

            app_logger.debug(f"Empty response content from {endpoint}, returning empty dict")
            return {}

        except requests.exceptions.RequestException as e:
            error_details = str(e)
            if getattr(e, "response", None) is not None:
                error_details += f", Status Code: {e.response.status_code}"
                if e.response.content:
                    error_details += f", Content: {e.response.text[:200]}"
            app_logger.error(f"Error during {method} request to {endpoint}: {error_details}")
            return None

    except Exception as e:
        app_logger.error(f"CRITICAL ERROR in arr_request: {str(e)}")
        app_logger.error(f"Full traceback: {traceback.format_exc()}")
        return None
