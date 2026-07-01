from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bot.config import get_settings, Settings
from bot.exceptions import AuthenticationError


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear the lru_cache of get_settings before each test."""
    get_settings.cache_clear()


def test_get_settings_raises_if_missing_keys():
    """Test that missing keys raise an error ONLY when get_settings is called."""
    with patch.dict(os.environ, clear=True):
        with pytest.raises(AuthenticationError):
            get_settings()


def test_get_settings_parses_use_testnet_true():
    """Test that USE_TESTNET=true is parsed as boolean True."""
    env = {
        "BINANCE_API_KEY": "key",
        "BINANCE_API_SECRET": "secret",
        "USE_TESTNET": "true",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.use_testnet is True
        assert settings.base_url == settings.testnet_url


def test_get_settings_parses_use_testnet_false():
    """Test that USE_TESTNET=false is parsed as boolean False."""
    env = {
        "BINANCE_API_KEY": "key",
        "BINANCE_API_SECRET": "secret",
        "USE_TESTNET": "false",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.use_testnet is False
        assert settings.base_url == settings.prod_url
