"""Extended auth tests — change_username, change_password, and 2FA functions.

Complements test_auth.py which covers hashing, sessions, and basic verify_user.
All tests that touch the credentials file use the config_dir fixture from conftest.py.
"""
import pyotp
import pytest

import src.primary.auth as auth


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(config_dir, username="testuser", password="TestPass1!"):
    """Create a test user and return (username, password)."""
    auth.create_user(username, password)
    return username, password


# ── change_username ───────────────────────────────────────────────────────────

def test_change_username_success(config_dir):
    _make_user(config_dir)
    assert auth.change_username("testuser", "newuser", "TestPass1!") is True


def test_change_username_updates_stored_hash(config_dir):
    _make_user(config_dir)
    auth.change_username("testuser", "newuser", "TestPass1!")
    data = auth.get_user_data()
    assert data["username"] == auth.hash_username("newuser")


def test_change_username_wrong_current_name_returns_false(config_dir):
    _make_user(config_dir)
    assert auth.change_username("wronguser", "newuser", "TestPass1!") is False


def test_change_username_wrong_password_returns_false(config_dir):
    _make_user(config_dir)
    assert auth.change_username("testuser", "newuser", "WrongPass99!") is False


def test_change_username_original_name_no_longer_valid_after_change(config_dir):
    _make_user(config_dir)
    auth.change_username("testuser", "newuser", "TestPass1!")
    # old username hash should not match
    data = auth.get_user_data()
    assert data["username"] != auth.hash_username("testuser")


# ── change_password ───────────────────────────────────────────────────────────

def test_change_password_success(config_dir):
    _make_user(config_dir)
    assert auth.change_password("TestPass1!", "NewPass99!") is True


def test_change_password_new_password_verifiable(config_dir):
    _make_user(config_dir)
    auth.change_password("TestPass1!", "NewPass99!")
    data = auth.get_user_data()
    assert auth.verify_password(data["password"], "NewPass99!") is True


def test_change_password_old_password_rejected_after_change(config_dir):
    _make_user(config_dir)
    auth.change_password("TestPass1!", "NewPass99!")
    data = auth.get_user_data()
    assert auth.verify_password(data["password"], "TestPass1!") is False


def test_change_password_wrong_current_returns_false(config_dir):
    _make_user(config_dir)
    assert auth.change_password("WrongPass!", "NewPass99!") is False


def test_change_password_wrong_current_leaves_data_unchanged(config_dir):
    _make_user(config_dir)
    before = auth.get_user_data()["password"]
    auth.change_password("WrongPass!", "NewPass99!")
    after = auth.get_user_data()["password"]
    assert before == after


# ── is_2fa_enabled ────────────────────────────────────────────────────────────

def test_2fa_disabled_by_default(config_dir):
    _make_user(config_dir)
    assert auth.is_2fa_enabled("testuser") is False


# ── generate_2fa_secret ───────────────────────────────────────────────────────

def test_generate_2fa_secret_returns_secret_and_qr(config_dir):
    _make_user(config_dir)
    secret, qr_uri = auth.generate_2fa_secret("testuser")
    assert secret
    assert qr_uri.startswith("data:image/png;base64,")


def test_generate_2fa_secret_stores_temp_secret(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    data = auth.get_user_data()
    assert data.get("temp_2fa_secret") == secret


def test_generate_2fa_secret_is_valid_base32(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    # Valid pyotp secret — should not raise
    totp = pyotp.TOTP(secret)
    assert len(totp.now()) == 6


# ── verify_2fa_code ───────────────────────────────────────────────────────────

def test_verify_2fa_code_no_temp_secret_returns_false(config_dir):
    _make_user(config_dir)
    assert auth.verify_2fa_code("testuser", "123456") is False


def test_verify_2fa_code_valid_code_returns_true(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    code = pyotp.TOTP(secret).now()
    assert auth.verify_2fa_code("testuser", code) is True


def test_verify_2fa_code_invalid_code_returns_false(config_dir):
    _make_user(config_dir)
    auth.generate_2fa_secret("testuser")
    assert auth.verify_2fa_code("testuser", "000000") is False


def test_verify_2fa_code_enable_on_verify_sets_2fa_enabled(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    code = pyotp.TOTP(secret).now()
    auth.verify_2fa_code("testuser", code, enable_on_verify=True)
    assert auth.get_user_data().get("2fa_enabled") is True


def test_verify_2fa_code_enable_on_verify_promotes_temp_to_permanent(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    code = pyotp.TOTP(secret).now()
    auth.verify_2fa_code("testuser", code, enable_on_verify=True)
    data = auth.get_user_data()
    assert data.get("2fa_secret") == secret
    assert "temp_2fa_secret" not in data


def test_verify_2fa_code_enable_on_verify_false_does_not_enable(config_dir):
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    code = pyotp.TOTP(secret).now()
    auth.verify_2fa_code("testuser", code, enable_on_verify=False)
    assert auth.get_user_data().get("2fa_enabled") is False


# ── disable_2fa ───────────────────────────────────────────────────────────────

def _enable_2fa(config_dir):
    """Helper: create user and enable 2FA. Returns (secret,)."""
    _make_user(config_dir)
    secret, _ = auth.generate_2fa_secret("testuser")
    code = pyotp.TOTP(secret).now()
    auth.verify_2fa_code("testuser", code, enable_on_verify=True)
    return secret


def test_disable_2fa_correct_password_returns_true(config_dir):
    _enable_2fa(config_dir)
    assert auth.disable_2fa("TestPass1!") is True


def test_disable_2fa_sets_flag_to_false(config_dir):
    _enable_2fa(config_dir)
    auth.disable_2fa("TestPass1!")
    assert auth.get_user_data().get("2fa_enabled") is False


def test_disable_2fa_clears_secret(config_dir):
    _enable_2fa(config_dir)
    auth.disable_2fa("TestPass1!")
    assert auth.get_user_data().get("2fa_secret") is None


def test_disable_2fa_wrong_password_returns_false(config_dir):
    _enable_2fa(config_dir)
    assert auth.disable_2fa("WrongPass!") is False


def test_disable_2fa_wrong_password_leaves_2fa_enabled(config_dir):
    _enable_2fa(config_dir)
    auth.disable_2fa("WrongPass!")
    assert auth.get_user_data().get("2fa_enabled") is True


# ── disable_2fa_with_password_and_otp ────────────────────────────────────────

def test_disable_2fa_with_otp_success(config_dir):
    secret = _enable_2fa(config_dir)
    code = pyotp.TOTP(secret).now()
    assert auth.disable_2fa_with_password_and_otp("testuser", "TestPass1!", code) is True


def test_disable_2fa_with_otp_disables_flag(config_dir):
    secret = _enable_2fa(config_dir)
    code = pyotp.TOTP(secret).now()
    auth.disable_2fa_with_password_and_otp("testuser", "TestPass1!", code)
    assert auth.get_user_data().get("2fa_enabled") is False


def test_disable_2fa_with_otp_wrong_password_returns_false(config_dir):
    secret = _enable_2fa(config_dir)
    code = pyotp.TOTP(secret).now()
    assert auth.disable_2fa_with_password_and_otp("testuser", "WrongPass!", code) is False


def test_disable_2fa_with_otp_invalid_otp_returns_false(config_dir):
    _enable_2fa(config_dir)
    assert auth.disable_2fa_with_password_and_otp("testuser", "TestPass1!", "000000") is False


def test_disable_2fa_with_otp_when_2fa_not_enabled_returns_false(config_dir):
    _make_user(config_dir)
    assert auth.disable_2fa_with_password_and_otp("testuser", "TestPass1!", "123456") is False


# ── verify_user with 2FA paths ────────────────────────────────────────────────

def test_verify_user_with_2fa_enabled_no_code_returns_needs_2fa(config_dir):
    secret = _enable_2fa(config_dir)
    success, needs_2fa = auth.verify_user("testuser", "TestPass1!")
    assert success is False
    assert needs_2fa is True


def test_verify_user_with_2fa_valid_code_returns_success(config_dir):
    secret = _enable_2fa(config_dir)
    code = pyotp.TOTP(secret).now()
    success, needs_2fa = auth.verify_user("testuser", "TestPass1!", otp_code=code)
    assert success is True
    assert needs_2fa is False


def test_verify_user_with_2fa_invalid_code_returns_needs_2fa(config_dir):
    _enable_2fa(config_dir)
    success, needs_2fa = auth.verify_user("testuser", "TestPass1!", otp_code="000000")
    assert success is False
    assert needs_2fa is True
