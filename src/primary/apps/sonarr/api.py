#!/usr/bin/env python3
"""
Sonarr-specific API functions
Handles all communication with the Sonarr API
"""

import requests
import json
import time
import traceback
from typing import List, Dict, Any, Optional, Union
# Correct the import path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Sonarr app
sonarr_logger = get_logger("sonarr")

# Use a session for better performance
session = requests.Session()

def arr_request(api_url: str, api_key: str, api_timeout: int, endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Any:
    """
    Make a request to the Sonarr API.

    Args:
        api_url: The base URL of the Sonarr API
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
            sonarr_logger.error("No URL or API key provided")
            return None

        # Ensure api_url has a scheme
        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            sonarr_logger.error(f"Invalid URL format: {api_url} - URL must start with http:// or https://")
            return None

        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"

        sonarr_logger.debug(f"Making {method} request to: {full_url}")

        # Set up headers with User-Agent to identify Seekarr
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "Seekarr/7.0.0 (https://github.com/diybits/seekarr)"
        }

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            sonarr_logger.debug("SSL verification disabled by user setting")

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
                sonarr_logger.error(f"Unsupported HTTP method: {method}")
                return None

            # Check for successful response
            response.raise_for_status()

            # Check if there's any content before trying to parse JSON
            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError as jde:
                    # Log detailed information about the malformed response
                    sonarr_logger.error(f"Error decoding JSON response from {endpoint}: {str(jde)}")
                    sonarr_logger.error(f"Response status code: {response.status_code}")
                    sonarr_logger.error(f"Response content (first 200 chars): {response.content[:200]}")
                    return None
            else:
                sonarr_logger.debug(f"Empty response content from {endpoint}, returning empty dict")
                return {}

        except requests.exceptions.RequestException as e:
            # Add detailed error logging
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_details += f", Status Code: {e.response.status_code}"
                if e.response.content:
                    error_details += f", Content: {e.response.content[:200]}"

            sonarr_logger.error(f"Error during {method} request to {endpoint}: {error_details}")
            return None
    except Exception as e:
        # Catch all exceptions and log them with traceback
        sonarr_logger.error(f"CRITICAL ERROR in arr_request: {str(e)}")
        sonarr_logger.error(f"Full traceback: {traceback.format_exc()}")
        return None

def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Checks connection by fetching system status."""
    if not api_url:
        sonarr_logger.error("API URL is empty or not set")
        return False
    if not api_key:
        sonarr_logger.error("API Key is empty or not set")
        return False

    try:
        # Use a shorter timeout for a quick connection check
        quick_timeout = min(api_timeout, 15)
        status = get_system_status(api_url, api_key, quick_timeout)
        if status and isinstance(status, dict) and 'version' in status:
             # Log success only if debug is enabled to avoid clutter
             sonarr_logger.debug(f"Connection check successful for {api_url}. Version: {status.get('version')}")
             return True
        else:
             # Log details if the status response was unexpected
             sonarr_logger.warning(f"Connection check for {api_url} returned unexpected status: {str(status)[:200]}")
             return False
    except Exception:
        # Error should have been logged by arr_request, just indicate failure
        sonarr_logger.error(f"Connection check failed for {api_url}")
        return False

def get_system_status(api_url: str, api_key: str, api_timeout: int) -> Dict:
    """
    Get Sonarr system status.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        System status information or empty dict if request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "system/status")
    if response:
        return response
    return {}

def get_series(api_url: str, api_key: str, api_timeout: int, series_id: Optional[int] = None) -> Union[List, Dict, None]:
    """
    Get series information from Sonarr.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        series_id: Optional series ID to get a specific series

    Returns:
        List of all series, a specific series, or None if request failed
    """
    if series_id:
        endpoint = f"series/{series_id}"
    else:
        endpoint = "series"

    return arr_request(api_url, api_key, api_timeout, endpoint)

def get_episode(api_url: str, api_key: str, api_timeout: int, episode_id: int) -> Dict:
    """
    Get episode information by ID.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        episode_id: The episode ID

    Returns:
        Episode information or empty dict if request failed
    """
    response = arr_request(api_url, api_key, api_timeout, f"episode/{episode_id}")
    if response:
        return response
    return {}

def get_queue(api_url: str, api_key: str, api_timeout: int) -> List:
    """
    Get the current queue from Sonarr.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        Queue information or empty list if request failed
    """
    response = arr_request(api_url, api_key, api_timeout, "queue")
    if not response or "records" not in response:
        return []

    return response.get("records", [])

def get_calendar(api_url: str, api_key: str, api_timeout: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List:
    """
    Get calendar information for a date range.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        start_date: Optional start date (ISO format)
        end_date: Optional end date (ISO format)

    Returns:
        Calendar information or empty list if request failed
    """
    params = {}
    if start_date:
        params["start"] = start_date
    if end_date:
        params["end"] = end_date

    response = arr_request(api_url, api_key, api_timeout, "calendar", params=params or None)
    if response:
        return response
    return []

def command_status(api_url: str, api_key: str, api_timeout: int, command_id: Union[int, str]) -> Dict:
    """
    Get the status of a command by ID.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The command ID

    Returns:
        Command status information or empty dict if request failed
    """
    response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
    if response:
        return response
    return {}

def _fetch_paginated(
    api_url: str, api_key: str, api_timeout: int,
    endpoint: str, extra_params: Dict[str, Any],
    log_label: str, page_size: int = 1000
) -> List[Dict[str, Any]]:
    """Fetch all pages from a paginated Sonarr wanted/* endpoint with per-page retry."""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Seekarr/7.0.0 (https://github.com/diybits/seekarr)"
    }
    url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"
    retries_per_page = 2
    retry_delay = 3
    all_records: List[Dict] = []
    page = 1

    while True:
        retry_count = 0
        success = False
        records: List[Dict] = []

        while retry_count <= retries_per_page and not success:
            params = {"page": page, "pageSize": page_size, **extra_params}
            sonarr_logger.debug(f"Requesting {log_label} page {page} (attempt {retry_count + 1}/{retries_per_page + 1})")

            try:
                response = session.get(url, headers=headers, params=params, timeout=api_timeout, verify=get_ssl_verify_setting())
                response.raise_for_status()

                if not response.content:
                    sonarr_logger.warning(f"Empty response for {log_label} page {page} (attempt {retry_count + 1})")
                    if retry_count < retries_per_page:
                        retry_count += 1
                        time.sleep(retry_delay)
                        continue
                    sonarr_logger.error(f"Giving up on empty response after {retries_per_page + 1} attempts")
                    break

                data = response.json()
                records = data.get('records', [])

                if page == 1:
                    sonarr_logger.debug(f"Sonarr reports {data.get('totalRecords', 0)} total {log_label} records")

                if not records:
                    sonarr_logger.debug(f"No more {log_label} records on page {page}, stopping pagination")
                    success = True
                    break

                all_records.extend(records)
                success = True
                if len(records) < page_size:
                    sonarr_logger.debug(f"Received {len(records)} records (< page size {page_size}), last page")
                    break

            except json.JSONDecodeError as e:
                sonarr_logger.error(f"JSON decode error for {log_label} page {page} (attempt {retry_count + 1}): {e}")
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay)
                    continue
                break
            except requests.exceptions.Timeout as e:
                sonarr_logger.error(f"Timeout for {log_label} page {page} (attempt {retry_count + 1}): {e}")
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay * 2)
                    continue
                break
            except requests.exceptions.RequestException as e:
                sonarr_logger.error(f"Request error for {log_label} page {page} (attempt {retry_count + 1}): {e}")
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay)
                    continue
                break
            except Exception as e:
                sonarr_logger.error(f"Unexpected error for {log_label} page {page} (attempt {retry_count + 1}): {e}")
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay)
                    continue
                break

        if not success or not records:
            break
        page += 1

    sonarr_logger.info(f"Fetched {len(all_records)} {log_label} records total")
    return all_records


def get_missing_episodes(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, series_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get missing episodes from Sonarr, handling pagination."""
    extra: Dict[str, Any] = {"includeSeries": "true"}
    if series_id is not None:
        extra["seriesId"] = series_id
    episodes = _fetch_paginated(api_url, api_key, api_timeout, "wanted/missing", extra, "missing episodes")
    if monitored_only:
        return [ep for ep in episodes if ep.get('series', {}).get('monitored', False) and ep.get('monitored', False)]
    return episodes

def get_cutoff_unmet_episodes(api_url: str, api_key: str, api_timeout: int, monitored_only: bool) -> List[Dict[str, Any]]:
    """Get cutoff unmet episodes from Sonarr, handling pagination."""
    extra = {"includeSeries": "true", "sortKey": "airDateUtc", "sortDir": "asc"}
    episodes = _fetch_paginated(api_url, api_key, api_timeout, "wanted/cutoff", extra, "cutoff unmet episodes")
    if monitored_only:
        return [ep for ep in episodes if ep.get('series', {}).get('monitored', False) and ep.get('monitored', False)]
    return episodes

def get_cutoff_unmet_episodes_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int) -> List[Dict[str, Any]]:
    """
    Get a specified number of random cutoff unmet episodes by selecting a random page.
    This is much more efficient for very large libraries.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored episodes
        count: How many episodes to return

    Returns:
        A list of randomly selected cutoff unmet episodes
    """
    endpoint = "wanted/cutoff"
    page_size = 100  # Smaller page size to make the initial query faster

    # Get total record count from a minimal query
    data = arr_request(api_url, api_key, api_timeout, endpoint, params={"page": 1, "pageSize": 1, "includeSeries": "true"})
    if not data:
        sonarr_logger.error("Error getting random cutoff unmet episodes from Sonarr")
        return []

    total_records = data.get('totalRecords', 0)
    if total_records == 0:
        sonarr_logger.info("No cutoff unmet episodes found in Sonarr.")
        return []

    # Calculate total pages with our desired page size
    total_pages = (total_records + page_size - 1) // page_size
    sonarr_logger.info(f"Found {total_records} total cutoff unmet episodes across {total_pages} pages")

    if total_pages == 0:
        return []

    # Select a random page
    import random
    random_page = random.randint(1, total_pages)
    sonarr_logger.info(f"Selected random page {random_page} of {total_pages} for quality upgrade selection")

    # Get episodes from the random page
    data = arr_request(api_url, api_key, api_timeout, endpoint, params={"page": random_page, "pageSize": page_size, "includeSeries": "true"})
    if not data:
        sonarr_logger.error("Error getting cutoff unmet episodes page from Sonarr")
        return []

    records = data.get('records', [])
    sonarr_logger.info(f"Retrieved {len(records)} episodes from page {random_page}")

    # Apply monitored filter if requested
    if monitored_only:
        filtered_records = [
            ep for ep in records
            if ep.get('series', {}).get('monitored', False) and ep.get('monitored', False)
        ]
        sonarr_logger.debug(f"Filtered to {len(filtered_records)} monitored episodes")
        records = filtered_records

    # Select random episodes from this page
    if len(records) > count:
        selected_records = random.sample(records, count)
        sonarr_logger.debug(f"Randomly selected {len(selected_records)} episodes from page {random_page}")
        return selected_records
    else:
        # If we have fewer episodes than requested, return all of them
        sonarr_logger.debug(f"Returning all {len(records)} episodes from page {random_page} (fewer than requested {count})")
        return records

def get_missing_episodes_random_page(api_url: str, api_key: str, api_timeout: int, monitored_only: bool, count: int, series_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get a specified number of random missing episodes by selecting a random page.
    This is more efficient for very large libraries.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored episodes
        count: How many episodes to return
        series_id: Optional series ID to filter results for a specific series

    Returns:
        A list of randomly selected missing episodes, up to the requested count
    """
    endpoint = "wanted/missing"
    page_size = 100  # Smaller page size for better performance
    retries = 2
    retry_delay = 3

    count_params = {"page": 1, "pageSize": 1, "includeSeries": "true"}
    if series_id is not None:
        count_params["seriesId"] = series_id

    for attempt in range(retries + 1):
        # Get total record count from a minimal query
        sonarr_logger.debug(f"Getting missing episodes count (attempt {attempt+1}/{retries+1})")
        data = arr_request(api_url, api_key, api_timeout, endpoint, params=count_params)

        if data is None:
            sonarr_logger.warning(f"Failed to get missing episodes count (attempt {attempt+1})")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []

        total_records = data.get('totalRecords', 0)

        if total_records == 0:
            sonarr_logger.info("No missing episodes found in Sonarr.")
            return []

        # Calculate total pages with our desired page size
        total_pages = (total_records + page_size - 1) // page_size
        sonarr_logger.info(f"Found {total_records} total missing episodes across {total_pages} pages")

        if total_pages == 0:
            return []

        # Select a random page
        import random
        random_page = random.randint(1, total_pages)
        sonarr_logger.info(f"Selected random page {random_page} of {total_pages} for missing episodes")

        # Get episodes from the random page
        page_params = {"page": random_page, "pageSize": page_size, "includeSeries": "true"}
        if series_id is not None:
            page_params["seriesId"] = series_id

        page_data = arr_request(api_url, api_key, api_timeout, endpoint, params=page_params)

        if page_data is None:
            sonarr_logger.warning(f"Failed to get missing episodes page {random_page}")
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return []

        records = page_data.get('records', [])
        sonarr_logger.info(f"Retrieved {len(records)} missing episodes from page {random_page}")

        # Apply monitored filter if requested
        if monitored_only:
            filtered_records = [
                ep for ep in records
                if ep.get('series', {}).get('monitored', False) and ep.get('monitored', False)
            ]
            sonarr_logger.debug(f"Filtered to {len(filtered_records)} monitored missing episodes")
            records = filtered_records

        # Select random episodes from this page
        if len(records) > count:
            selected_records = random.sample(records, count)
            sonarr_logger.debug(f"Randomly selected {len(selected_records)} missing episodes from page {random_page}")
            return selected_records
        else:
            sonarr_logger.debug(f"Returning all {len(records)} missing episodes from page {random_page} (fewer than requested {count})")
            return records

    sonarr_logger.error("All attempts to get missing episodes failed")
    return []

def search_episode(api_url: str, api_key: str, api_timeout: int, episode_ids: List[int]) -> Optional[Union[int, str]]:
    """Trigger a search for specific episodes in Sonarr."""
    if not episode_ids:
        sonarr_logger.warning("No episode IDs provided for search.")
        return None
    payload = {"name": "EpisodeSearch", "episodeIds": episode_ids}
    response = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)
    if response and 'id' in response:
        command_id = response['id']
        sonarr_logger.info(f"Triggered Sonarr search for episode IDs: {episode_ids}. Command ID: {command_id}")
        return command_id
    sonarr_logger.error(f"Failed to trigger search for episode IDs {episode_ids}. Response: {response}")
    return None

def get_command_status(api_url: str, api_key: str, api_timeout: int, command_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """Get the status of a Sonarr command."""
    response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
    if response:
        sonarr_logger.debug(f"Checked Sonarr command status for ID {command_id}: {response.get('status')}")
    else:
        sonarr_logger.error(f"Error getting Sonarr command status for ID {command_id}")
    return response or None

def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """Get the current size of the Sonarr download queue."""
    response = arr_request(api_url, api_key, api_timeout, "queue", params={"page": 1, "pageSize": 1})
    if response is None:
        sonarr_logger.error("Failed to get Sonarr download queue size")
        return -1
    queue_size = response.get('totalRecords', 0)
    sonarr_logger.debug(f"Sonarr download queue size: {queue_size}")
    return queue_size

def get_series_by_id(api_url: str, api_key: str, api_timeout: int, series_id: int) -> Optional[Dict[str, Any]]:
    """Get series details by ID from Sonarr."""
    response = arr_request(api_url, api_key, api_timeout, f"series/{series_id}")
    if response:
        sonarr_logger.debug(f"Fetched details for Sonarr series ID: {series_id}")
    else:
        sonarr_logger.error(f"Error getting Sonarr series details for ID {series_id}")
    return response or None

def search_season(api_url: str, api_key: str, api_timeout: int, series_id: int, season_number: int) -> Optional[Union[int, str]]:
    """Trigger a search for a specific season in Sonarr."""
    payload = {"name": "SeasonSearch", "seriesId": series_id, "seasonNumber": season_number}
    response = arr_request(api_url, api_key, api_timeout, "command", method="POST", data=payload)
    if response and 'id' in response:
        command_id = response['id']
        sonarr_logger.info(f"Triggered Sonarr season search for series ID: {series_id}, season: {season_number}. Command ID: {command_id}")
        return command_id
    sonarr_logger.error(f"Failed to trigger season search for series ID {series_id}, season {season_number}. Response: {response}")
    return None

def get_cutoff_unmet_episodes_for_series(api_url: str, api_key: str, api_timeout: int, series_id: int, monitored_only: bool = True) -> List[Dict[str, Any]]:
    """Get all cutoff unmet episodes for a specific series, handling pagination."""
    extra = {"includeSeries": "true", "sortKey": "airDateUtc", "sortDir": "asc", "seriesId": series_id}
    episodes = _fetch_paginated(api_url, api_key, api_timeout, "wanted/cutoff", extra, f"cutoff unmet for series {series_id}")
    verified = [ep for ep in episodes if ep.get('seriesId') == series_id]
    if len(verified) < len(episodes):
        sonarr_logger.warning(f"Filtered out {len(episodes) - len(verified)} episodes not belonging to series {series_id}")
    sonarr_logger.info(f"Found {len(verified)} cutoff unmet episodes for series {series_id}")
    if monitored_only:
        return [ep for ep in verified if ep.get('series', {}).get('monitored', False) and ep.get('monitored', False)]
    return verified

def get_series_with_missing_episodes(api_url: str, api_key: str, api_timeout: int, monitored_only: bool = True, limit: int = 50, random_mode: bool = True) -> List[Dict[str, Any]]:
    """
    Get a list of series that have missing episodes, along with missing episode counts per season.
    This is much more efficient than fetching all missing episodes for large libraries.

    Args:
        api_url: The base URL of the Sonarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to only include monitored series
        limit: Maximum number of series to return
        random_mode: Whether to randomly select series

    Returns:
        A list of series with missing episodes and counts per season
    """
    # Step 1: Get all series
    all_series = get_series(api_url, api_key, api_timeout)
    if not all_series:
        sonarr_logger.error("Failed to retrieve series list")
        return []

    # Step 2: Filter to monitored series if requested
    if monitored_only:
        filtered_series = [s for s in all_series if s.get('monitored', False)]
        sonarr_logger.info(f"Filtered from {len(all_series)} total series to {len(filtered_series)} monitored series")
    else:
        filtered_series = all_series

    # Apply random selection if requested
    if random_mode:
        import random
        sonarr_logger.info("Using RANDOM selection mode for missing episodes")
        random.shuffle(filtered_series)
    else:
        sonarr_logger.info("Using SEQUENTIAL selection mode for missing episodes")

    # Step 3: For each series, check if it has missing episodes using episode endpoint
    # This is much more efficient than using the wanted/missing endpoint
    series_with_missing = []
    examined_count = 0

    for series in filtered_series[:limit]:
        examined_count += 1
        series_id = series.get('id')
        series_title = series.get('title', 'Unknown')

        if not series_id:
            continue

        # Get all episodes for this series
        try:
            episodes = arr_request(api_url, api_key, api_timeout, "episode", params={"seriesId": series_id})
            if not episodes:
                continue

            # Filter to missing episodes
            missing_episodes = [
                e for e in episodes
                if e.get('hasFile') is False and
                (not monitored_only or e.get('monitored', False))
            ]

            if not missing_episodes:
                continue

            # Group by season
            seasons_dict = {}
            for episode in missing_episodes:
                season_number = episode.get('seasonNumber')
                if season_number is not None:
                    if season_number not in seasons_dict:
                        seasons_dict[season_number] = []
                    seasons_dict[season_number].append(episode)

            # If we have any seasons with missing episodes, add this series to our result
            if seasons_dict:
                missing_info = {
                    'series_id': series_id,
                    'series_title': series_title,
                    'seasons': [
                        {
                            'season_number': season,
                            'episode_count': len(episodes),
                            'episodes': episodes
                        }
                        for season, episodes in seasons_dict.items()
                    ]
                }
                series_with_missing.append(missing_info)

                sonarr_logger.debug(f"Found series {series_title} with {len(missing_episodes)} missing episodes across {len(seasons_dict)} seasons")

        except Exception as e:
            sonarr_logger.error(f"Error checking missing episodes for series {series_title} (ID: {series_id}): {str(e)}")
            continue

    selection_mode = "RANDOM" if random_mode else "SEQUENTIAL"
    sonarr_logger.info(f"Examined {examined_count} series ({selection_mode} mode) and found {len(series_with_missing)} with missing episodes")
    return series_with_missing
