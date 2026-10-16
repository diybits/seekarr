#!/usr/bin/env python3
"""
Radarr-specific API functions
Handles all communication with the Radarr API
"""

import time
from typing import List, Dict, Any, Optional
# Correct the import path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting
import src.primary.utils.arr_client as arr_client

# Get logger for the Radarr app
radarr_logger = get_logger("radarr")

# Shared session (re-exported so callers/tests can keep using radarr_api.session)
session = arr_client.session

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Any:
    """
    Make a request to the Radarr API.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call (without /api/v3/)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests
    
    Returns:
        The parsed JSON response or None if the request failed
    """
    # Delegated to the shared *Arr client (src/primary/utils/arr_client.py).
    # get_ssl_verify_setting() is resolved here (app namespace) so existing
    # test monkeypatches on this module keep working.
    return arr_client.arr_request(
        "radarr", api_url, api_key, api_timeout, endpoint,
        method=method, data=data, params=params,
        api_prefix="v3",
        ssl_verify=get_ssl_verify_setting(),
    )

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    if not api_url or not api_key:
        radarr_logger.error("Radarr API URL or API Key not provided for queue size check.")
        return -1
    response = arr_request(api_url, api_key, api_timeout, "queue", params={"page": 1, "pageSize": 1000})
    if response is None:
        radarr_logger.error("Error getting Radarr download queue size.")
        return -1
    queue_size = response.get('totalRecords', 0)
    radarr_logger.debug(f"Radarr download queue size: {queue_size}")
    return queue_size

def get_movies_with_missing(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get a list of movies with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects with missing files, or None if the request failed.
    """
    # Use the updated arr_request with passed arguments
    movies = arr_request(api_url, api_key, api_timeout, "movie")
    if movies is None: # Check for None explicitly, as an empty list is valid
        radarr_logger.error("Failed to retrieve movies from Radarr API.")
        return None
    
    missing_movies = []
    for movie in movies:
        is_monitored = movie.get("monitored", False)
        has_file = movie.get("hasFile", False)
        # Apply monitored_only filter if requested
        if not has_file and (not monitored_only or is_monitored):
            missing_movies.append(movie)
    
    radarr_logger.debug(f"Found {len(missing_movies)} missing movies (monitored_only={monitored_only}).")
    return missing_movies

def get_cutoff_unmet_movies(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> Optional[List[Dict]]:
    """
    Get a list of movies that don't meet their quality profile cutoff.

    Uses Radarr's native GET /api/v3/wanted/cutoff endpoint, which applies the
    same upgradability logic as the Radarr UI (quality cutoff AND custom-format
    cutoff score) instead of comparing raw quality IDs client-side.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects (full MovieResource records) that need quality
        upgrades, or None if the request failed.
    """
    # Radarr's `monitored` query param is an equality filter (default true), so
    # "include unmonitored too" requires one pass per value.
    monitored_values = [True] if monitored_only else [True, False]

    page_size = 1000
    unmet_movies = []
    for monitored in monitored_values:
        fetched = 0
        page = 1
        while True:
            params = {"page": page, "pageSize": page_size, "monitored": monitored}
            data = arr_request(api_url, api_key, api_timeout, "wanted/cutoff", params=params)
            if data is None:
                radarr_logger.error(f"Failed to retrieve cutoff unmet movies from Radarr API (monitored={monitored}).")
                return None
            records = data.get("records", [])
            unmet_movies.extend(records)
            fetched += len(records)
            total_records = data.get("totalRecords", fetched)
            if not records or fetched >= total_records:
                break
            page += 1

    radarr_logger.debug(f"Found {len(unmet_movies)} cutoff unmet movies (monitored_only={monitored_only}).")
    return unmet_movies

def movie_search(api_url: str, api_key: str, api_timeout: int, movie_ids: List[int]) -> Optional[int]:
    """
    Trigger a search for one or more movies.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_ids: A list of movie IDs to search for
        
    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    if not movie_ids:
        radarr_logger.warning("No movie IDs provided for search.")
        return None
        
    endpoint = "command"
    data = {
        "name": "MoviesSearch",
        "movieIds": movie_ids
    }
    
    # Use the updated arr_request
    response = arr_request(api_url, api_key, api_timeout, endpoint, method="POST", data=data)
    if response and 'id' in response:
        command_id = response['id']
        radarr_logger.debug(f"Triggered search for movie IDs: {movie_ids}. Command ID: {command_id}")
        return command_id
    else:
        radarr_logger.error(f"Failed to trigger search command for movie IDs {movie_ids}. Response: {response}")
        return None

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Check the connection to Radarr API."""
    if not api_url:
        radarr_logger.error("API URL is empty or not set")
        return False
    if not (api_url.startswith('http://') or api_url.startswith('https://')):
        radarr_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
        return False
    status = arr_request(api_url, api_key, api_timeout, "system/status")
    if status and isinstance(status, dict) and 'version' in status:
        radarr_logger.debug(f"Successfully connected to Radarr. Version: {status.get('version')}")
        return True
    radarr_logger.warning(f"Connection check for {api_url} returned unexpected status: {str(status)[:200]}")
    return False

def wait_for_command(api_url: str, api_key: str, api_timeout: int, command_id: int, 
                    delay_seconds: int = 1, max_attempts: int = 600) -> bool:
    """
    Wait for a command to complete.
    
    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to wait for
        delay_seconds: Seconds to wait between command status checks
        max_attempts: Maximum number of status check attempts
        
    Returns:
        True if the command completed successfully, False if timed out
    """
    attempts = 0
    while attempts < max_attempts:
        response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
        if response and 'state' in response:
            state = response['state']
            if state == "completed":
                return True
            elif state == "failed":
                radarr_logger.error(f"Command {command_id} failed")
                return False
        time.sleep(delay_seconds)
        attempts += 1
    radarr_logger.warning(f"Timed out waiting for command {command_id} to complete")
    return False
