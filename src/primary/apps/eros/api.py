#!/usr/bin/env python3
"""
Whisparr v3 (Eros) API functions
Handles all communication with the Whisparr v3 / Eros API

Uses the /api/v3/ endpoint path. Internal config key is 'eros'.
"""

from typing import List, Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting
import src.primary.utils.arr_client as arr_client

# Get logger for the Eros app
eros_logger = get_logger("eros")

# Shared session (re-exported so callers/tests can keep using eros_api.session)
session = arr_client.session

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
    # Delegated to the shared *Arr client (src/primary/utils/arr_client.py).
    # Eros (Whisparr v3) serves its REST API under /api/v3/
    # (upstream Whisparr.Api.V3 controllers, movie-based wanted endpoints).
    # get_ssl_verify_setting() is resolved here (app namespace) so existing
    # test monkeypatches on this module keep working.
    return arr_client.arr_request(
        "eros", api_url, api_key, api_timeout, endpoint,
        method=method, data=data, params=params,
        api_prefix="v3",
        ssl_verify=get_ssl_verify_setting(),
    )

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


def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Eros (Whisparr v3) is movie-based; the legacy 'scene' search mode has been
    removed because Eros upstream exposes no scene endpoints.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        eros_logger.debug("Retrieving missing items...")

        response = arr_request(api_url, api_key, api_timeout, "movie")

        if response is None:
            return None

        items = []
        if isinstance(response, list):
            items = [item for item in response if not item.get("hasFile", True)]
        elif isinstance(response, dict) and "records" in response:
            items = [item for item in response["records"] if not item.get("hasFile", True)]

        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]

        eros_logger.debug(f"Found {len(items)} missing items")
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


def get_quality_upgrades(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that can be upgraded to better quality.

    Eros (Whisparr v3) is movie-based; the legacy 'scene' search mode has been
    removed because Eros upstream exposes no scene endpoints.

    Args:
        api_url: The base URL of the Eros API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        eros_logger.debug("Retrieving quality upgrade items...")

        response = arr_request(api_url, api_key, api_timeout, "movie")

        if response is None:
            return None

        items = []
        if isinstance(response, list):
            items = [item for item in response if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]
        elif isinstance(response, dict) and "records" in response:
            items = [item for item in response["records"] if item.get("hasFile", False) and item.get("qualityCutoffNotMet", False)]

        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]

        eros_logger.debug(f"Found {len(items)} quality upgrade items")
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

        payload = {"name": "MoviesSearch", "movieIds": item_ids}
        eros_logger.debug(f"Triggering search command: {payload}")
        response = arr_request(api_url, api_key, api_timeout, "command", "POST", payload)
        if response and "id" in response:
            command_id = response["id"]
            eros_logger.debug(f"Search command succeeded with ID {command_id}")
            return command_id

        eros_logger.error(f"Search command failed — no command ID returned. Response: {response}")
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
