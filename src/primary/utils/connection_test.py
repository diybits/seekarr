#!/usr/bin/env python3
"""
Shared test-connection utility for all *Arr route blueprints.

All six apps (sonarr, radarr, lidarr, readarr, whisparr, eros) go through
this single function so that socket pre-check, SSL, HTTP error mapping,
and exception handling stay consistent.
"""

import socket
import requests
from urllib.parse import urlparse
from flask import jsonify
from src.primary.settings_manager import get_ssl_verify_setting
from src.primary.utils.logger import get_logger


def test_arr_connection(api_url, api_key, api_timeout, app_name, api_path, *, version_prefix=None):
    """
    Test connectivity to an *Arr API endpoint and return a Flask response tuple.

    api_path:       API path segment, e.g. "api/v3", "api/v1", "api"
    version_prefix: if set, the version field must start with this string (e.g. "2", "3")
    """
    logger = get_logger(app_name.lower().split()[0])

    if not api_url or not api_key:
        return jsonify({"success": False, "message": "API URL and API Key are required"}), 400

    logger.info(f"Testing connection to {app_name} API at {api_url}")

    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        msg = "API URL must start with http:// or https://"
        logger.error(msg)
        return jsonify({"success": False, "message": msg}), 400

    parsed = urlparse(api_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((hostname, port))
        sock.close()
        if result != 0:
            msg = (f"Connection refused - Unable to connect to {hostname}:{port}. "
                   f"Please check if the server is running and the port is correct.")
            logger.error(msg)
            return jsonify({"success": False, "message": msg}), 404
    except socket.gaierror:
        msg = f"DNS resolution failed - Cannot resolve hostname: {hostname}. Please check your URL."
        logger.error(msg)
        return jsonify({"success": False, "message": msg}), 404
    except Exception as e:
        logger.debug(f"Socket test error, continuing with full request: {e}")

    test_url = f"{api_url.rstrip('/')}/{api_path}/system/status"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    verify_ssl = get_ssl_verify_setting()

    if not verify_ssl:
        logger.debug(f"SSL verification disabled for {app_name} connection test")

    try:
        response = requests.get(test_url, headers=headers, timeout=(10, api_timeout), verify=verify_ssl)

        if response.status_code == 401:
            msg = "Authentication failed: Invalid API key"
            logger.error(msg)
            return jsonify({"success": False, "message": msg}), 401
        elif response.status_code == 403:
            msg = "Access forbidden: Check API key permissions"
            logger.error(msg)
            return jsonify({"success": False, "message": msg}), 403
        elif response.status_code == 404:
            msg = f"API endpoint not found: This doesn't appear to be a valid {app_name} server. Check your URL."
            logger.error(msg)
            return jsonify({"success": False, "message": msg}), 404
        elif response.status_code >= 500:
            msg = f"{app_name} server error (HTTP {response.status_code}): The {app_name} server is experiencing issues"
            logger.error(msg)
            return jsonify({"success": False, "message": msg}), response.status_code

        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            msg = f"Invalid JSON response from {app_name} API - This doesn't appear to be a valid {app_name} server"
            logger.error(f"{msg}. Response content: {response.text[:200]}")
            return jsonify({"success": False, "message": msg}), 500

        version = data.get("version", "unknown")

        if version_prefix is not None:
            if not version or not str(version).startswith(version_prefix):
                if version_prefix == "2" and str(version).startswith("3"):
                    msg = f"Connected to Whisparr V3 (version {version}). Use the Eros integration for V3."
                elif version_prefix == "3" and str(version).startswith("2"):
                    msg = f"Incompatible version detected: {version}. This appears to be Whisparr V2, not Eros."
                else:
                    msg = f"Unexpected version {version}. {app_name} requires version {version_prefix}.x."
                logger.error(msg)
                return jsonify({"success": False, "message": msg}), 400

        logger.info(f"Successfully connected to {app_name} API version: {version}")
        return jsonify({
            "success": True,
            "message": f"Successfully connected to {app_name} API",
            "version": version
        })

    except requests.exceptions.ConnectionError as e:
        details = str(e)
        if "Connection refused" in details:
            msg = f"Connection refused - {app_name} is not running on {api_url} or the port is incorrect"
        elif "Name or service not known" in details or "getaddrinfo failed" in details:
            msg = f"DNS resolution failed - Cannot find host '{urlparse(api_url).hostname}'. Check your URL."
        else:
            msg = f"Connection error - Check if {app_name} is running: {details}"
        logger.error(msg)
        return jsonify({"success": False, "message": msg}), 404

    except requests.exceptions.Timeout:
        msg = f"Connection timed out - {app_name} took too long to respond"
        logger.error(msg)
        return jsonify({"success": False, "message": msg}), 504

    except requests.exceptions.RequestException as e:
        msg = f"Connection test failed: {e}"
        logger.error(msg)
        return jsonify({"success": False, "message": msg}), 500
