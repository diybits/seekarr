#!/usr/bin/env python3
"""
Whisparr v2 API functions
Handles all communication with the Whisparr v2 API

Uses the /api/v3/ endpoint path. Connection check verifies application
version starts with '2' to confirm this is a v2 instance.
"""

from typing import List, Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting
import src.primary.utils.arr_client as arr_client

# Get logger for the Whisparr app
whisparr_logger = get_logger("whisparr")

# Shared session (re-exported so callers/tests can keep using whisparr_api.session)
session = arr_client.session

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Any:
    """
    Make a request to the Whisparr API.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
    
    Returns:
        The parsed JSON response or None if the request failed
    """
    # Delegated to the shared *Arr client (src/primary/utils/arr_client.py).
    # Whisparr v2 serves its REST API exclusively under /api/v3/
    # (upstream Whisparr.Api.V3 controllers), so that is the only path we use.
    # get_ssl_verify_setting() is resolved here (app namespace) so existing
    # test monkeypatches on this module keep working.
    return arr_client.arr_request(
        "whisparr", api_url, api_key, api_timeout, endpoint,
        method=method, data=data, params=params,
        api_prefix="v3",
        ssl_verify=get_ssl_verify_setting(),
    )

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    # The queue endpoint is paginated (PagingResource, default page ~10), so
    # len(records) would cap the count. One record is enough to read totalRecords.
    params = {"page": 1, "pageSize": 1}
    response = arr_request(api_url, api_key, api_timeout, "queue", params=params)

    if response and isinstance(response, dict) and "totalRecords" in response:
        queue_size = response.get("totalRecords", 0)
        whisparr_logger.debug(f"Whisparr download queue size: {queue_size}")
        return queue_size

    whisparr_logger.error("Error getting Whisparr download queue size.")
    return -1

def get_items_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects with missing files, or None if the request failed.
    """
    try:
        whisparr_logger.debug("Retrieving missing items...")
        
        # Endpoint parameters - always use v2 format
        endpoint = "wanted/missing?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"
        
        response = arr_request(api_url, api_key, api_timeout, endpoint)
        
        if response is None:
            return None
        
        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        
        # Filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
        
        whisparr_logger.debug(f"Found {len(items)} missing items")
        return items
        
    except Exception as e:
        whisparr_logger.error(f"Error retrieving missing items: {str(e)}")
        return None

def get_cutoff_unmet_items(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """
    Get a list of items that don't meet their quality profile cutoff.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored items.

    Returns:
        A list of item objects that need quality upgrades, or None if the request failed.
    """
    try:
        whisparr_logger.debug("Retrieving cutoff unmet items...")
        
        # Endpoint - always use v2 format
        endpoint = "wanted/cutoff?pageSize=1000&sortKey=airDateUtc&sortDirection=descending"
        
        response = arr_request(api_url, api_key, api_timeout, endpoint)
        
        if response is None:
            return None
        
        # Extract the episodes/items
        items = []
        if isinstance(response, dict) and "records" in response:
            items = response["records"]
        
        whisparr_logger.debug(f"Found {len(items)} cutoff unmet items")
        
        # Just filter monitored if needed
        if monitored_only:
            items = [item for item in items if item.get("monitored", False)]
            whisparr_logger.debug(f"Found {len(items)} cutoff unmet items after filtering monitored")
        
        return items
        
    except Exception as e:
        whisparr_logger.error(f"Error retrieving cutoff unmet items: {str(e)}")
        return None

def item_search(api_url: str, api_key: str, api_timeout: int, item_ids: List[int]) -> int:
    """
    Trigger a search for one or more items.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        item_ids: A list of item IDs to search for
        
    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    try:
        if not item_ids:
            whisparr_logger.warning("No item IDs provided for search.")
            return None

        whisparr_logger.debug(f"Searching for items with IDs: {item_ids}")

        payload = {
            "name": "EpisodeSearch",
            "episodeIds": item_ids
        }

        result = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)

        if result and isinstance(result, dict) and "id" in result:
            command_id = result["id"]
            whisparr_logger.debug(f"Search command triggered with ID {command_id}")
            return command_id

        whisparr_logger.error(f"Failed to trigger search command - no command ID returned. Response: {result}")
        return None

    except Exception as e:
        whisparr_logger.error(f"Error searching for items: {str(e)}")
        return None

def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: int) -> Optional[Dict]:
    """
    Get the status of a specific command.

    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to check

    Returns:
        A dictionary containing the command status, or None if the request failed.
    """
    if not command_id:
        whisparr_logger.error("No command ID provided for status check.")
        return None
        
    # Commands live under /api/v3/command — a single arr_request call is enough.
    result = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
    if isinstance(result, dict):
        whisparr_logger.debug(f"Command {command_id} status: {result.get('status', 'unknown')}")
        return result

    whisparr_logger.error(f"Failed to get command status for ID {command_id}")
    return None

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """
    Check the connection to Whisparr V2 API.
    
    Args:
        api_url: The base URL of the Whisparr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        
    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        whisparr_logger.debug(f"Checking connection to Whisparr V2 instance at {api_url}")

        response = arr_request(api_url, api_key, api_timeout, "system/status")

        if not isinstance(response, dict):
            whisparr_logger.error("Failed to connect to Whisparr V2 API")
            return False

        version = response.get("version", "unknown")

        # Only accept v2.x instances (v1 used a different API layout).
        if isinstance(version, str) and version.startswith('2'):
            whisparr_logger.debug(f"Successfully connected to Whisparr V2 API version: {version}")
            return True

        whisparr_logger.warning(f"Connected to Whisparr but found unexpected version: {version}, expected 2.x")
        return False

    except Exception as e:
        whisparr_logger.error(f"Error checking connection to Whisparr V2 API: {str(e)}")
        return False
