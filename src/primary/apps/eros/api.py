#!/usr/bin/env python3
"""
Whisparr v3 (Eros) API functions
Handles all communication with the Whisparr v3 / Eros API

Uses the /api/v3/ endpoint path. Internal config key is 'eros'.
"""

import requests
import json
from typing import List, Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Eros app
eros_logger = get_logger("eros")

# Use a session for better performance
session = requests.Session()

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Any:
    """
    Make a request to the Eros API.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
        params: Optional query parameters for GET requests

    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            eros_logger.error("No URL or API key provided")
            return None

        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            eros_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return None

        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"

        eros_logger.debug(f"Making {method} request to: {full_url}")

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Seekarr/7.0.0 (https://github.com/diybits/seekarr)"
        }

        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            eros_logger.debug("SSL verification disabled by user setting")

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
                eros_logger.error(f"Unsupported HTTP method: {method}")
                return None

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                eros_logger.error(f"Error during {method} request to {endpoint}: {e}, Status Code: {response.status_code}")
                eros_logger.debug(f"Response content: {response.text[:200]}")
                return None

            try:
                if response.text:
                    result = response.json()
                    eros_logger.debug(f"Response from {response.url}: Status {response.status_code}, JSON parsed successfully")
                    return result
                else:
                    eros_logger.debug(f"Response from {response.url}: Status {response.status_code}, Empty response")
                    return {}
            except json.JSONDecodeError:
                eros_logger.error(f"Invalid JSON response from API: {response.text[:200]}")
                return None

        except requests.exceptions.RequestException as e:
            eros_logger.error(f"Request failed: {e}")
            return None
    except Exception as e:
        eros_logger.error(f"Unexpected error during API request: {e}")
        return None


def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "queue")

    if response is None:
        return -1

    if isinstance(response, dict) and "records" in response:
        return len(response["records"])
    elif isinstance(response, list):
        return len(response)
    else:
        return -1


def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, search_mode: str = "movie") -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.
        search_mode: The search mode to use - 'movie' for movie-based or 'scene' for scene-based

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        eros_logger.debug(f"Retrieving missing items using search mode: {search_mode}...")

        if search_mode == "movie":
            response = arr_request(api_url, api_key, api_timeout, "movie")

            if response is None:
                return None

            items = []
            if isinstance(response, list):
                items = [item for item in response if not item.get("hasFile", True)]
            elif isinstance(response, dict) and "records" in response:
                items = [item for item in response["records"] if not item.get("hasFile", True)]

        elif search_mode == "scene":
            response = arr_request(api_url, api_key, api_timeout, "scene/missing",
                                   params={"pageSize": 1000})

            if response is None:
                eros_logger.warning("Scene endpoint not available, falling back to movie mode")
                return get_items_with_missing(api_url, api_key, api_timeout, monitored_only, "movie")

            items = []
            if isinstance(response, dict) and "records" in response:
                items = response["records"]
            elif isinstance(response, list):
                items = response

        else:
            eros_logger.error(f"Invalid search mode: {search_mode}. Must be 'movie' or 'scene'")
            return None

        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]

        eros_logger.debug(f"Found {len(items)} missing items using {search_mode} mode")
        return items

    except Exception as e:
        eros_logger.error(f"Error retrieving missing items: {str(e)}")
        return None


def get_cutoff_unmet_items(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that don't meet their quality profile cutoff.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        eros_logger.debug("Retrieving cutoff unmet items...")

        response = arr_request(api_url, api_key, api_timeout, "wanted/cutoff",
                               params={"pageSize": 1000, "sortKey": "airDateUtc", "sortDirection": "descending"})

        if response is None:
            return None

        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        elif isinstance(response, list):
            items = response

        eros_logger.debug(f"Found {len(items)} cutoff unmet items")

        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            eros_logger.debug(f"Found {len(items)} cutoff unmet items after filtering monitored")

        return items

    except Exception as e:
        eros_logger.error(f"Error retrieving cutoff unmet items: {str(e)}")
        return None


def get_quality_upgrades(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, search_mode: str = "movie") -> List[Dict[str, Any]]:
    """
    Get a list of items that can be upgraded to better quality.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.
        search_mode: The search mode to use - 'movie' for movie-based or 'scene' for scene-based

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        eros_logger.debug(f"Retrieving quality upgrade items using search mode: {search_mode}...")

        if search_mode == "movie":
            response = arr_request(api_url, api_key, api_timeout, "movie")

            if response is None:
                return None

            items = []
            if isinstance(response, list):
                items = [item for item in response if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]
            elif isinstance(response, dict) and "records" in response:
                items = [item for item in response["records"] if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]

        elif search_mode == "scene":
            response = arr_request(api_url, api_key, api_timeout, "scene/cutoff",
                                   params={"pageSize": 1000})

            if response is None:
                eros_logger.warning("Scene cutoff endpoint not available, falling back to movie mode")
                return get_quality_upgrades(api_url, api_key, api_timeout, monitored_only, "movie")

            items = []
            if isinstance(response, dict) and "records" in response:
                items = response["records"]
            elif isinstance(response, list):
                items = response

        else:
            eros_logger.error(f"Invalid search mode: {search_mode}. Must be 'movie' or 'scene'")
            return None

        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]

        eros_logger.debug(f"Found {len(items)} quality upgrade items using {search_mode} mode")
        return items

    except Exception as e:
        eros_logger.error(f"Error retrieving quality upgrade items: {str(e)}")
        return None


def item_search(api_url: str, api_key: str, api_timeout: int, item_ids: List[int]) -> int:
    """
    Trigger a search for one or more items in Eros.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_ids: A list of item IDs to search for

    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    try:
        if not item_ids:
            eros_logger.warning("No item IDs provided for search.")
            return None

        eros_logger.debug(f"Searching for items with IDs: {item_ids}")

        possible_commands = [
            {
                "name": "MoviesSearch",
                "movieIds": item_ids,
                "updateScheduledTask": False,
                "runRefreshAfterSearch": False,
                "sendUpdatesToClient": False
            },
            {
                "name": "MovieSearch",
                "movieIds": item_ids,
                "updateScheduledTask": False,
                "runRefreshAfterSearch": False,
                "sendUpdatesToClient": False
            },
            {
                "name": "MoviesSearch",
                "movieIds": [str(id) for id in item_ids],
                "updateScheduledTask": False,
                "runRefreshAfterSearch": False,
                "sendUpdatesToClient": False
            },
            {
                "name": "MovieSearch",
                "movieIds": [str(id) for id in item_ids],
                "updateScheduledTask": False,
                "runRefreshAfterSearch": False,
                "sendUpdatesToClient": False
            },
            {"name": "MoviesSearch", "movieIds": item_ids},
            {"name": "MovieSearch", "movieIds": item_ids},
            {"name": "MoviesSearch", "movieIds": [str(id) for id in item_ids]},
            {"name": "MovieSearch", "movieIds": [str(id) for id in item_ids]}
        ]

        for i, payload in enumerate(possible_commands):
            eros_logger.debug(f"Trying search command format {i+1}: {payload}")
            response = arr_request(api_url, api_key, api_timeout, "command", "POST", payload)
            if response and "id" in response:
                command_id = response["id"]
                eros_logger.debug(f"Search command format {i+1} succeeded with ID {command_id}")
                return command_id

        eros_logger.error("All search command formats failed - no command ID returned")
        return None

    except Exception as e:
        eros_logger.error(f"Error searching for items: {str(e)}")
        return None


def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict]:
    """
    Get the status of a specific command.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to check

    Returns:
        A dictionary containing the command status, or None if the request failed.
    """
    if not command_id:
        eros_logger.error("No command ID provided for status check.")
        return None

    try:
        result = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
        if result:
            eros_logger.debug(f"Command {command_id} status: {result.get('status', 'unknown')}")
            return result
        else:
            eros_logger.error(f"Failed to get command status for ID {command_id}")
            return None

    except Exception as e:
        eros_logger.error(f"Error getting command status for ID {command_id}: {e}")
        return None


def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """
    Check the connection to Eros API.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        eros_logger.debug(f"Checking connection to Eros instance at {api_url}")

        response = arr_request(api_url, api_key, api_timeout, "system/status")

        if response is not None:
            version = response.get("version", "unknown")
            if version and isinstance(version, str):
                eros_logger.debug(f"Successfully connected to Eros API, reported version: {version}")
                return True
            else:
                eros_logger.warning(f"Connected to server but found unexpected version format: {version}")
                return False
        else:
            eros_logger.error("Failed to connect to Eros API")
            return False

    except Exception as e:
        eros_logger.error(f"Error checking connection to Eros API: {str(e)}")
        return False
