# tests/test_oauth.py
import os
from unittest.mock import AsyncMock, patch

import pytest

from middleware.oauth import check_group_membership, oauth_configured


# ── check_group_membership ─────────────────────────────────


class TestCheckGroupMembership:
    """Tests for the group membership checker."""

    def test_no_required_group_allows_anyone(self):
        with patch.dict(os.environ, {"OAUTH_ALLOWED_GROUP": ""}, clear=False):
            # Reload the module-level constant
            import middleware.oauth as mod

            orig = mod.OAUTH_ALLOWED_GROUP
            mod.OAUTH_ALLOWED_GROUP = ""
            try:
                assert check_group_membership({}) is True
                assert check_group_membership({"groups": []}) is True
            finally:
                mod.OAUTH_ALLOWED_GROUP = orig

    def test_string_groups_match(self):
        import middleware.oauth as mod

        orig = mod.OAUTH_ALLOWED_GROUP
        mod.OAUTH_ALLOWED_GROUP = "admin"
        try:
            userinfo = {"groups": ["users", "admin", "editors"]}
            assert check_group_membership(userinfo) is True
        finally:
            mod.OAUTH_ALLOWED_GROUP = orig

    def test_dict_groups_match(self):
        """Pocket ID returns groups as list of dicts with 'name' key."""
        import middleware.oauth as mod

        orig = mod.OAUTH_ALLOWED_GROUP
        mod.OAUTH_ALLOWED_GROUP = "admin"
        try:
            userinfo = {"groups": [{"name": "users"}, {"name": "admin"}]}
            assert check_group_membership(userinfo) is True
        finally:
            mod.OAUTH_ALLOWED_GROUP = orig

    def test_group_not_present(self):
        import middleware.oauth as mod

        orig = mod.OAUTH_ALLOWED_GROUP
        mod.OAUTH_ALLOWED_GROUP = "admin"
        try:
            userinfo = {"groups": ["users", "editors"]}
            assert check_group_membership(userinfo) is False
        finally:
            mod.OAUTH_ALLOWED_GROUP = orig

    def test_no_groups_claim(self):
        import middleware.oauth as mod

        orig = mod.OAUTH_ALLOWED_GROUP
        mod.OAUTH_ALLOWED_GROUP = "admin"
        try:
            assert check_group_membership({}) is False
        finally:
            mod.OAUTH_ALLOWED_GROUP = orig


# ── oauth_configured ───────────────────────────────────────


class TestOAuthConfigured:
    def test_configured_when_all_vars_set(self):
        import middleware.oauth as mod

        orig = (mod.OAUTH_CLIENT_ID, mod.OAUTH_ISSUER_URL, mod.OAUTH_REDIRECT_URI)
        mod.OAUTH_CLIENT_ID = "test-id"
        mod.OAUTH_ISSUER_URL = "https://id.example.com"
        mod.OAUTH_REDIRECT_URI = "https://app.example.com/admin/oauth/callback"
        try:
            assert oauth_configured() is True
        finally:
            mod.OAUTH_CLIENT_ID, mod.OAUTH_ISSUER_URL, mod.OAUTH_REDIRECT_URI = orig

    def test_not_configured_when_missing(self):
        import middleware.oauth as mod

        orig = mod.OAUTH_CLIENT_ID
        mod.OAUTH_CLIENT_ID = ""
        try:
            assert oauth_configured() is False
        finally:
            mod.OAUTH_CLIENT_ID = orig


# ── get_authorization_url ──────────────────────────────────


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_url_state_verifier(self):
        import middleware.oauth as mod

        mod.OAUTH_CLIENT_ID = "test-client"
        mod.OAUTH_CLIENT_SECRET = "test-secret"
        mod.OAUTH_REDIRECT_URI = "https://app.example.com/callback"
        mod.OAUTH_SCOPE = "openid profile email groups"
        mod._oidc_config = {
            "authorization_endpoint": "https://id.example.com/authorize",
            "token_endpoint": "https://id.example.com/token",
            "userinfo_endpoint": "https://id.example.com/userinfo",
        }

        try:
            url, state, code_verifier = await mod.get_authorization_url()
            assert "https://id.example.com/authorize" in url
            assert "client_id=test-client" in url
            assert "code_challenge=" in url
            assert "code_challenge_method=S256" in url
            assert len(state) > 0
            assert len(code_verifier) > 0
        finally:
            mod._oidc_config = None


# ── exchange_code ──────────────────────────────────────────


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_exchanges_code_and_returns_userinfo(self):
        import middleware.oauth as mod

        mod.OAUTH_CLIENT_ID = "test-client"
        mod.OAUTH_CLIENT_SECRET = "test-secret"
        mod.OAUTH_REDIRECT_URI = "https://app.example.com/callback"
        mod._oidc_config = {
            "authorization_endpoint": "https://id.example.com/authorize",
            "token_endpoint": "https://id.example.com/token",
            "userinfo_endpoint": "https://id.example.com/userinfo",
        }

        fake_token = {"access_token": "fake-token", "token_type": "Bearer"}
        fake_userinfo = {"sub": "user-1", "email": "test@example.com", "groups": ["admin"]}

        mock_resp = AsyncMock()
        mock_resp.json = lambda: fake_userinfo
        mock_resp.raise_for_status = lambda: None

        with patch("middleware.oauth.AsyncOAuth2Client") as MockClient:
            instance = AsyncMock()
            instance.fetch_token = AsyncMock(return_value=fake_token)
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            try:
                result = await mod.exchange_code("auth-code", "state-val", "verifier-val")
                assert result == fake_userinfo
                instance.fetch_token.assert_awaited_once()
                instance.get.assert_awaited_once()
            finally:
                mod._oidc_config = None
