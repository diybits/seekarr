#!/usr/bin/env python3

from flask import Blueprint, request, jsonify
import datetime, os
from src.primary import keys_manager
from src.primary.state import get_state_file_path, reset_state_file
from src.primary.utils.logger import get_logger
import traceback
from src.primary.utils.connection_test import test_arr_connection

lidarr_bp = Blueprint('lidarr', __name__)
lidarr_logger = get_logger("lidarr")

# Make sure we're using the correct state files
PROCESSED_MISSING_FILE = get_state_file_path("lidarr", "processed_missing")
PROCESSED_UPGRADES_FILE = get_state_file_path("lidarr", "processed_upgrades")

@lidarr_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connection to a Lidarr API instance"""
    data = request.json
    return test_arr_connection(
        data.get('api_url'), data.get('api_key'), data.get('api_timeout', 30),
        "Lidarr", "api/v1"
    )
