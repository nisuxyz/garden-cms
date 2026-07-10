# middleware/oauth.py
"""OAuth2 / OIDC helpers for Pocket ID (or any standard provider)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client

_log = logging.getLogger(__name__)

# ── Configuration from environment ────────────────────────

OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "")
OAUTH_ISSUER_URL: str = os.getenv("OAUTH_ISSUER_URL", "").rstrip("/")
OAUTH_REDIRECT_URI: str = os.getenv("OAUTH_REDIRECT_URI", "")
OAUTH_ALLOWED_GROUP: str = os.getenv("OAUTH_ALLOWED_GROUP", "")
OAUTH_SCOPE: str = os.getenv("OAUTH_SCOPE", "openid profile email groups")

# Network operations against the IdP should never hang indefinitely.
_OAUTH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Warn loudly once if OAuth is configured without an allowed-group restriction
# — that ships a default-admin posture where anyone who can authenticate
# against the issuer becomes a CMS admin.
if OAUTH_CLIENT_ID and not OAUTH_ALLOWED_GROUP:
    _log.warning(
        "OAUTH_ALLOWED_GROUP is empty — any user who can authenticate against "
        "%s will be granted admin access. Set OAUTH_ALLOWED_GROUP to restrict.",
        OAUTH_ISSUER_URL,
    )

# Cached OIDC discovery document
_oidc_config: dict[str, Any] | None = None


def oauth_configured() -> bool:
    """Return True when all required OAuth env vars are set."""
    return bool(OAUTH_CLIENT_ID and OAUTH_ISSUER_URL and OAUTH_REDIRECT_URI)


async def _discover_oidc() -> dict[str, Any]:
    """Fetch and cache the OIDC discovery document from the issuer."""
    global _oidc_config
    if _oidc_config is not None:
        return _oidc_config

    url = f"{OAUTH_ISSUER_URL}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=_OAUTH_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _oidc_config = resp.json()
    return _oidc_config


async def get_authorization_url() -> tuple[str, str, str]:
    """Build the authorization URL with PKCE.

    Returns:
        (authorization_url, state, code_verifier)
    """
    oidc = await _discover_oidc()
    authorization_endpoint: str = oidc["authorization_endpoint"]

    code_verifier = generate_token(48)
    state = generate_token(32)

    client = AsyncOAuth2Client(
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET or None,
        redirect_uri=OAUTH_REDIRECT_URI,
        scope=OAUTH_SCOPE,
        code_challenge_method="S256",
        timeout=_OAUTH_TIMEOUT,
    )

    url, _state = client.create_authorization_url(
        authorization_endpoint,
        state=state,
        code_verifier=code_verifier,
    )

    return url, state, code_verifier


async def exchange_code(
    code: str,
    state: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange the authorization code for tokens and fetch userinfo.

    Returns:
        The userinfo dict from the provider.

    Raises:
        Exception on token exchange or userinfo failure.
    """
    oidc = await _discover_oidc()
    token_endpoint: str = oidc["token_endpoint"]
    userinfo_endpoint: str = oidc["userinfo_endpoint"]

    async with AsyncOAuth2Client(
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET or None,
        redirect_uri=OAUTH_REDIRECT_URI,
        code_challenge_method="S256",
        timeout=_OAUTH_TIMEOUT,
    ) as client:
        await client.fetch_token(
            token_endpoint,
            code=code,
            code_verifier=code_verifier,
        )

        resp = await client.get(userinfo_endpoint)
        resp.raise_for_status()
        return resp.json()


def check_group_membership(userinfo: dict[str, Any]) -> bool:
    """Check whether the user belongs to the required group.

    If ``OAUTH_ALLOWED_GROUP`` is not set, any authenticated user is allowed
    (a warning is logged at import time). The ``groups`` claim is expected
    to be a list of group dicts with a ``name`` key (Pocket ID format) or a
    plain list of strings.
    """
    required = OAUTH_ALLOWED_GROUP
    if not required:
        return True

    groups = userinfo.get("groups", [])
    for group in groups:
        if isinstance(group, dict):
            if group.get("name") == required:
                return True
        elif isinstance(group, str):
            if group == required:
                return True
    return False
