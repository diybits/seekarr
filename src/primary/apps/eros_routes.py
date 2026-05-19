#!/usr/bin/env python3

from flask import Blueprint, request, jsonify
import os
from src.primary.state import get_state_file_path, reset_state_file
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import load_settings
from src.primary.apps.eros import api as eros_api
from src.primary.utils.connection_test import test_arr_connection

eros_bp = Blueprint('eros', __name__)
eros_logger = get_logger("eros")

# Make sure we're using the correct state files
PROCESSED_MISSING_FILE = get_state_file_path("eros", "processed_missing")
PROCESSED_UPGRADES_FILE = get_state_file_path("eros", "processed_upgrades")

def get_configured_instances():
    # Load Eros settings
    settings = load_settings("eros")
    instances = settings.get("instances", [])
    return instances

@eros_bp.route('/status', methods=['GET'])
def get_status():
    """Get the status of all configured Eros instances"""
    try:
        instances = get_configured_instances()
        eros_logger.debug(f"Eros configured instances: {instances}")
        if instances:
            connected_count = 0
            for instance in instances:
                api_url = instance.get('api_url')
                api_key = instance.get('api_key')
                if api_url and api_key and eros_api.check_connection(api_url, api_key, 5):
                    connected_count += 1
            return jsonify({
                "configured": True,
                "connected": connected_count > 0,
                "connected_count": connected_count,
                "total_configured": len(instances)
            })
        else:
            eros_logger.debug("No Eros instances configured")
            return jsonify({"configured": False, "connected": False})
    except Exception as e:
        eros_logger.error(f"Error getting Eros status: {str(e)}")
        return jsonify({"configured": False, "connected": False, "error": str(e)})

@eros_bp.route('/test-connection', methods=['POST'])
def test_connection_endpoint():
    """Test connection to an Eros API instance"""
    data = request.json
    return test_arr_connection(
        data.get('api_url'), data.get('api_key'), data.get('api_timeout', 30),
        "Eros", "api/v3", version_prefix="3"
    )

@eros_bp.route('/test-settings', methods=['GET'])
def test_eros_settings():
    """Debug endpoint to test Eros settings loading"""
    try:
        # Directly read the settings file to bypass any potential caching
        import json

        # Check all possible settings locations
        possible_locations = [
            "/config/eros.json",  # Main Docker mount
            "/app/config/eros.json",  # Alternate location
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "eros.json")  # Relative path
        ]

        results = {}

        # Try all locations
        for location in possible_locations:
            results[location] = {"exists": os.path.exists(location)}
            if os.path.exists(location):
                try:
                    with open(location, 'r') as f:
                        results[location]["content"] = json.load(f)
                except Exception as e:
                    results[location]["error"] = str(e)

        # Also try loading via settings_manager
        try:
            from src.primary.settings_manager import load_settings
            settings = load_settings("eros")
            results["settings_manager"] = settings
        except Exception as e:
            results["settings_manager_error"] = str(e)

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})

@eros_bp.route('/reset-processed', methods=['POST'])
def reset_processed_state():
    """Reset the processed state files for Eros"""
    try:
        # Reset the state files for missing and upgrades
        reset_state_file("eros", "processed_missing")
        reset_state_file("eros", "processed_upgrades")

        eros_logger.info("Successfully reset Eros processed state files")
        return jsonify({"success": True, "message": "Successfully reset processed state"})
    except Exception as e:
        error_msg = f"Error resetting Eros state: {str(e)}"
        eros_logger.error(error_msg)
        return jsonify({"success": False, "message": error_msg}), 500
