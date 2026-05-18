#!/usr/bin/env python3
"""
Authentication module for Seekarr
Handles user creation, verification, and session management
Including two-factor authentication
"""

import os
import json
import hashlib
import secrets
import time
import pathlib
import threading
import base64
import io
import qrcode
import pyotp # Ensure pyotp is imported
import re # Import the re module for regex
import bcrypt
from typing import Dict, Any, Optional, Tuple
from flask import request, redirect, url_for, session
from .utils.logger import logger # Ensure logger is imported

# User directory setup
USER_DIR = pathlib.Path("/config/user")
try:
    USER_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    pass
USER_FILE = USER_DIR / "credentials.json"

# Session settings
SESSION_EXPIRY = 60 * 60 * 24 * 7  # 1 week in seconds
SESSION_COOKIE_NAME = "seekarr_session"

# Session persistence
_session_lock = threading.Lock()
_SESSIONS_FILE = pathlib.Path("/config/sessions.json")

active_sessions: Dict[str, Dict] = {}


def _load_sessions() -> None:
    """Load persisted sessions into active_sessions, dropping any that have expired."""
    global active_sessions
    if not _SESSIONS_FILE.exists():
        return
    try:
        with open(_SESSIONS_FILE, "r") as f:
            data = json.load(f)
        now = time.time()
        active_sessions = {sid: s for sid, s in data.items() if s.get("expires_at", 0) > now}
        if active_sessions:
            logger.info(f"Loaded {len(active_sessions)} active session(s) from disk")
    except Exception as e:
        logger.warning(f"Could not load sessions file: {e}")


def _save_sessions() -> None:
    """Write active_sessions to disk atomically. Caller must hold _session_lock."""
    try:
        _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SESSIONS_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(active_sessions, f)
        tmp.replace(_SESSIONS_FILE)
        try:
            os.chmod(_SESSIONS_FILE, 0o600)
        except OSError:
            pass
    except Exception as e:
        logger.warning(f"Could not save sessions file: {e}")


_load_sessions()

# --- Add Helper functions for user data ---
def get_user_data() -> Dict[str, Any]:
    """Load user data from the credentials file."""
    if not USER_FILE.exists():
        logger.warning(f"Attempted to get user data, but file not found: {USER_FILE}")
        return {}
    try:
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from user file: {USER_FILE}")
        return {}
    except Exception as e:
        logger.error(f"Error reading user file {USER_FILE}: {e}", exc_info=True)
        return {}

def save_user_data(user_data: Dict[str, Any]) -> bool:
    """Save user data to the credentials file."""
    try:
        logger.debug(f"Attempting to save user data to: {USER_FILE}")
        # Ensure directory exists (though it should from startup)
        USER_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(USER_FILE, 'w') as f:
            json.dump(user_data, f, indent=4) # Add indent for readability
        
        # Set permissions after writing
        try:
            os.chmod(USER_FILE, 0o600)
            logger.debug(f"Set permissions 0o600 on {USER_FILE}")
        except Exception as e_perm:
            logger.warning(f"Could not set permissions on file {USER_FILE}: {e_perm}")
            
        logger.info(f"User data saved successfully to {USER_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving user file {USER_FILE}: {e}", exc_info=True)
        return False
# --- End Helper functions ---

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a password against its hash.

    Supports both bcrypt hashes (new) and legacy SHA-256 salt:hash pairs so
    that existing accounts continue to work until their hash is migrated on
    next successful login.
    """
    try:
        if stored_password.startswith('$2b$') or stored_password.startswith('$2a$'):
            return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))
        # Legacy SHA-256 format: "<hex-salt>:<hex-hash>"
        salt, pw_hash = stored_password.split(':', 1)
        verify_hash = hashlib.sha256((provided_password + salt).encode()).hexdigest()
        return secrets.compare_digest(verify_hash, pw_hash)
    except Exception as e:
        logger.error(f"Error verifying password hash: {e}", exc_info=True)
        return False

def hash_username(username: str) -> str:
    """Create a normalized hash of the username"""
    # Convert to lowercase and hash
    return hashlib.sha256(username.lower().encode()).hexdigest()

def validate_password_strength(password: str) -> Optional[str]:
    """Validate password strength based on defined criteria.

    Args:
        password: The password string to validate.

    Returns:
        An error message string if validation fails, None otherwise.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    
    # If check passes
    return None

def user_exists() -> bool:
    """Check if a user has been created"""
    return USER_FILE.exists() and os.path.getsize(USER_FILE) > 0

def create_user(username: str, password: str) -> bool:
    """Create a new user"""
    if not username or not password:
        logger.error("Attempted to create user with empty username or password")
        return False
        
    # Ensure user directory exists with proper permissions
    logger.info(f"Ensuring user directory exists: {USER_DIR}")
    USER_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Set appropriate permissions if not running as root
        logger.info(f"Setting permissions on directory: {USER_DIR}")
        os.chmod(USER_DIR, 0o755)
    except Exception as e:
        logger.warning(f"Could not set permissions on directory {USER_DIR}: {e}")
        
    # Hash the username and password
    username_hash = hash_username(username)
    password_hash = hash_password(password)
    
    # Store the credentials
    user_data = {
        "username": username_hash,
        "password": password_hash,
        "created_at": time.time(),
        "2fa_enabled": False,
        "2fa_secret": None
    }
    
    try:
        logger.info(f"Writing user file: {USER_FILE}")
        with open(USER_FILE, 'w') as f:
            json.dump(user_data, f)
        # Set appropriate permissions on the file
        try:
            logger.info(f"Setting permissions on file: {USER_FILE}")
            os.chmod(USER_FILE, 0o600)
        except Exception as e:
            logger.warning(f"Could not set permissions on file {USER_FILE}: {e}")
        logger.info("User creation successful")
        return True
    except Exception as e:
        logger.error(f"Error creating user file {USER_FILE}: {e}", exc_info=True)
        return False

def verify_user(username: str, password: str, otp_code: str = None) -> Tuple[bool, bool]:
    """
    Verify user credentials
    
    Returns:
        Tuple[bool, bool]: (auth_success, needs_2fa)
    """
    if not user_exists():
        logger.warning("Login attempt failed: User does not exist.")
        return False, False
        
    try:
        with open(USER_FILE, 'r') as f:
            user_data = json.load(f)
            
        # Hash the provided username
        username_hash = hash_username(username)
        
        # Compare username and verify password
        if user_data.get("username") == username_hash:
            stored_pw = user_data.get("password", "")
            if verify_password(stored_pw, password):
                # Silently upgrade legacy SHA-256 hash to bcrypt on successful login
                if not (stored_pw.startswith('$2b$') or stored_pw.startswith('$2a$')):
                    user_data["password"] = hash_password(password)
                    save_user_data(user_data)
                    logger.info(f"Migrated password hash to bcrypt for user '{username}'.")
                # Check if 2FA is enabled
                two_fa_enabled = user_data.get("2fa_enabled", False)
                logger.debug(f"2FA enabled for user '{username}': {two_fa_enabled}")
                logger.debug(f"2FA secret present: {bool(user_data.get('2fa_secret'))}")
                logger.debug(f"OTP code provided: {bool(otp_code)}")
                
                if two_fa_enabled:
                    # If 2FA code was provided, verify it
                    if otp_code:
                        totp = pyotp.TOTP(user_data.get("2fa_secret"))
                        valid_code = totp.verify(otp_code)
                        logger.debug(f"OTP code validation result: {valid_code}")
                        if valid_code:
                            logger.info(f"User '{username}' authenticated successfully with 2FA.")
                            return True, False
                        else:
                            logger.warning(f"Login attempt failed for user '{username}': Invalid 2FA code.")
                            return False, True
                    else:
                        # No OTP code provided but 2FA is enabled
                        logger.warning(f"Login attempt failed for user '{username}': 2FA code required but not provided.")
                        logger.debug("Returning needs_2fa=True to trigger 2FA input display")
                        return False, True
                else:
                    # 2FA not enabled, password is correct
                    logger.info(f"User '{username}' authenticated successfully (no 2FA).")
                    return True, False
            else:
                logger.warning(f"Login attempt failed for user '{username}': Invalid password.")
                return False, False
    except Exception as e:
        logger.error(f"Error during user verification for '{username}': {e}", exc_info=True)
    
    logger.warning(f"Login attempt failed for user '{username}': Username not found or other error.")
    return False, False

def create_session(username: str) -> str:
    """Create a new session for an authenticated user and persist it."""
    session_id = secrets.token_hex(32)
    with _session_lock:
        active_sessions[session_id] = {
            "username": username,
            "created_at": time.time(),
            "expires_at": time.time() + SESSION_EXPIRY,
        }
        _save_sessions()
    return session_id


def verify_session(session_id: str) -> bool:
    """Verify if a session is valid, extending its expiry window in memory."""
    if not session_id:
        return False
    with _session_lock:
        if session_id not in active_sessions:
            return False
        session_data = active_sessions[session_id]
        if session_data.get("expires_at", 0) < time.time():
            del active_sessions[session_id]
            _save_sessions()
            return False
        # Slide the expiry window in memory; persisted on next create/logout
        active_sessions[session_id]["expires_at"] = time.time() + SESSION_EXPIRY
        return True


def get_username_from_session(session_id: str) -> Optional[str]:
    """Get the username from a session."""
    if not session_id:
        return None
    with _session_lock:
        return active_sessions.get(session_id, {}).get("username")

def authenticate_request():
    """Flask route decorator to check if user is authenticated"""
    # If no user exists, redirect to setup
    if not user_exists():
        script_root = request.script_root
        setup_path = f"{script_root}/setup"
        static_path = f"{script_root}/static/"
        api_setup_path = f"{script_root}/api/setup"
        
        if request.path != setup_path and not request.path.startswith((static_path, api_setup_path)):
            return redirect(setup_path)
        return None
    
    # Skip authentication for static files and the login/setup pages
    script_root = request.script_root
    static_path = f"{script_root}/static/"
    login_path = f"{script_root}/login"
    api_login_path = f"{script_root}/api/login"
    setup_path = f"{script_root}/setup"
    api_setup_path = f"{script_root}/api/setup"
    favicon_path = f"{script_root}/favicon.ico"
    health_check_path = f"{script_root}/api/health"
    
    if request.path.startswith((static_path, login_path, api_login_path, setup_path, api_setup_path)) or request.path in (favicon_path, health_check_path):
        return None
    
    # Load general settings
    local_access_bypass = False
    proxy_auth_bypass = False
    try:
        # Force reload settings from disk to ensure we have the latest
        from src.primary.settings_manager import load_settings
        from src.primary import settings_manager
        
        settings = load_settings("general")  # Specify 'general' as the app_type
        general_settings = settings
        local_access_bypass = general_settings.get("local_access_bypass", False)
        proxy_auth_bypass = general_settings.get("proxy_auth_bypass", False)
        logger.debug(f"Local access bypass setting: {local_access_bypass}")
        logger.debug(f"Proxy auth bypass setting: {proxy_auth_bypass}")
        
        # Debug print all general settings
        logger.debug(f"All general settings: {general_settings}")
    except Exception as e:
        logger.error(f"Error loading authentication bypass settings: {e}", exc_info=True)
    
    # Check if proxy auth bypass is enabled - this completely disables authentication
    # Note: This has highest priority and is checked first (matching the "No Login Mode" in the UI)
    if proxy_auth_bypass:
        logger.info("Proxy authentication bypass is ENABLED (No Login Mode) - Authentication bypassed!")
        return None
    
    remote_addr = request.remote_addr
    logger.debug(f"Request IP address: {remote_addr}")

    if local_access_bypass:
        import ipaddress as _ipaddress
        _PRIVATE_NETWORKS = [
            _ipaddress.ip_network('127.0.0.0/8'),
            _ipaddress.ip_network('::1/128'),
            _ipaddress.ip_network('10.0.0.0/8'),
            _ipaddress.ip_network('172.16.0.0/12'),
            _ipaddress.ip_network('192.168.0.0/16'),
            _ipaddress.ip_network('fc00::/7'),
            _ipaddress.ip_network('fe80::/10'),
        ]
        try:
            ip = _ipaddress.ip_address(remote_addr)
            is_local = any(ip in net for net in _PRIVATE_NETWORKS)
        except ValueError:
            is_local = False

        if is_local:
            logger.info(f"Local network access from {remote_addr} - authentication bypassed (Local Bypass Mode)")
            return None
        else:
            logger.warning(f"Access from {remote_addr} is not a local network address - authentication required")
    else:
        logger.info("Local Bypass Mode is DISABLED - Authentication required")
    
    # Check for valid session
    session_id = session.get(SESSION_COOKIE_NAME)
    if session_id and verify_session(session_id):
        return None
    
    # No valid session, redirect to login
    script_root = request.script_root
    login_path = f"{script_root}/login"
    api_path = f"{script_root}/api/"
    
    if request.path != login_path and not request.path.startswith(api_path):
        return redirect(login_path)
    
    # For API calls, return 401 Unauthorized
    if request.path.startswith("/api/"):
        return {"error": "Unauthorized"}, 401
    
    return None

def logout(session_id: str):
    """Invalidate a session and remove it from disk."""
    with _session_lock:
        active_sessions.pop(session_id, None)
        _save_sessions()

def is_2fa_enabled(username):
    """Check if 2FA is enabled for a user."""
    user_data = get_user_data()
    return user_data.get('2fa_enabled', False)

def generate_2fa_secret(username: str) -> Tuple[str, str]:
    """
    Generate a new 2FA secret and QR code
    
    Returns:
        Tuple[str, str]: (secret, qr_code_data_uri)
    """
    # Generate a random secret
    secret = pyotp.random_base32()
    
    # Create a TOTP object
    totp = pyotp.TOTP(secret)
    
    # Get the provisioning URI - Use the actual username here
    uri = totp.provisioning_uri(name=username, issuer_name="Seekarr")
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    
    try:
        img = qr.make_image(fill_color="black", back_color="white")
    
        # Convert to base64 string
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
    
        # Store the secret temporarily associated with the user
        user_data = get_user_data()
        user_data["temp_2fa_secret"] = secret
        if save_user_data(user_data):
            logger.info(f"Generated temporary 2FA secret for user '{username}'.")
            return secret, f"data:image/png;base64,{img_str}"
        else:
            logger.error(f"Failed to save temporary 2FA secret for user '{username}'.")
            raise Exception("Failed to save user data with temporary 2FA secret.")
    
    except Exception as e:
        logger.error(f"Error generating 2FA QR code for user '{username}': {e}", exc_info=True)
        raise

def verify_2fa_code(username: str, code: str, enable_on_verify: bool = False) -> bool:
    """Verify a 2FA code against the temporary secret"""
    user_data = get_user_data()
    temp_secret = user_data.get("temp_2fa_secret")
    
    if not temp_secret:
        logger.warning(f"2FA verification attempt for '{username}' failed: No temporary secret found.")
        return False
    
    totp = pyotp.TOTP(temp_secret)
    if totp.verify(code):
        logger.info(f"2FA code verified successfully for user '{username}'.")
        if enable_on_verify:
            user_data["2fa_enabled"] = True
            user_data["2fa_secret"] = temp_secret
            user_data.pop("temp_2fa_secret", None)
            if save_user_data(user_data):
                logger.info(f"2FA enabled permanently for user '{username}'.")
            else:
                logger.error(f"Failed to save user data after enabling 2FA for '{username}'.")
                return False
        return True
    else:
        logger.warning(f"Invalid 2FA code provided by user '{username}'.")
        return False

def disable_2fa(password: str) -> bool:
    """Disable 2FA for the current user (using only password - kept for potential other uses)"""
    user_data = get_user_data()
    
    # Verify password
    if verify_password(user_data.get("password", ""), password):
        user_data["2fa_enabled"] = False
        user_data["2fa_secret"] = None
        if save_user_data(user_data):
            logger.info("2FA disabled successfully (password only).")
            return True
        else:
            logger.error("Failed to save user data after disabling 2FA (password only).")
            return False
    else:
        logger.warning("Failed to disable 2FA (password only): Invalid password provided.")
        return False

def disable_2fa_with_password_and_otp(username: str, password: str, otp_code: str) -> bool:
    """Disable 2FA for the specified user, requiring both password and OTP code."""
    user_data = get_user_data() # Assuming this gets data for the logged-in user implicitly
    
    # 1. Verify Password
    if not verify_password(user_data.get("password", ""), password):
        logger.warning(f"Failed to disable 2FA for '{username}': Invalid password provided.")
        return False
        
    # 2. Verify OTP Code against permanent secret
    perm_secret = user_data.get("2fa_secret")
    if not user_data.get("2fa_enabled") or not perm_secret:
        logger.error(f"Failed to disable 2FA for '{username}': 2FA is not enabled or secret missing.")
        # Should ideally not happen if called from the correct UI state, but good to check
        return False 
        
    totp = pyotp.TOTP(perm_secret)
    if not totp.verify(otp_code):
        logger.warning(f"Failed to disable 2FA for '{username}': Invalid OTP code provided.")
        return False
        
    # 3. Both verified, proceed to disable
    user_data["2fa_enabled"] = False
    user_data["2fa_secret"] = None
    if save_user_data(user_data):
        logger.info(f"2FA disabled successfully for '{username}' after verifying password and OTP.")
        return True
    else:
        logger.error(f"Failed to save user data after disabling 2FA for '{username}'.")
        return False

def change_username(current_username: str, new_username: str, password: str) -> bool:
    """Change the username for the current user"""
    user_data = get_user_data()
    
    # Verify current username and password
    current_username_hash = hash_username(current_username)
    if user_data.get("username") != current_username_hash:
        logger.warning(f"Username change failed: Current username '{current_username}' does not match stored hash.")
        return False
    
    if not verify_password(user_data.get("password", ""), password):
        logger.warning(f"Username change failed for '{current_username}': Invalid password provided.")
        return False
    
    # Update username
    user_data["username"] = hash_username(new_username)
    if save_user_data(user_data):
        logger.info(f"Username changed successfully from '{current_username}' to '{new_username}'.")
        return True
    else:
        logger.error(f"Failed to save user data after changing username for '{current_username}'.")
        return False

def change_password(current_password: str, new_password: str) -> bool:
    """Change the password for the current user"""
    user_data = get_user_data()
    
    # Verify current password
    if not verify_password(user_data.get("password", ""), current_password):
        logger.warning("Password change failed: Invalid current password provided.")
        return False
    
    # Update password
    user_data["password"] = hash_password(new_password)
    if save_user_data(user_data):
        logger.info("Password changed successfully.")
        return True
    else:
        logger.error("Failed to save user data after changing password.")
        return False

def get_app_url_and_key(app_type: str) -> Tuple[str, str]:
    """
    Get the API URL and API key for a specific app type
    
    Args:
        app_type: The app type (sonarr, radarr, lidarr, readarr)
    
    Returns:
        Tuple[str, str]: (api_url, api_key)
    """
    from primary import keys_manager
    return keys_manager.get_api_keys(app_type)