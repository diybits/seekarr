#!/usr/bin/env python3
"""
Readarr-specific API functions
Handles all communication with the Readarr API
"""

from typing import List, Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings, get_ssl_verify_setting
import src.primary.utils.arr_client as arr_client

# Get app-specific logger
logger = get_logger("readarr")

# Shared session (re-exported so callers/tests can keep using readarr_api.session)
session = arr_client.session

# Default API timeout in seconds - used as fallback only
API_TIMEOUT = 30

def arr_request(api_url: str = None, api_key: str = None, api_timeout: int = None,
                endpoint: str = "", method: str = "GET", data: Dict = None,
                app_type: str = "readarr", params: Dict = None, instance_data: Dict = None) -> Any:
    """
    Make a request to the Readarr API.

    This function handles making API requests to Readarr, with automatic
    instance detection or manual override of API details.

    Args:
        endpoint: The API endpoint to call (relative path)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
        app_type: Application type (default: readarr)
        api_url: Optional URL override (if not using instances)
        api_key: Optional API key override (if not using instances)
        api_timeout: Optional timeout override
        params: Optional query parameters
        instance_data: Optional specific instance data to use

    Returns:
        The parsed JSON response or None if the request failed
    """
    app_logger = get_logger(app_type)

    # Readarr-specific: resolve credentials from (in order) explicit
    # instance_data, explicit args, or stored settings. The HTTP request
    # itself is delegated to the shared *Arr client
    # (src/primary/utils/arr_client.py); get_ssl_verify_setting() is
    # resolved here (app namespace) so existing test monkeypatches on
    # this module keep working.
    if instance_data:
        url = instance_data.get('api_url', '')
        key = instance_data.get('api_key', '')
        timeout = api_timeout or 60
    elif api_url and api_key:
        url = api_url
        key = api_key
        timeout = api_timeout or 60
    else:
        try:
            settings = load_settings(app_type)
            url = settings.get('api_url', '')
            key = settings.get('api_key', '')
            timeout = api_timeout or settings.get('api_timeout', 60)
        except Exception as e:
            app_logger.error(f"Error loading {app_type} settings: {e}")
            return None

    if not url or not key:
        app_logger.error(f"Missing API URL or key for {app_type}")
        return None

    return arr_client.arr_request(
        app_type, url, key, timeout, endpoint,
        method=method, data=data, params=params,
        api_prefix="v1",
        ssl_verify=get_ssl_verify_setting(),
    )


def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Check the connection to Readarr API."""
    if not api_url:
        logger.error("API URL is empty or not set")
        return False
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
        return False
    response = arr_request(api_url, api_key, api_timeout, "system/status")
    if response and isinstance(response, dict):
        logger.debug("Successfully connected to Readarr.")
        return True
    logger.warning(f"Connection check for {api_url} returned unexpected status: {str(response)[:200]}")
    return False


def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """Get the current size of the download queue."""
    try:
        response = arr_request(api_url, api_key, api_timeout, "queue")
        if response and "totalRecords" in response:
            return response["totalRecords"]
        return 0
    except Exception as e:
        logger.error(f"Error getting download queue size: {e}")
        return 0


def get_cutoff_unmet_books(api_url: Optional[str] = None, api_key: Optional[str] = None,
                           api_timeout: Optional[int] = None, monitored_only: bool = True) -> Optional[List[Dict]]:
    """
    Get a list of books that don't meet their quality profile cutoff.
    Accepts optional API credentials (falls back to stored settings).

    Uses Readarr's native GET /api/v1/wanted/cutoff endpoint. Note that
    Readarr was retired and archived upstream (2025-06-27); this targets
    the final API, which is stable.

    Readarr's `monitored` query param is a binary filter (default true:
    book AND author must be monitored), so "include unmonitored too"
    requires one pass per value.

    Args:
        api_url: Optional API URL
        api_key: Optional API key
        api_timeout: Optional API timeout
        monitored_only: If True, only return monitored books.

    Returns:
        A list of book objects (BookResource records) that need quality
        upgrades, or None if the request failed.
    """
    monitored_values = [True] if monitored_only else [True, False]

    page_size = 1000
    unmet_books = []
    for monitored in monitored_values:
        fetched = 0
        page = 1
        while True:
            params = {"page": page, "pageSize": page_size, "monitored": monitored}
            data = arr_request(api_url, api_key, api_timeout, "wanted/cutoff", params=params)
            if data is None:
                logger.error(f"Failed to retrieve cutoff unmet books from Readarr API (monitored={monitored}).")
                return None
            records = data.get("records", [])
            unmet_books.extend(records)
            fetched += len(records)
            total_records = data.get("totalRecords", fetched)
            if not records or fetched >= total_records:
                break
            page += 1

    logger.debug(f"Found {len(unmet_books)} cutoff unmet books (monitored_only={monitored_only}).")
    return unmet_books


def get_wanted_missing_books(api_url: str, api_key: str, api_timeout: int, monitored_only: bool = True) -> List[Dict]:
    """
    Get wanted/missing books from Readarr, handling pagination.

    Args:
        api_url: The base URL of the Readarr API.
        api_key: The API key for authentication.
        api_timeout: Timeout for the API request.
        monitored_only: If True, only return monitored books.

    Returns:
        A list of dictionaries, each representing a missing book, or an empty list on error.
    """
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        logger.error(f"Invalid URL format: {api_url}")
        return []

    # Readarr's `monitored` query param is a binary filter (default true),
    # so "include unmonitored too" requires one pass per value.
    monitored_values = [True] if monitored_only else [True, False]

    all_missing_books = []
    page_size = 100
    for monitored in monitored_values:
        fetched = 0
        page = 1
        while True:
            params = {'page': page, 'pageSize': page_size, 'monitored': monitored}
            data = arr_request(api_url, api_key, api_timeout, "wanted/missing", params=params)

            if not data or 'records' not in data or not data['records']:
                break

            all_missing_books.extend(data['records'])
            fetched += len(data['records'])

            total_records = data.get('totalRecords', 0)
            if fetched >= total_records:
                break

            page += 1

    logger.info(f"Successfully fetched {len(all_missing_books)} missing books from Readarr.")
    return all_missing_books


def get_author_details(api_url: str, api_key: str, author_id: int, api_timeout: int = 120) -> Optional[Dict]:
    """Fetches details for a specific author from the Readarr API."""
    response = arr_request(api_url, api_key, api_timeout, f"author/{author_id}")
    if response is None:
        logger.error(f"Error fetching author details for ID {author_id}.")
    else:
        logger.debug(f"Successfully fetched details for author ID {author_id}.")
    return response


def search_books(api_url: str, api_key: str, book_ids: List[int], api_timeout: int = 120) -> Optional[Dict]:
    """Triggers a search for specific book IDs in Readarr."""
    payload = {'name': 'BookSearch', 'bookIds': book_ids}
    response = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)
    if response:
        command_id = response.get('id')
        logger.info(f"Successfully triggered BookSearch command for book IDs: {book_ids}. Command ID: {command_id}")
    else:
        logger.error(f"Error triggering BookSearch command for book IDs {book_ids}")
    return response
