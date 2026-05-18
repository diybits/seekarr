"""
Shared test fixtures.

Module-level code sets CONFIG_DIR before state.py is imported so that
state.py's init_state_files() uses a writable temp directory rather than
/config. The try/except wrappers in settings_manager and auth mean those
modules import cleanly in CI where /config doesn't exist.
"""
import hashlib
import os
import pathlib
import secrets
import tempfile

import pytest

# Set CONFIG_DIR early — state.py reads this at import time
_session_tmp = pathlib.Path(tempfile.mkdtemp(prefix="seekarr_test_"))
os.environ["CONFIG_DIR"] = str(_session_tmp)

# Set STATEFUL_DIR early — stateful_manager.py reads this at import time and
# runs mkdir calls that would fail without a writable path.
_stateful_tmp = pathlib.Path(tempfile.mkdtemp(prefix="seekarr_stateful_"))
os.environ["STATEFUL_DIR"] = str(_stateful_tmp)

# Import modules after env vars are set.
import src.primary.auth as _auth_mod
import src.primary.settings_manager as _sm_mod
import src.primary.stats_manager as _stats_mod
import src.primary.stateful_manager as _stateful_mod


@pytest.fixture()
def config_dir(tmp_path, monkeypatch):
    """Per-test isolated config directory with all module paths redirected."""
    cfg = tmp_path / "config"
    cfg.mkdir()

    # settings_manager
    monkeypatch.setattr(_sm_mod, "SETTINGS_DIR", cfg)
    monkeypatch.setattr(_sm_mod, "settings_cache", {})

    # auth
    user_dir = cfg / "user"
    user_dir.mkdir()
    monkeypatch.setattr(_auth_mod, "USER_DIR", user_dir)
    monkeypatch.setattr(_auth_mod, "USER_FILE", user_dir / "credentials.json")
    monkeypatch.setattr(_auth_mod, "_SESSIONS_FILE", cfg / "sessions.json")
    monkeypatch.setattr(_auth_mod, "active_sessions", {})

    # stats_manager
    tally = cfg / "tally"
    tally.mkdir()
    monkeypatch.setattr(_stats_mod, "STATS_DIR", str(tally))
    monkeypatch.setattr(_stats_mod, "STATS_FILE", str(tally / "media_stats.json"))
    monkeypatch.setattr(_stats_mod, "HOURLY_CAP_FILE", str(tally / "hourly_cap.json"))

    # state.py reads CONFIG_DIR from env at call time via os.environ
    monkeypatch.setenv("CONFIG_DIR", str(cfg))

    return cfg


def make_legacy_sha256_hash(password: str) -> str:
    """Create a legacy SHA-256 salt:hash credential string for migration tests."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{pw_hash}"
