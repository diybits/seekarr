#!/usr/bin/env python3
"""
Readarr-specific API functions
Handles all communication with the Readarr API
"""

import requests
from typing import List, Dict, Any, Optional
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings, get_ssl_verify_setting

# Get app-specific logger
logger = get_logger("readarr")

# Use a session for better performance
session = requests.Session()

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
    logger = get_logger(app_type)

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
            logger.error(f"Error loading {app_type} settings: {e}")
            return None

    if not url or not key:
        logger.error(f"Missing API URL or key for {app_type}")
        return None

    url = url.rstrip('/')
    endpoint = endpoint.lstrip('/')
    full_url = f"{url}/api/v1/{endpoint}"

    headers = {
        "X-Api-Key": key,
        "Content-Type": "application/json",
        "User-Agent": "Seekarr/7.0.0 (https://github.com/diybits/seekarr)"
    }

    verify_ssl = get_ssl_verify_setting()

    if not verify_ssl:
        logger.debug("SSL verification disabled by user setting")

    logger.debug(f"Making {method} request to {full_url}")

    try:
        if method.upper() == "GET":
            response = session.get(full_url, headers=headers, params=params, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "POST":
            response = session.post(full_url, headers=headers, json=data, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "PUT":
            response = session.put(full_url, headers=headers, json=data, timeout=timeout, verify=verify_ssl)
        elif method.upper() == "DELETE":
            response = session.delete(full_url, headers=headers, timeout=timeout, verify=verify_ssl)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None

        response.raise_for_status()

        if response.text:
            return response.json()
        return {}

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None


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


def get_cutoff_unmet_books(api_url: Optional[str] = None, api_key: Optional[str] = None, api_timeout: Optional[int] = None) -> List[Dict]:
    """
    Get a list of books that don't meet their quality profile cutoff.
    Accepts optional API credentials.

    Args:
        api_url: Optional API URL
        api_key: Optional API key
        api_timeout: Optional API timeout

    Returns:
        A list of book objects that need quality upgrades
    """
    books = arr_request(api_url, api_key, api_timeout, "wanted/cutoff?cutoffUnmet=true")
    if not books or "records" not in books:
        return []

    return books.get("records", [])


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

    all_missing_books = []
    page = 1
    page_size = 100

    while True:
        params = {'page': page, 'pageSize': page_size}
        data = arr_request(api_url, api_key, api_timeout, "wanted/missing", params=params)

        if not data or 'records' not in data or not data['records']:
            break

        all_missing_books.extend(data['records'])

        total_records = data.get('totalRecords', 0)
        if len(all_missing_books) >= total_records:
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
