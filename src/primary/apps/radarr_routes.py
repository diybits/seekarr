#!/usr/bin/env python3

from flask import Blueprint, request
from src.primary.state import get_state_file_path
from src.primary.utils.logger import get_logger
from src.primary.utils.connection_test import test_arr_connection

radarr_bp = Blueprint('radarr', __name__)
radarr_logger = get_logger("radarr")

# Make sure we're using the correct state files
PROCESSED_MISSING_FILE = get_state_file_path("radarr", "processed_missing")
PROCESSED_UPGRADES_FILE = get_state_file_path("radarr", "processed_upgrades")

@radarr_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connection to a Radarr API instance"""
    data = request.json
    return test_arr_connection(
        data.get('api_url'), data.get('api_key'), data.get('api_timeout', 30),
        "Radarr", "api/v3"
    )
