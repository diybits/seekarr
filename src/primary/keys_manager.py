#!/usr/bin/env python3
"""
Keys manager for Seekarr
Thin wrapper around settings_manager that provides api_url/api_key access
for callers that predate the settings_manager migration.
"""

from typing import Any, Dict, Tuple


def load_api_keys(app_name: str) -> Dict[str, Any]:
    """Return the full settings dict for an app (delegates to settings_manager)."""
    from src.primary import settings_manager
    return settings_manager.load_settings(app_name)


def get_api_keys(app_name: str) -> Tuple[str, str]:
    """Return (api_url, api_key) for an app.

    For apps using the instances model, returns the first enabled instance.
    For apps using a flat settings model, returns top-level values.
    Returns ('', '') if the app is not configured.
    """
    from src.primary import settings_manager
    settings = settings_manager.load_settings(app_name)

    instances = settings.get("instances", [])
    if instances:
        for instance in instances:
            if instance.get("enabled", True):
                return instance.get("api_url", ""), instance.get("api_key", "")
        return "", ""

    return settings.get("api_url", ""), settings.get("api_key", "")
