"""Tests for src/primary/auth.py — password hashing, validation, sessions."""
import json
import re
import time

import bcrypt
import pytest

import src.primary.auth as auth
from tests.conftest import make_legacy_sha256_hash


# ── Password hashing ──────────────────────────────────────────────────────────

def test_hash_password_produces_bcrypt():
    h = auth.hash_password("correcthorsebattery")
    assert h.startswith("$2b$") or h.startswith("$2a$")


def test_hash_password_unique_salts():
    h1 = auth.hash_password("samepassword")
    h2 = auth.hash_password("samepassword")
    assert h1 != h2


def test_verify_password_correct_bcrypt():
    h = auth.hash_password("mypassword")
    assert auth.verify_password(h, "mypassword") is True


def test_verify_password_wrong_bcrypt():
    h = auth.hash_password("mypassword")
    assert auth.verify_password(h, "wrongpassword") is False


def test_verify_password_legacy_sha256_correct():
    legacy = make_legacy_sha256_hash("legacypass")
    assert auth.verify_password(legacy, "legacypass") is True


def test_verify_password_legacy_sha256_wrong():
    legacy = make_legacy_sha256_hash("legacypass")
    assert auth.verify_password(legacy, "wrongpass") is False


def test_verify_password_garbage_input_returns_false():
    assert auth.verify_password("notahash", "anything") is False


# ── Username hashing ──────────────────────────────────────────────────────────

def test_hash_username_deterministic():
    assert auth.hash_username("admin") == auth.hash_username("admin")


def test_hash_username_case_insensitive():
    assert auth.hash_username("Admin") == auth.hash_username("admin")
    assert auth.hash_username("ADMIN") == auth.hash_username("admin")


def test_hash_username_different_inputs_differ():
    assert auth.hash_username("alice") != auth.hash_username("bob")


# ── Password strength ─────────────────────────────────────────────────────────

def test_validate_password_too_short():
    result = auth.validate_password_strength("Sh0rt!")
    assert result is not None
    assert "12" in result


def test_validate_password_no_digit():
    result = auth.validate_password_strength("NoDigitsHere!!")
    assert result is not None
    assert "number" in result


def test_validate_password_no_special():
    result = auth.validate_password_strength("NoSpecialChar1234")
    assert result is not None
    assert "special" in result


def test_validate_password_valid():
    assert auth.validate_password_strength("ValidPass1!secure") is None


# ── Sessions ──────────────────────────────────────────────────────────────────

def test_create_session_returns_nonempty_token(config_dir):
    token = auth.create_session("testuser")
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_session_valid(config_dir):
    token = auth.create_session("testuser")
    assert auth.verify_session(token) is True


def test_verify_session_unknown_token(config_dir):
    assert auth.verify_session("notarealtoken") is False


def test_verify_session_empty_string(config_dir):
    assert auth.verify_session("") is False


def test_logout_invalidates_session(config_dir):
    token = auth.create_session("testuser")
    assert auth.verify_session(token) is True
    auth.logout(token)
    assert auth.verify_session(token) is False


def test_get_username_from_session(config_dir):
    token = auth.create_session("alice")
    assert auth.get_username_from_session(token) == "alice"


def test_get_username_from_invalid_session_returns_none(config_dir):
    assert auth.get_username_from_session("badtoken") is None


# ── Recovery codes ────────────────────────────────────────────────────────────

def test_generate_recovery_codes_count():
    codes = auth.generate_recovery_codes()
    assert len(codes) == auth._RECOVERY_CODE_COUNT


def test_generate_recovery_codes_format():
    codes = auth.generate_recovery_codes()
    pattern = re.compile(r'^[A-Z0-9]{5}-[A-Z0-9]{5}$')
    for code in codes:
        assert pattern.match(code), f"Unexpected format: {code}"


def test_generate_recovery_codes_unique():
    codes = auth.generate_recovery_codes()
    assert len(set(codes)) == len(codes)


def test_store_and_count_recovery_codes(config_dir):
    # Write a minimal credentials file first
    user_data = {
        "username": auth.hash_username("alice"),
        "password": auth.hash_password("ValidPass1!"),
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    codes = auth.generate_recovery_codes()
    assert auth.store_recovery_codes(codes) is True
    assert auth.get_recovery_code_count() == auth._RECOVERY_CODE_COUNT


def test_use_recovery_code_valid(config_dir):
    user_data = {
        "username": auth.hash_username("alice"),
        "password": auth.hash_password("ValidPass1!"),
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    codes = auth.generate_recovery_codes()
    auth.store_recovery_codes(codes)

    assert auth.use_recovery_code(codes[0]) is True
    # One code consumed
    assert auth.get_recovery_code_count() == auth._RECOVERY_CODE_COUNT - 1


def test_use_recovery_code_invalid(config_dir):
    user_data = {
        "username": auth.hash_username("alice"),
        "password": auth.hash_password("ValidPass1!"),
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    codes = auth.generate_recovery_codes()
    auth.store_recovery_codes(codes)

    assert auth.use_recovery_code("AAAAA-BBBBB") is False
    # Count unchanged
    assert auth.get_recovery_code_count() == auth._RECOVERY_CODE_COUNT


def test_use_recovery_code_single_use(config_dir):
    user_data = {
        "username": auth.hash_username("alice"),
        "password": auth.hash_password("ValidPass1!"),
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    codes = auth.generate_recovery_codes()
    auth.store_recovery_codes(codes)

    assert auth.use_recovery_code(codes[0]) is True
    assert auth.use_recovery_code(codes[0]) is False  # already consumed


def test_use_recovery_code_case_insensitive(config_dir):
    user_data = {
        "username": auth.hash_username("alice"),
        "password": auth.hash_password("ValidPass1!"),
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    codes = auth.generate_recovery_codes()
    auth.store_recovery_codes(codes)

    # Codes are uppercase; submit lowercase with hyphen — should still match
    lower = codes[0].lower()
    assert auth.use_recovery_code(lower) is True


# ── bcrypt migration ──────────────────────────────────────────────────────────

def test_verify_user_upgrades_legacy_hash_on_login(config_dir):
    """verify_user silently re-hashes a legacy SHA-256 password to bcrypt."""
    username = "migrationuser"
    password = "password123"
    legacy_hash = make_legacy_sha256_hash(password)

    user_data = {
        "username": auth.hash_username(username),
        "password": legacy_hash,
        "2fa_enabled": False,
        "2fa_secret": None,
    }
    with open(auth.USER_FILE, "w") as f:
        json.dump(user_data, f)

    success, needs_2fa = auth.verify_user(username, password)
    assert success is True
    assert needs_2fa is False

    # Hash should now be bcrypt
    with open(auth.USER_FILE) as f:
        updated = json.load(f)
    stored = updated["password"]
    assert stored.startswith("$2b$") or stored.startswith("$2a$")
