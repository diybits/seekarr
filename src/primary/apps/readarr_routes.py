#!/usr/bin/env python3

from flask import Blueprint, request
from src.primary.state import get_state_file_path
from src.primary.utils.logger import get_logger
from src.primary.utils.connection_test import test_arr_connection

readarr_bp = Blueprint('readarr', __name__)
readarr_logger = get_logger("readarr")

# Make sure we're using the correct state files
PROCESSED_MISSING_FILE = get_state_file_path("readarr", "processed_missing")
PROCESSED_UPGRADES_FILE = get_state_file_path("readarr", "processed_upgrades")

@readarr_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connection to a Readarr API instance"""
    data = request.json
    return test_arr_connection(
        data.get('api_url'), data.get('api_key'), data.get('api_timeout', 30),
        "Readarr", "api/v1"
    )
